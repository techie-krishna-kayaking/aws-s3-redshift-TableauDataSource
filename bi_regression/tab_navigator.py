"""
tab_navigator.py — Detects and iterates through all Tableau dashboard tabs/pages.

Tableau Cloud uses several different DOM patterns for tab navigation depending
on the version. This module tries a prioritised list of selectors and falls back
gracefully to "single-page" mode if no navigation bar is found.
"""
import time
import logging
from dataclasses import dataclass, field
from typing import List, Optional

from playwright.sync_api import Page


@dataclass
class TabInfo:
    name: str           # Display name as shown in the tab bar
    index: int          # 0-based position
    exists: bool = True # Set to False for "missing" entries in mismatch reporting
    reason: str = ""    # Populated when exists=False (e.g. "Missing in Pre-Production")


# Ordered from most-specific to most-generic. Add new patterns here.
_TAB_SELECTORS = [
    # Tableau Cloud / Tableau Server 2022+
    "[data-tb-test-id='tab-sheet-nav-item']",
    "[data-tb-test-id='DesktopTabNav'] li",
    # Older Tableau Server
    ".tabStoryNav .tab",
    ".tab-navItem",
    ".tab-strip .tab",
    # Generic fallback
    "ul.tab-strip li",
    ".tabNavigation li",
]


class TabNavigator:
    """
    Discovers all tabs from a loaded Tableau dashboard page and
    provides a click-and-wait helper to navigate between them.
    """

    def __init__(self, page: Page, logger: logging.Logger = None):
        self.page = page
        self.logger = logger or logging.getLogger(__name__)

    # ------------------------------------------------------------------

    def get_all_tabs(self) -> List[TabInfo]:
        """
        Return all visible tabs. If none are detected returns a single
        synthetic TabInfo representing the whole page.
        """
        for selector in _TAB_SELECTORS:
            try:
                elements = self.page.query_selector_all(selector)
                if not elements:
                    continue
                tabs = []
                for i, el in enumerate(elements):
                    name = (el.inner_text() or "").strip()
                    if not name:
                        name = f"Tab_{i + 1}"
                    tabs.append(TabInfo(name=name, index=i))
                self.logger.info(
                    f"Detected [bold]{len(tabs)}[/] tab(s) using selector '{selector}': "
                    + ", ".join(f"'{t.name}'" for t in tabs)
                )
                return tabs
            except Exception as exc:
                self.logger.debug(f"Selector '{selector}' failed: {exc}")
                continue

        self.logger.warning(
            "No Tableau tab navigation detected — treating dashboard as single-page."
        )
        return [TabInfo(name="Main", index=0)]

    # ------------------------------------------------------------------

    def navigate_to_tab(self, tab: TabInfo, render_wait: int = 5) -> bool:
        """
        Click the tab at *tab.index* and wait for the content to load.
        Returns True on success, False if the tab element could not be found.
        """
        if tab.index == 0:
            # First tab may already be active; still click to be safe
            pass

        for selector in _TAB_SELECTORS:
            try:
                elements = self.page.query_selector_all(selector)
                if elements and tab.index < len(elements):
                    self.logger.info(f"Navigating to tab: [cyan]'{tab.name}'[/]")
                    elements[tab.index].click()
                    # Wait for idle network + extra render time
                    try:
                        self.page.wait_for_load_state("networkidle", timeout=15_000)
                    except Exception:
                        pass
                    time.sleep(render_wait)
                    self.logger.debug(f"Tab '{tab.name}' loaded.")
                    return True
            except Exception as exc:
                self.logger.debug(f"Tab click via '{selector}' failed: {exc}")
                continue

        self.logger.warning(f"Could not navigate to tab '{tab.name}' (index {tab.index}).")
        return False

    # ------------------------------------------------------------------

    @staticmethod
    def align_tabs(
        tabs_a: List[TabInfo],
        tabs_b: List[TabInfo],
        label_a: str = "Dashboard 1",
        label_b: str = "Dashboard 2",
    ) -> List[tuple]:
        """
        Match tabs from two dashboards by name (case-insensitive).

        Returns a list of (tab_a, tab_b) tuples where:
          - Both are TabInfo  →  matched pair (test both)
          - tab_b is None     →  tab exists in A but not B  (FAIL)
          - tab_a is None     →  tab exists in B but not A  (FAIL)
        """
        map_a = {t.name.lower(): t for t in tabs_a}
        map_b = {t.name.lower(): t for t in tabs_b}

        all_names = sorted(set(map_a) | set(map_b))
        pairs = []
        for name in all_names:
            a = map_a.get(name)
            b = map_b.get(name)
            if a is None:
                # Present in B only
                missing = TabInfo(name=map_b[name].name, index=-1, exists=False,
                                  reason=f"Missing in {label_a}")
                pairs.append((missing, map_b[name]))
            elif b is None:
                # Present in A only
                missing = TabInfo(name=map_a[name].name, index=-1, exists=False,
                                  reason=f"Missing in {label_b}")
                pairs.append((map_a[name], missing))
            else:
                pairs.append((a, b))
        return pairs
