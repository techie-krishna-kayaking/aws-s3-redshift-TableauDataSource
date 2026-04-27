"""
output_manager.py — Creates the timestamped test-run directory tree and manages file paths.

Directory structure produced:
  test_results/
    test_run_YYYYMMDD_HHMMSS/
        smoke/          (or comparison/)
            pass/
            fail/
            diff/
        run.log
"""
from datetime import datetime
from pathlib import Path
from bi_regression.config_parser import TestConfig


class OutputManager:
    def __init__(self, config: TestConfig):
        self.config = config
        self.base_dir = Path(config.output.base_dir)
        self.run_dir: Path = None
        self.mode_dir: Path = None   # run_dir/smoke  OR  run_dir/comparison

    # ------------------------------------------------------------------
    # Directory creation
    # ------------------------------------------------------------------

    def create_run_dir(self) -> Path:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.run_dir = self.base_dir / f"test_run_{ts}"
        mode = self.config.test_type
        self.mode_dir = self.run_dir / mode

        if mode == "performance":
            (self.mode_dir / "screenshots").mkdir(parents=True, exist_ok=True)
        else:
            for sub in ["pass", "fail", "diff"]:
                (self.mode_dir / sub).mkdir(parents=True, exist_ok=True)

        return self.run_dir

    # ------------------------------------------------------------------
    # File-path helpers — callers receive the full Path ready to write
    # ------------------------------------------------------------------

    def _ts(self) -> str:
        return datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # ms precision

    def pass_path(self, label: str = "") -> Path:
        suffix = f"_{label}" if label else ""
        return self.mode_dir / "pass" / f"pass_{self._ts()}{suffix}.png"

    def fail_path(self, label: str = "") -> Path:
        suffix = f"_{label}" if label else ""
        return self.mode_dir / "fail" / f"fail_{self._ts()}{suffix}.png"

    def diff_path(self, label: str = "") -> Path:
        suffix = f"_{label}" if label else ""
        return self.mode_dir / "diff" / f"diff_{self._ts()}{suffix}.png"

    def log_path(self) -> Path:
        return self.run_dir / "run.log"

    def perf_screenshot_path(self, label: str = "") -> Path:
        suffix = f"_{label}" if label else ""
        return self.mode_dir / "screenshots" / f"perf_{self._ts()}{suffix}.png"

    def report_path(self) -> Path:
        return self.run_dir / "report.html"

    def report_path(self) -> Path:
        return self.run_dir / "report.html"
