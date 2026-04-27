"""
comparison_runner.py — Orchestrates full two-dashboard comparison.

Flow
----
1. Open dashboard_url_1 in Page A, detect all tabs.
2. Open dashboard_url_2 in Page B, detect all tabs.
3. Align tabs by name: matched → compare, unmatched → FAIL with reason.
4. For each matched pair: screenshot both, SSIM diff, save composite.
5. Return list of DiffResult objects for the reporter.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import List

from bi_regression.config_parser import TestConfig
from bi_regression.browser_manager import BrowserManager
from bi_regression.tab_navigator import TabNavigator, TabInfo
from bi_regression.visual_diff import DiffResult, compare_images, create_missing_tab_image
from bi_regression.output_manager import OutputManager
from bi_regression.filter_manager import FilterManager


class ComparisonRunner:
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
        self.cfg = config.comparison

    # ------------------------------------------------------------------

    def run(self) -> List[DiffResult]:
        """Execute the full comparison and return results."""
        cfg_list = self.cfg if isinstance(self.cfg, list) else [self.cfg]
        all_results: List[DiffResult] = []

        for cfg in cfg_list:
            url_a = cfg.dashboard_url_1
            url_b = cfg.dashboard_url_2
            label_a = cfg.label_1
            label_b = cfg.label_2
            threshold = cfg.ssim_threshold

            self.logger.info(
                "[bold yellow]╔══════════════════════════════════════════════╗[/]"
            )
            self.logger.info(
                "[bold yellow]║   REGRESSION / COMPARISON TESTING            ║[/]"
            )
            self.logger.info(
                "[bold yellow]╚══════════════════════════════════════════════╝[/]"
            )
            self.logger.info(f"  {label_a}: {url_a}")
            self.logger.info(f"  {label_b}: {url_b}")

            # Open two tabs in the same authenticated session
            # NOTE: create each page right before navigating — creating both
            # upfront can cause the second page to be invalidated by Tableau's
            # SPA lifecycle when connected via CDP.
            page_a = self.bm.new_page()
            self.bm.navigate_with_retry(page_a, url_a, label=label_a)

            page_b = self.bm.new_page()
            self.bm.navigate_with_retry(page_b, url_b, label=label_b)

            # Discover tabs
            nav_a = TabNavigator(page_a, self.logger)
            nav_b = TabNavigator(page_b, self.logger)
            tabs_a = nav_a.get_all_tabs()
            tabs_b = nav_b.get_all_tabs()

            # Align by name
            pairs = TabNavigator.align_tabs(tabs_a, tabs_b, label_a, label_b)
            self.logger.info(
                f"Tab alignment: {len(pairs)} pair(s) — "
                + f"{sum(1 for a,b in pairs if a.exists and b.exists)} matched, "
                + f"{sum(1 for a,b in pairs if not a.exists or not b.exists)} missing."
            )

            # ----- Determine scenarios to run ---------------------------
            scenarios = cfg.filter_scenarios or []

            if not scenarios:
                # No filter scenarios — run once with current filter state
                results = self._compare_all_tabs(
                    page_a, page_b, pairs, nav_a, nav_b,
                    label_a, label_b, threshold,
                    scenario_label="",
                )
                all_results.extend(results)
            else:
                for scenario in scenarios:
                    self.logger.info(
                        f"[bold magenta]Filter scenario:[/] '{scenario.label}' "
                        f"({len(scenario.filters)} filter(s))"
                    )

                    # Apply identical filters to BOTH dashboards
                    fm_a = FilterManager(page_a, self.logger)
                    fm_b = FilterManager(page_b, self.logger)

                    render_wait = self.config.browser.render_wait_seconds

                    self.logger.info(f"  Applying filters to {label_a}…")
                    applied_a = fm_a.apply_scenario(scenario.filters, render_wait)

                    self.logger.info(f"  Applying filters to {label_b}…")
                    applied_b = fm_b.apply_scenario(scenario.filters, render_wait)

                    self.logger.info(
                        f"  Filters applied: {applied_a}/{len(scenario.filters)} on {label_a}, "
                        f"{applied_b}/{len(scenario.filters)} on {label_b}"
                    )

                    results = self._compare_all_tabs(
                        page_a, page_b, pairs, nav_a, nav_b,
                        label_a, label_b, threshold,
                        scenario_label=scenario.label,
                    )
                    all_results.extend(results)

            page_a.close()
            page_b.close()

        self._log_summary(all_results)
        return all_results

    # ------------------------------------------------------------------

    def _compare_all_tabs(
        self,
        page_a, page_b,
        pairs, nav_a, nav_b,
        label_a, label_b,
        threshold,
        scenario_label: str = "",
    ) -> List[DiffResult]:
        """Compare every tab pair and return results."""
        results: List[DiffResult] = []
        for tab_a, tab_b in pairs:
            result = self._compare_tab_pair(
                page_a, page_b,
                tab_a, tab_b,
                nav_a, nav_b,
                label_a, label_b,
                threshold,
                scenario_label=scenario_label,
            )
            results.append(result)
        return results

    # ------------------------------------------------------------------

    def _compare_tab_pair(
        self,
        page_a, page_b,
        tab_a: TabInfo, tab_b: TabInfo,
        nav_a: TabNavigator, nav_b: TabNavigator,
        label_a: str, label_b: str,
        threshold: float,
        scenario_label: str = "",
    ) -> DiffResult:

        tab_name = tab_a.name if tab_a.exists else tab_b.name
        display_name = f"{tab_name} [{scenario_label}]" if scenario_label else tab_name

        # ---- Handle missing tab ----------------------------------------
        if not tab_a.exists or not tab_b.exists:
            reason = tab_a.reason if not tab_a.exists else tab_b.reason
            self.logger.warning(
                f"  [yellow]MISSING TAB[/] '{tab_name}': {reason}"
            )
            placeholder = str(self.output.fail_path(f"missing_{_slug(display_name)}"))
            create_missing_tab_image(tab_name, reason, placeholder)
            return DiffResult(
                tab_name=tab_name,
                passed=False,
                ssim_score=0.0,
                baseline_path=placeholder if not tab_a.exists else "",
                target_path=placeholder if not tab_b.exists else "",
                diff_path=placeholder,
                label_a=label_a,
                label_b=label_b,
                scenario_label=scenario_label,
            )

        self.logger.info(f"  Comparing tab: [cyan]'{display_name}'[/]")

        # ---- Navigate both pages to their respective tab ---------------
        if tab_a.index > 0:
            nav_a.navigate_to_tab(tab_a, render_wait=self.config.browser.render_wait_seconds)
        if tab_b.index > 0:
            nav_b.navigate_to_tab(tab_b, render_wait=self.config.browser.render_wait_seconds)

        # ---- Screenshot both pages -------------------------------------
        slug = _slug(display_name)
        ss_a_path = str(self.output.pass_path(f"{label_a}_{slug}"))
        ss_b_path = str(self.output.pass_path(f"{label_b}_{slug}"))

        try:
            page_a.screenshot(path=ss_a_path, full_page=True)
            self.logger.debug(f"  Screenshot saved: {ss_a_path}")
        except Exception as e:
            self.logger.error(f"  Screenshot failed for {label_a}/'{tab_name}': {e}")
            return DiffResult(
                tab_name=tab_name, passed=False, ssim_score=0.0,
                baseline_path="", target_path="", diff_path="",
                label_a=label_a, label_b=label_b,
                scenario_label=scenario_label,
            )

        try:
            page_b.screenshot(path=ss_b_path, full_page=True)
            self.logger.debug(f"  Screenshot saved: {ss_b_path}")
        except Exception as e:
            self.logger.error(f"  Screenshot failed for {label_b}/'{tab_name}': {e}")
            return DiffResult(
                tab_name=tab_name, passed=False, ssim_score=0.0,
                baseline_path=ss_a_path, target_path="", diff_path="",
                label_a=label_a, label_b=label_b,
                scenario_label=scenario_label,
            )

        # ---- Visual diff -----------------------------------------------
        diff_p = str(self.output.diff_path(slug))
        result = compare_images(
            baseline_path=ss_a_path,
            target_path=ss_b_path,
            diff_output_path=diff_p,
            threshold=threshold,
            tab_name=tab_name,
            label_a=label_a,
            label_b=label_b,
        )
        result.scenario_label = scenario_label

        # Move individual screenshots to pass/ or fail/ bucket
        if result.passed:
            self.logger.info(
                f"  [green]PASS[/] '{tab_name}' — SSIM: {result.ssim_score:.4f}"
            )
        else:
            # Rename screenshots from pass/ to fail/
            ss_a_fail = str(self.output.fail_path(f"{label_a}_{slug}"))
            ss_b_fail = str(self.output.fail_path(f"{label_b}_{slug}"))
            _safe_rename(ss_a_path, ss_a_fail)
            _safe_rename(ss_b_path, ss_b_fail)
            result.baseline_path = ss_a_fail
            result.target_path   = ss_b_fail
            self.logger.warning(
                f"  [red]FAIL[/] '{tab_name}' — SSIM: {result.ssim_score:.4f} "
                f"(threshold: {threshold}) | Diff pixels: {result.diff_pixel_count}"
            )

        return result

    # ------------------------------------------------------------------

    def _log_summary(self, results: List[DiffResult]):
        passed = sum(1 for r in results if r.passed)
        total  = len(results)
        self.logger.info(
            f"[bold]REGRESSION / COMPARISON TESTING Summary:[/] {passed}/{total} tabs passed."
        )


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _slug(name: str) -> str:
    return re.sub(r"[^\w]+", "_", name).strip("_").lower()[:40]


def _safe_rename(src: str, dst: str):
    try:
        Path(src).rename(dst)
    except Exception:
        pass
