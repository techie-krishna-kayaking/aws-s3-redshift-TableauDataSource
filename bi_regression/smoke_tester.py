"""
smoke_tester.py — Validates Tableau dashboard UI against configured font/color/size standards.

Strategy
--------
Tableau Cloud renders its viz inside nested iframes.  We iterate through ALL
frames on the page and extract computed styles for every visible text element.
For elements not reachable via JS (SVG <text> nodes inside cross-origin iframes)
we still extract what we can from same-origin frames.

Violations are drawn as red boxes + annotation text directly on the screenshot
using Pillow, so every failure screenshot is self-documenting.
"""
from __future__ import annotations

import re
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import Page

from bi_regression.config_parser import TestConfig
from bi_regression.browser_manager import BrowserManager
from bi_regression.tab_navigator import TabNavigator, TabInfo
from bi_regression.output_manager import OutputManager


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class SmokeViolation:
    violation_type: str   # "font_family" | "font_size" | "color"
    expected: List[str]
    found: str
    element_text: str
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0

    @property
    def annotation(self) -> str:
        exp = ", ".join(self.expected[:3])  # truncate long lists
        return f"{self.violation_type}: expected [{exp}], found '{self.found}'"


@dataclass
class TabSmokeResult:
    tab_name: str
    passed: bool
    violations: List[SmokeViolation] = field(default_factory=list)
    screenshot_path: str = ""
    annotated_path: str = ""
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# JavaScript injected into every frame to extract computed styles
# ---------------------------------------------------------------------------

_EXTRACT_JS = """
() => {
    const results = [];
    const selectors = [
        'text', 'tspan',                         // SVG text
        'span', 'div', 'p', 'td', 'th',
        'h1','h2','h3','h4','h5','h6','label',
        '[class*="label"]', '[class*="text"]',
        '[class*="tooltip"]'
    ];

    function rgb2hex(rgb) {
        const m = rgb.match(/\\d+/g);
        if (!m || m.length < 3) return rgb;
        return '#' + m.slice(0,3).map(x =>
            parseInt(x).toString(16).padStart(2,'0').toUpperCase()
        ).join('');
    }

    const seen = new Set();
    for (const sel of selectors) {
        let elems;
        try { elems = document.querySelectorAll(sel); } catch(e) { continue; }
        for (const el of elems) {
            const txt = (el.textContent || el.innerHTML || '').trim().substring(0, 60);
            if (!txt || seen.has(txt)) continue;
            seen.add(txt);
            const rect  = el.getBoundingClientRect();
            if (rect.width < 1 || rect.height < 1) continue;
            const style = window.getComputedStyle(el);
            results.push({
                tag:        el.tagName,
                text:       txt,
                fontFamily: (style.fontFamily || '').replace(/['"]/g,'').split(',')[0].trim(),
                fontSize:   style.fontSize   || '',
                color:      rgb2hex(style.color || ''),
                x: rect.left, y: rect.top,
                w: rect.width, h: rect.height
            });
        }
    }
    return results;
}
"""


# ---------------------------------------------------------------------------
# SmokeTester
# ---------------------------------------------------------------------------

class SmokeTester:
    def __init__(
        self,
        browser_mgr: BrowserManager,
        config: TestConfig,
        output_mgr: OutputManager,
        logger: logging.Logger,
    ):
        self.bm = browser_mgr
        self.config = config
        self.output = output_mgr
        self.logger = logger
        self.standards = config.smoke.ui_standards

    # ------------------------------------------------------------------

    def run(self) -> List[TabSmokeResult]:
        self.logger.info(
            "[bold green]╔══════════════════════════════════════╗[/]"
        )
        self.logger.info(
            "[bold green]║         SMOKE TESTING                ║[/]"
        )
        self.logger.info(
            "[bold green]╚══════════════════════════════════════╝[/]"
        )
        url = self.config.smoke.dashboard_url
        self.logger.info(f"[bold]Dashboard:[/] {url}")

        page = self.bm.new_page()
        self.bm.navigate_with_retry(page, url, label="Smoke")

        navigator = TabNavigator(page, self.logger)
        tabs = navigator.get_all_tabs()

        results: List[TabSmokeResult] = []
        for tab in tabs:
            result = self._test_tab(page, tab, navigator)
            results.append(result)

        page.close()
        self._log_summary(results)
        return results

    # ------------------------------------------------------------------

    def _test_tab(self, page: Page, tab: TabInfo, navigator: TabNavigator) -> TabSmokeResult:
        self.logger.info(f"  Testing tab: [cyan]'{tab.name}'[/]")

        if tab.index > 0:
            navigator.navigate_to_tab(tab, render_wait=self.config.browser.render_wait_seconds)

        # Take raw screenshot
        raw_ss_path = self.output.pass_path(f"raw_{_slug(tab.name)}")
        try:
            page.screenshot(path=str(raw_ss_path), full_page=True)
        except Exception as e:
            self.logger.warning(f"Screenshot failed for tab '{tab.name}': {e}")
            return TabSmokeResult(tab_name=tab.name, passed=False, error=str(e))

        # Extract styles from all accessible frames
        elements = self._extract_all_frame_styles(page)
        self.logger.debug(f"  Extracted {len(elements)} elements from all frames.")

        # Check against standards
        violations: List[SmokeViolation] = []
        for el in elements:
            violations += self._check_element(el)

        passed = len(violations) == 0

        # Build annotated screenshot if there are violations
        annotated_path = ""
        if violations:
            ann_path = self.output.fail_path(_slug(tab.name))
            annotated_path = self._annotate_screenshot(str(raw_ss_path), violations, str(ann_path), tab.name)
            self.logger.warning(
                f"  [red]FAIL[/] — {len(violations)} violation(s) on tab '{tab.name}'"
            )
        else:
            self.logger.info(f"  [green]PASS[/] — tab '{tab.name}' is compliant.")

        return TabSmokeResult(
            tab_name=tab.name,
            passed=passed,
            violations=violations,
            screenshot_path=str(raw_ss_path),
            annotated_path=annotated_path,
        )

    # ------------------------------------------------------------------

    def _extract_all_frame_styles(self, page: Page) -> list:
        """Extract styles from the main page + all accessible iframes."""
        all_elements = []

        # Main frame
        try:
            all_elements += page.evaluate(_EXTRACT_JS) or []
        except Exception as e:
            self.logger.debug(f"Main frame extraction failed: {e}")

        # Child frames
        for frame in page.frames:
            if frame == page.main_frame:
                continue
            try:
                items = frame.evaluate(_EXTRACT_JS) or []
                all_elements += items
            except Exception:
                pass  # cross-origin frame — skip silently

        return all_elements

    # ------------------------------------------------------------------

    def _check_element(self, el: dict) -> List[SmokeViolation]:
        violations = []
        text = el.get("text", "")
        x, y, w, h = el.get("x", 0), el.get("y", 0), el.get("w", 0), el.get("h", 0)

        # Font family
        ff = el.get("fontFamily", "")
        if ff and not _any_match(ff, self.standards.fonts_allowed):
            violations.append(SmokeViolation(
                violation_type="font_family",
                expected=self.standards.fonts_allowed,
                found=ff, element_text=text,
                x=x, y=y, width=w, height=h,
            ))

        # Font size
        fs = el.get("fontSize", "")
        if fs and not _exact_match(fs, self.standards.font_sizes_allowed):
            violations.append(SmokeViolation(
                violation_type="font_size",
                expected=self.standards.font_sizes_allowed,
                found=fs, element_text=text,
                x=x, y=y, width=w, height=h,
            ))

        # Color
        color = el.get("color", "")
        if color and color.startswith("#") and not _exact_match(color.upper(), self.standards.colors_allowed):
            violations.append(SmokeViolation(
                violation_type="color",
                expected=self.standards.colors_allowed,
                found=color.upper(), element_text=text,
                x=x, y=y, width=w, height=h,
            ))

        return violations

    # ------------------------------------------------------------------

    def _annotate_screenshot(
        self,
        src_path: str,
        violations: List[SmokeViolation],
        out_path: str,
        tab_name: str,
    ) -> str:
        img = Image.open(src_path).convert("RGB")
        draw = ImageDraw.Draw(img, "RGBA")

        try:
            font_ann = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 13)
            font_hdr = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 20)
        except Exception:
            font_ann = ImageFont.load_default()
            font_hdr = font_ann

        # Header banner
        banner_h = 50
        header = Image.new("RGB", (img.width, banner_h), color=(180, 0, 0))
        draw_h = ImageDraw.Draw(header)
        draw_h.text(
            (15, 14),
            f"SMOKE FAIL — Tab: '{tab_name}'  |  {len(violations)} violation(s)",
            fill=(255, 255, 255), font=font_hdr,
        )
        combined = Image.new("RGB", (img.width, img.height + banner_h))
        combined.paste(header, (0, 0))
        combined.paste(img, (0, banner_h))
        draw = ImageDraw.Draw(combined, "RGBA")

        # Draw violation boxes
        for v in violations:
            if v.width < 1 or v.height < 1:
                continue
            x0 = int(v.x)
            y0 = int(v.y) + banner_h
            x1 = int(v.x + v.width)
            y1 = int(v.y + v.height) + banner_h

            # Translucent red fill + solid border
            draw.rectangle([x0, y0, x1, y1], fill=(255, 0, 0, 60), outline=(255, 0, 0, 255), width=2)
            # Label above the box
            label = v.annotation[:80]
            draw.rectangle([x0, y0 - 18, x0 + len(label) * 7, y0], fill=(180, 0, 0, 220))
            draw.text((x0 + 2, y0 - 16), label, fill=(255, 255, 255), font=font_ann)

        combined.save(out_path)
        return out_path

    # ------------------------------------------------------------------

    def _log_summary(self, results: List[TabSmokeResult]):
        passed = sum(1 for r in results if r.passed)
        total = len(results)
        self.logger.info(
            f"[bold]SMOKE TESTING Summary:[/] {passed}/{total} tabs passed."
        )


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _slug(name: str) -> str:
    """Convert a tab name to a safe filename fragment."""
    return re.sub(r"[^\w]+", "_", name).strip("_").lower()[:40]


def _any_match(value: str, allowed: List[str]) -> bool:
    """Case-insensitive substring match — e.g. 'Arial, sans-serif' matches 'Arial'."""
    v_lower = value.lower()
    return any(a.lower() in v_lower for a in allowed)


def _exact_match(value: str, allowed: List[str]) -> bool:
    """Case-insensitive exact match."""
    v_lower = value.lower()
    return any(a.lower() == v_lower for a in allowed)
