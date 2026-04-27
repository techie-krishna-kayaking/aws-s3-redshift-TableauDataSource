"""
browser_manager.py — Launches Microsoft Edge using your existing user profile
so Okta SSO / Tableau Cloud sessions are already authenticated.

Launch Strategy (automatic, three-stage fallback)
---------------------------------------------------
Stage 1: launch_persistent_context  — works when Edge is fully closed
Stage 2: CDP connect on port 9222   — works if Edge was started with
          --remote-debugging-port=9222 (see start_edge_debug.sh)
Stage 3: Gracefully close Edge via  — kills the running Edge, waits, then
          osascript + retry launch     relaunches from your saved profile
"""
import subprocess
import time
import logging
from playwright.sync_api import sync_playwright, BrowserContext, Page

from bi_regression.config_parser import TestConfig

_CDP_PORT = 9222
_CDP_URL = f"http://localhost:{_CDP_PORT}"


class BrowserManager:
    def __init__(self, config: TestConfig, logger: logging.Logger = None):
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
        self._playwright = None
        self.context: BrowserContext = None
        self._cdp_browser = None

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> "BrowserManager":
        self._start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._stop()

    # ------------------------------------------------------------------
    # Internal lifecycle
    # ------------------------------------------------------------------

    def _start(self):
        bc = self.config.browser
        self.logger.info(
            f"[bold cyan]Starting Edge[/] | profile: {bc.user_data_dir} / {bc.profile_dir}"
        )
        self._playwright = sync_playwright().start()
        self._try_launch_or_connect(bc)
        self.logger.info("[green]Browser ready.[/]")

    def _try_launch_or_connect(self, bc):
        """Three-stage launch strategy — fully automatic, no manual steps."""

        # ── Stage 1: Normal persistent launch ─────────────────────────
        try:
            self.context = self._make_persistent_context(bc)
            self.logger.info("[green]Stage 1: Edge launched via persistent profile.[/]")
            return
        except Exception as e:
            if not ("ProcessSingleton" in str(e) or "profile is already in use" in str(e)):
                raise  # Not a profile-lock issue — re-raise
            self.logger.warning(
                "[yellow]Stage 1: Edge profile is locked (Edge is already running).[/]"
            )

        # ── Stage 2: CDP connect (if Edge has remote debugging enabled) ─
        self.logger.info(f"Stage 2: Trying CDP on {_CDP_URL}…")
        if self._try_cdp_silent(bc):
            self.logger.info(f"[green]Stage 2: Connected to running Edge via CDP.[/]")
            return
        self.logger.warning("Stage 2: CDP not available (Edge not started with --remote-debugging-port).")

        # ── Stage 3: Close Edge + re-launch ────────────────────────────
        self.logger.info(
            "Stage 3: Closing the running Edge instance and relaunching…"
        )
        self._close_edge_gracefully()

        try:
            self.context = self._make_persistent_context(bc)
            self.logger.info(
                "[green]Stage 3: Edge relaunched successfully.[/] "
                "[yellow](Your Okta session is still active from the saved profile.)[/]"
            )
        except Exception as retry_err:
            raise RuntimeError(
                f"Could not launch Edge even after closing it.\n"
                f"Error: {retry_err}\n\n"
                "Please close Edge manually, then run again."
            ) from None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_persistent_context(self, bc) -> BrowserContext:
        return self._playwright.chromium.launch_persistent_context(
            user_data_dir=bc.user_data_dir,
            channel="msedge",
            headless=bc.headless,
            args=[
                f"--profile-directory={bc.profile_dir}",
                "--disable-blink-features=AutomationControlled",
                "--start-maximized",
            ],
            viewport={"width": bc.viewport_width, "height": bc.viewport_height},
        )

    def _try_cdp_silent(self, bc) -> bool:
        """Try CDP without raising — returns True on success."""
        try:
            self._cdp_browser = self._playwright.chromium.connect_over_cdp(_CDP_URL)
            if self._cdp_browser.contexts:
                self.context = self._cdp_browser.contexts[0]
            else:
                self.context = self._cdp_browser.new_context(
                    viewport={"width": bc.viewport_width, "height": bc.viewport_height}
                )
            return True
        except Exception:
            self._cdp_browser = None
            return False

    def _close_edge_gracefully(self):
        """
        Ask macOS to quit Edge via AppleScript, wait for it to exit,
        then double-check with pkill. Preserves your session data.
        """
        self.logger.info("Sending Quit to Microsoft Edge via AppleScript…")
        try:
            subprocess.run(
                ["osascript", "-e", 'quit app "Microsoft Edge"'],
                check=False, timeout=10,
            )
        except Exception as e:
            self.logger.debug(f"osascript quit: {e}")

        # Give Edge up to 8 seconds to close gracefully
        for _ in range(8):
            time.sleep(1)
            result = subprocess.run(
                ["pgrep", "-x", "Microsoft Edge"],
                capture_output=True, text=True
            )
            if result.returncode != 0:
                self.logger.info("Edge closed. Relaunching…")
                return

        # Force-kill if still running
        self.logger.warning("Edge did not close in time — force-killing…")
        subprocess.run(["pkill", "-x", "Microsoft Edge"], check=False)
        time.sleep(2)

    def _stop(self):
        try:
            if self._cdp_browser:
                self._cdp_browser.close()
            elif self.context:
                self.context.close()
            self.logger.info("Browser connection closed.")
        except Exception as e:
            self.logger.debug(f"Error during browser close: {e}")
        try:
            if self._playwright:
                self._playwright.stop()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def new_page(self) -> Page:
        page = self.context.new_page()
        page.set_default_timeout(self.config.browser.page_load_timeout)
        return page

    def navigate_with_retry(self, page: Page, url: str, label: str = "") -> None:
        bc = self.config.browser
        tag = f"[{label}] " if label else ""
        last_exc = None

        for attempt in range(1, bc.max_retries + 1):
            try:
                self.logger.info(
                    f"{tag}Navigating to [cyan]{url}[/] (attempt {attempt}/{bc.max_retries})"
                )
                page.goto(url, wait_until="domcontentloaded", timeout=bc.page_load_timeout)
                self._wait_for_tableau(page, label=tag)
                self.logger.info(f"{tag}[green]Page ready.[/]")
                return
            except Exception as exc:
                last_exc = exc
                self.logger.warning(
                    f"{tag}Attempt {attempt} failed: {exc}. "
                    + ("Retrying…" if attempt < bc.max_retries else "Giving up.")
                )
                if attempt < bc.max_retries:
                    time.sleep(4)

        raise RuntimeError(
            f"{tag}Failed to load '{url}' after {bc.max_retries} attempts. "
            f"Last error: {last_exc}"
        )

    def _wait_for_tableau(self, page: Page, label: str = "") -> None:
        bc = self.config.browser
        tag = label or ""

        TABLEAU_SELECTORS = [
            "tableau-viz",
            "#tableau-viz",
            ".tab-storyboard",
            "[data-tb-test-id='DesktopLayout']",
            ".tabCanvas",
            ".vizContainer",
        ]

        self.logger.debug(f"{tag}Waiting for Tableau to render…")

        self.logger.debug(f"{tag}Waiting for Tableau to render…")

        found = False
        start_time = time.time()
        timeout = 30  # Wait up to 30 seconds
        
        while time.time() - start_time < timeout:
            for frame in page.frames:
                for sel in TABLEAU_SELECTORS:
                    try:
                        if frame.locator(sel).count() > 0:
                            self.logger.debug(f"{tag}Detected Tableau container: '{sel}' in a frame")
                            found = True
                            break
                    except Exception:
                        pass
                if found:
                    break
            if found:
                break
            time.sleep(1)

        if not found:
            self.logger.warning(
                f"{tag}No known Tableau selector found after 30s — falling back to networkidle."
            )
            try:
                page.wait_for_load_state("networkidle", timeout=20_000)
            except Exception:
                pass

        extra = bc.render_wait_seconds
        self.logger.debug(f"{tag}Extra {extra}s render wait…")
        time.sleep(extra)
