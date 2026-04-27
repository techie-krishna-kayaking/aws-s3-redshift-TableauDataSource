#!/usr/bin/env python3
"""
run.py — CLI entry point for the Tableau Dashboard Testing Framework.

Usage:
    python -m bi_regression.run                          # uses config.yaml in current dir
    python -m bi_regression.run --config path/to/config.yaml
"""
import argparse
import sys
from pathlib import Path

# Ensure project root is on sys.path when run directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bi_regression.config_parser import load_config
from bi_regression.logger import get_logger
from bi_regression.output_manager import OutputManager
from bi_regression.browser_manager import BrowserManager
from bi_regression.comparison_runner import ComparisonRunner
from bi_regression.smoke_tester import SmokeTester
from bi_regression.reporter import Reporter
from bi_regression.performance_tester import PerformanceTester
from bi_regression.performance_reporter import PerformanceReporter

# Map internal test_type → display label for logs/reports
_TEST_TYPE_LABELS = {
    "smoke": "SMOKE TESTING",
    "comparison": "REGRESSION / COMPARISON TESTING",
    "performance": "PERFORMANCE TESTING",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Tableau Dashboard Testing Framework",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m bi_regression.run                          # smoke test with config.yaml
  python -m bi_regression.run --config config.yaml    # explicit config path
        """,
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to the YAML configuration file (default: config.yaml)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    # ---- Bootstrap logger (no file yet — run dir not created) ----------
    logger = get_logger("main")
    logger.info("[bold cyan]Tableau Dashboard Testing Framework[/]")
    logger.info(f"Config: {args.config}")

    # ---- Load & validate config ----------------------------------------
    try:
        config = load_config(args.config)
        test_label = _TEST_TYPE_LABELS.get(config.test_type, config.test_type.upper())
        logger.info(f"[bold]═══ {test_label} ═══[/]")
    except FileNotFoundError:
        logger.error(f"Config file not found: {args.config}")
        return 1
    except Exception as e:
        logger.error(f"Config error: {e}")
        return 1

    # ---- Create output directory tree ----------------------------------
    output_mgr = OutputManager(config)
    run_dir = output_mgr.create_run_dir()
    logger.info(f"Output directory: [cyan]{run_dir}[/]")

    # Attach file handler now that run_dir exists
    logger = get_logger("main", log_file=output_mgr.log_path())

    results = []
    exit_code = 0

    # ---- Run tests in a single authenticated browser session -----------
    try:
        with BrowserManager(config, logger=logger) as bm:
            if config.test_type == "comparison":
                runner = ComparisonRunner(bm, config, output_mgr, logger)
                results = runner.run()
            elif config.test_type == "smoke":
                tester = SmokeTester(bm, config, output_mgr, logger)
                results = tester.run()
            elif config.test_type == "performance":
                tester = PerformanceTester(bm, config, output_mgr, logger)
                results = tester.run()
            else:
                logger.error(f"Unknown test_type '{config.test_type}'")
                return 1

    except KeyboardInterrupt:
        logger.warning("Run cancelled by user (Ctrl+C).")
        exit_code = 1
    except Exception as exc:
        logger.exception(f"Unexpected error during test run: {exc}")
        exit_code = 1

    # ---- Generate HTML report even on partial runs --------------------
    if results:
        try:
            if config.test_type == "performance":
                reporter = PerformanceReporter(run_dir, config, results)
            else:
                reporter = Reporter(run_dir, config, results)
            report_path = reporter.generate()
            logger.info(f"[bold green]Report saved:[/] {report_path}")
        except Exception as e:
            logger.error(f"Failed to generate report: {e}")

    # ---- Final summary ------------------------------------------------
    if results:
        passed = sum(1 for r in results if getattr(r, "passed", False))
        total  = len(results)
        if passed == total:
            logger.info(f"[bold green]ALL PASSED[/] ({passed}/{total})")
        else:
            logger.warning(f"[bold red]{total - passed} FAILED[/] ({passed}/{total} passed)")
            exit_code = max(exit_code, 1)

    logger.info("[bold]Test run complete.[/]")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
