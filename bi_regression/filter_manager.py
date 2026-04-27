"""
filter_manager.py — Discovers and interacts with Tableau dashboard filters.

Supports filter types
---------------------
  - dropdown : Single-select dropdown / combobox filters  (default)
  - input    : Text or date input filters

Strategy (per filter)
---------------------
1. Iterate every frame on the page (Tableau content lives in iframes).
2. Locate the filter **label** by exact text match.
3. Walk up the DOM to the nearest filter container and locate the
   interactive control (<select>, <input>, or Tableau custom dropdown).
4. If DOM traversal fails, fall back to **position-based** clicking:
   click just below / to the right of the label where the control is
   visually rendered.
5. After all filters are applied, wait for the dashboard to re-render.
"""
from __future__ import annotations

import logging
import time
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.sync_api import Page


# JS executed inside each frame to find a filter container near a given label.
# Returns {found, hasInput, hasSelect, containerBox, inputBox, selectBox}
_FIND_FILTER_JS = """
(filterName) => {
    // Walk all elements looking for one whose trimmed text is exactly filterName
    const walker = document.createTreeWalker(
        document.body, NodeFilter.SHOW_ELEMENT, null
    );
    let labelEl = null;
    while (walker.nextNode()) {
        const el = walker.currentNode;
        // Only consider leaf-like labels (small text nodes)
        const text = el.textContent && el.textContent.trim();
        if (!text || text !== filterName) continue;
        // Prefer elements whose *own* direct text matches (avoid large parents)
        const childText = Array.from(el.childNodes)
            .filter(n => n.nodeType === 3)
            .map(n => n.textContent.trim())
            .join('');
        if (childText === filterName || el.children.length === 0) {
            labelEl = el;
            break;
        }
    }
    if (!labelEl) return { found: false };

    // Walk up to find a reasonable container (max 6 levels)
    let container = labelEl;
    for (let i = 0; i < 6; i++) {
        if (!container.parentElement) break;
        container = container.parentElement;
        const cls = (container.className || '').toLowerCase();
        if (cls.includes('filter') || cls.includes('fi-panel') ||
            cls.includes('tab-widget') || cls.includes('fipanel') ||
            cls.includes('fiitem') || cls.includes('quick-filter'))
            break;
    }

    const labelBox = labelEl.getBoundingClientRect();
    const containerBox = container.getBoundingClientRect();

    // Look for an <input> in the container
    const inp = container.querySelector('input[type="text"], input:not([type])');
    const inpBox = inp ? inp.getBoundingClientRect() : null;

    // Look for a <select> in the container
    const sel = container.querySelector('select');
    const selBox = sel ? sel.getBoundingClientRect() : null;

    return {
        found: true,
        labelBox: { x: labelBox.x, y: labelBox.y, w: labelBox.width, h: labelBox.height },
        containerBox: { x: containerBox.x, y: containerBox.y, w: containerBox.width, h: containerBox.height },
        hasInput: !!inp,
        inputBox: inpBox ? { x: inpBox.x, y: inpBox.y, w: inpBox.width, h: inpBox.height } : null,
        hasSelect: !!sel,
        selectBox: selBox ? { x: selBox.x, y: selBox.y, w: selBox.width, h: selBox.height } : null,
    };
}
"""


class FilterManager:
    """
    Applies a set of filter values to a Tableau dashboard page.

    Usage::

        fm = FilterManager(page, logger)
        applied = fm.apply_scenario(scenario.filters, render_wait=6)
    """

    def __init__(self, page: "Page", logger: logging.Logger):
        self.page = page
        self.logger = logger

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def apply_scenario(self, filters: List, render_wait: int = 6) -> int:
        """
        Apply every filter in *filters* (list of FilterSetting objects)
        and return the number that were successfully applied.
        """
        applied = 0
        for f in filters:
            ok = self._apply_one(f.name, f.value, f.type)
            if ok:
                applied += 1
            else:
                self.logger.warning(
                    f"  [yellow]Could not apply filter[/] '{f.name}' = '{f.value}'"
                )
            # Brief pause between individual filter changes
            time.sleep(1)

        self.logger.debug(f"  Waiting {render_wait}s for dashboard re-render…")
        try:
            self.page.wait_for_load_state("networkidle", timeout=15_000)
        except Exception:
            pass
        time.sleep(render_wait)
        return applied

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    def _apply_one(self, name: str, value: str, ftype: str) -> bool:
        self.logger.info(f"  Applying filter: [cyan]{name}[/] → '{value}' (type={ftype})")
        if ftype in ("input", "date", "text"):
            return self._apply_input(name, value)
        # Default: dropdown
        return self._apply_dropdown(name, value)

    # ------------------------------------------------------------------
    # Dropdown filter
    # ------------------------------------------------------------------

    def _apply_dropdown(self, name: str, value: str) -> bool:
        for frame in self.page.frames:
            try:
                info = frame.evaluate(_FIND_FILTER_JS, name)
                if not info.get("found"):
                    continue

                self.logger.debug(f"    Filter '{name}' found in frame '{frame.name}'")

                # ---- Strategy 1: native <select> --------------------------------
                if info["hasSelect"]:
                    try:
                        sel = frame.locator(
                            f"xpath=//select[ancestor::*[.//text()[normalize-space()='{name}']]]"
                        ).first
                        if sel.count():
                            sel.select_option(label=value)
                            self.logger.info(f"    ✓ Applied via <select>: {name} = {value}")
                            return True
                    except Exception as e:
                        self.logger.debug(f"    <select> strategy failed: {e}")

                # ---- Strategy 2: click container area to open dropdown -----------
                cbox = info["containerBox"]
                label_box = info["labelBox"]

                # Click the dropdown trigger (usually to the right of or below the label)
                trigger_x = cbox["x"] + cbox["w"] / 2
                trigger_y = label_box["y"] + label_box["h"] + 15
                if trigger_y > cbox["y"] + cbox["h"]:
                    trigger_y = cbox["y"] + cbox["h"] - 10

                self.logger.debug(
                    f"    Clicking dropdown trigger at ({trigger_x:.0f}, {trigger_y:.0f})"
                )
                self.page.mouse.click(trigger_x, trigger_y)
                time.sleep(1)

                # Look for the value in the opened popup across all frames
                if self._click_option_text(value):
                    self.logger.info(f"    ✓ Applied via dropdown click: {name} = {value}")
                    return True

                # Dismiss any open popup by pressing Escape
                self.page.keyboard.press("Escape")
                time.sleep(0.3)

            except Exception as exc:
                self.logger.debug(f"    Dropdown frame search error: {exc}")
                continue

        return False

    # ------------------------------------------------------------------
    # Input / Date filter
    # ------------------------------------------------------------------

    def _apply_input(self, name: str, value: str) -> bool:
        for frame in self.page.frames:
            try:
                info = frame.evaluate(_FIND_FILTER_JS, name)
                if not info.get("found"):
                    continue

                self.logger.debug(f"    Filter '{name}' found in frame '{frame.name}'")

                # ---- Strategy 1: direct <input> element -------------------------
                if info["hasInput"] and info["inputBox"]:
                    ibox = info["inputBox"]
                    click_x = ibox["x"] + ibox["w"] / 2
                    click_y = ibox["y"] + ibox["h"] / 2
                    self.logger.debug(
                        f"    Clicking input at ({click_x:.0f}, {click_y:.0f})"
                    )
                    self.page.mouse.click(click_x, click_y)
                    time.sleep(0.3)
                    # Select all existing text and replace
                    self.page.keyboard.press("Meta+a")
                    time.sleep(0.1)
                    self.page.keyboard.type(value, delay=30)
                    time.sleep(0.2)
                    self.page.keyboard.press("Enter")
                    self.logger.info(f"    ✓ Applied via <input>: {name} = {value}")
                    return True

                # ---- Strategy 2: click below label and type ---------------------
                label_box = info["labelBox"]
                click_x = label_box["x"] + label_box["w"] / 2
                click_y = label_box["y"] + label_box["h"] + 15
                self.logger.debug(
                    f"    Clicking below label at ({click_x:.0f}, {click_y:.0f})"
                )
                self.page.mouse.click(click_x, click_y)
                time.sleep(0.3)
                self.page.keyboard.press("Meta+a")
                time.sleep(0.1)
                self.page.keyboard.type(value, delay=30)
                time.sleep(0.2)
                self.page.keyboard.press("Enter")
                self.logger.info(f"    ✓ Applied via positional click: {name} = {value}")
                return True

            except Exception as exc:
                self.logger.debug(f"    Input frame search error: {exc}")
                continue

        return False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _click_option_text(self, value: str) -> bool:
        """Find and click an element with the given text in any frame."""
        for frame in self.page.frames:
            try:
                loc = frame.get_by_text(value, exact=True)
                if loc.count() > 0:
                    # Prefer visible, clickable elements
                    for i in range(loc.count()):
                        el = loc.nth(i)
                        if el.is_visible():
                            el.click()
                            time.sleep(0.5)
                            return True
            except Exception:
                continue
        return False
