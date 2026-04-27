"""
performance_tester.py — Measures Tableau dashboard render and interaction performance.

For each dashboard:
  1. Measure first render time (navigation → dashboard fully rendered).
  2. Measure interaction time for one key action (filter change or tab switch).
  3. Repeat for N iterations, compute min / max / average.
  4. Compare against thresholds → PASS / FAIL.
  5. Capture screenshots for the report.
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from typing import List, Optional

from playwright.sync_api import Page

from bi_regression.config_parser import TestConfig, PerformanceDashboard
from bi_regression.browser_manager import BrowserManager
from bi_regression.output_manager import OutputManager
from bi_regression.filter_manager import FilterManager
from bi_regression.tab_navigator import TabNavigator


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class PerfIteration:
    iteration: int
    first_render_ms: float
    interaction_ms: float


@dataclass
class PerfDashboardResult:
    label: str
    url: str
    passed: bool
    iterations: List[PerfIteration] = field(default_factory=list)
    first_render_min: float = 0.0
    first_render_max: float = 0.0
    first_render_avg: float = 0.0
    interaction_min: float = 0.0
    interaction_max: float = 0.0
    interaction_avg: float = 0.0
    first_render_threshold: float = 0.0
    interaction_threshold: float = 0.0
    first_render_passed: bool = True
    interaction_passed: bool = True
    screenshot_path: str = ""
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Tableau render-detection selectors (same as browser_manager)
# ---------------------------------------------------------------------------

_TABLEAU_SELECTORS = [
    "tableau-viz",
    "#tableau-viz",
    ".tab-storyboard",
    "[data-tb-test-id='DesktopLayout']",
    ".tabCanvas",
    ".vizContainer",
]


# ---------------------------------------------------------------------------
# PerformanceTester
# ---------------------------------------------------------------------------

class PerformanceTester:
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
        self.perf_cfg = config.performance

    # ------------------------------------------------------------------

    def run(self) -> List[PerfDashboardResult]:
        self.logger.info(
            "[bold magenta]╔══════════════════════════════════════╗[/]"
        )
        self.logger.info(
            "[bold magenta]║       PERFORMANCE TESTING            ║[/]"
        )
        self.logger.info(
            "[bold magenta]╚══════════════════════════════════════╝[/]"
        )

        iterations = self.perf_cfg.iterations
        results: List[PerfDashboardResult] = []

        for dash in self.perf_cfg.dashboards:
            self.logger.info(
                f"[bold]Dashboard:[/] {dash.label}  |  Iterations: {iterations}"
            )
            self.logger.info(f"  URL: [cyan]{dash.url}[/]")
            result = self._test_dashboard(dash, iterations)
            results.append(result)

        self._log_summary(results)
        return results

    # ------------------------------------------------------------------

    def _test_dashboard(
        self, dash: PerformanceDashboard, num_iterations: int
    ) -> PerfDashboardResult:
        iters: List[PerfIteration] = []
        screenshot_path = ""

        for i in range(1, num_iterations + 1):
            self.logger.info(f"  [cyan]Iteration {i}/{num_iterations}[/]")
            page = self.bm.new_page()

            try:
                # ---- Measure first render time ----
                first_render_ms = self._measure_first_render(page, dash.url, dash.label)
                self.logger.info(
                    f"    First render: [bold]{first_render_ms:.0f} ms[/]"
                )

                # Take screenshot on first iteration
                if i == 1:
                    ss_path = self.output.perf_screenshot_path(
                        f"render_{_slug(dash.label)}"
                    )
                    try:
                        page.screenshot(path=str(ss_path), full_page=True)
                        screenshot_path = str(ss_path)
                    except Exception as e:
                        self.logger.warning(f"    Screenshot failed: {e}")

                # ---- Measure interaction time ----
                interaction_ms = 0.0
                if dash.interaction:
                    interaction_ms = self._measure_interaction(
                        page, dash
                    )
                    self.logger.info(
                        f"    Interaction ({dash.interaction.type}): "
                        f"[bold]{interaction_ms:.0f} ms[/]"
                    )

                    # Screenshot after interaction on first iteration
                    if i == 1:
                        ss_path2 = self.output.perf_screenshot_path(
                            f"interaction_{_slug(dash.label)}"
                        )
                        try:
                            page.screenshot(path=str(ss_path2), full_page=True)
                        except Exception:
                            pass

                iters.append(PerfIteration(
                    iteration=i,
                    first_render_ms=first_render_ms,
                    interaction_ms=interaction_ms,
                ))

            except Exception as exc:
                self.logger.error(f"    Iteration {i} failed: {exc}")
                iters.append(PerfIteration(
                    iteration=i,
                    first_render_ms=-1,
                    interaction_ms=-1,
                ))
            finally:
                try:
                    page.close()
                except Exception:
                    pass

        # ---- Compute stats ----
        valid_render = [it.first_render_ms for it in iters if it.first_render_ms >= 0]
        valid_interaction = [it.interaction_ms for it in iters if it.interaction_ms >= 0]

        fr_min = min(valid_render) if valid_render else 0
        fr_max = max(valid_render) if valid_render else 0
        fr_avg = sum(valid_render) / len(valid_render) if valid_render else 0

        ia_min = min(valid_interaction) if valid_interaction else 0
        ia_max = max(valid_interaction) if valid_interaction else 0
        ia_avg = sum(valid_interaction) / len(valid_interaction) if valid_interaction else 0

        fr_threshold = dash.thresholds.first_render_ms
        ia_threshold = dash.thresholds.interaction_ms

        fr_passed = fr_avg <= fr_threshold if valid_render else False
        ia_passed = ia_avg <= ia_threshold if valid_interaction else True  # no interaction = pass

        overall = fr_passed and ia_passed

        self.logger.info(
            f"  First Render — min: {fr_min:.0f}ms  max: {fr_max:.0f}ms  "
            f"avg: [bold]{fr_avg:.0f}ms[/]  threshold: {fr_threshold:.0f}ms  "
            f"→ [{'green' if fr_passed else 'red'}]{'PASS' if fr_passed else 'FAIL'}[/]"
        )
        if dash.interaction:
            self.logger.info(
                f"  Interaction   — min: {ia_min:.0f}ms  max: {ia_max:.0f}ms  "
                f"avg: [bold]{ia_avg:.0f}ms[/]  threshold: {ia_threshold:.0f}ms  "
                f"→ [{'green' if ia_passed else 'red'}]{'PASS' if ia_passed else 'FAIL'}[/]"
            )

        return PerfDashboardResult(
            label=dash.label,
            url=dash.url,
            passed=overall,
            iterations=iters,
            first_render_min=fr_min,
            first_render_max=fr_max,
            first_render_avg=fr_avg,
            interaction_min=ia_min,
            interaction_max=ia_max,
            interaction_avg=ia_avg,
            first_render_threshold=fr_threshold,
            interaction_threshold=ia_threshold,
            first_render_passed=fr_passed,
            interaction_passed=ia_passed,
            screenshot_path=screenshot_path,
        )

    # ------------------------------------------------------------------
    # Timing helpers
    # ------------------------------------------------------------------

    def _measure_first_render(self, page: Page, url: str, label: str) -> float:
        """Navigate and return milliseconds until Tableau viz is detected."""
        start = time.perf_counter()
        page.goto(url, wait_until="domcontentloaded", timeout=self.config.browser.page_load_timeout)
        self._wait_for_tableau_rendered(page, label)
        end = time.perf_counter()
        return (end - start) * 1000

    def _wait_for_tableau_rendered(self, page: Page, label: str = "") -> None:
        """Wait until a Tableau container element appears in any frame."""
        tag = f"[{label}] " if label else ""
        timeout = 60  # seconds
        start = time.time()

        while time.time() - start < timeout:
            for frame in page.frames:
                for sel in _TABLEAU_SELECTORS:
                    try:
                        if frame.locator(sel).count() > 0:
                            # Found a Tableau container — give a small extra settle time
                            time.sleep(self.config.browser.render_wait_seconds)
                            return
                    except Exception:
                        pass
            time.sleep(0.5)

        # Fallback: wait for networkidle
        self.logger.warning(f"{tag}No Tableau selector found — falling back to networkidle.")
        try:
            page.wait_for_load_state("networkidle", timeout=20_000)
        except Exception:
            pass
        time.sleep(self.config.browser.render_wait_seconds)

    def _measure_interaction(self, page: Page, dash: PerformanceDashboard) -> float:
        """Perform the configured interaction and return time in ms."""
        interaction = dash.interaction
        start = time.perf_counter()

        if interaction.type == "tab_switch":
            nav = TabNavigator(page, self.logger)
            tabs = nav.get_all_tabs()
            target_idx = interaction.tab_index if interaction.tab_index is not None else 1
            if target_idx < len(tabs):
                nav.navigate_to_tab(tabs[target_idx], render_wait=self.config.browser.render_wait_seconds)
            else:
                self.logger.warning(
                    f"    Tab index {target_idx} out of range (only {len(tabs)} tabs found)"
                )
        elif interaction.type == "filter":
            if interaction.filter_name and interaction.filter_value:
                from bi_regression.config_parser import FilterSetting
                fm = FilterManager(page, self.logger)
                fm.apply_scenario(
                    [FilterSetting(name=interaction.filter_name, value=interaction.filter_value)],
                    render_wait=self.config.browser.render_wait_seconds,
                )
            else:
                self.logger.warning("    Filter interaction configured but filter_name/filter_value missing")

        end = time.perf_counter()
        return (end - start) * 1000

    # ------------------------------------------------------------------

    def _log_summary(self, results: List[PerfDashboardResult]):
        passed = sum(1 for r in results if r.passed)
        total = len(results)
        self.logger.info(
            f"[bold]Performance Test Summary:[/] {passed}/{total} dashboard(s) passed."
        )


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _slug(name: str) -> str:
    return re.sub(r"[^\w]+", "_", name).strip("_").lower()[:40]
