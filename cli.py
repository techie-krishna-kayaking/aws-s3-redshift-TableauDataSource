#!/usr/bin/env python3
"""
BI Universal QA Tool — Unified CLI

Combines two tools into one:
  1. regression  — Tableau Dashboard Testing (smoke, comparison, performance)
  2. validate    — Universal Data Validation (file/table/datasource comparison)

Usage:
    python cli.py regression --config bi_regression/configs/config.yaml
    python cli.py validate   --config config/my_validation.yaml
    python cli.py validate   --config config/my_validation.yaml --name "CSV to Redshift"
"""
import sys
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))


def print_usage():
    print("""
BI Universal QA Tool
====================

Usage:
    python cli.py <command> [options]

Commands:
    regression    Tableau Dashboard Testing (smoke / comparison / performance)
    validate      Universal Data Validation (file / table / datasource comparison)

Examples:
    python cli.py regression --config bi_regression/configs/config.yaml
    python cli.py validate   --config config/my_validation.yaml
    python cli.py validate   --config config/my_validation.yaml --name "CSV to Redshift"

For help on a specific command:
    python cli.py regression --help
    python cli.py validate   --help
""")


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print_usage()
        sys.exit(0)

    command = sys.argv[1]
    # Remove the subcommand so downstream parsers see their own args
    sys.argv = [sys.argv[0]] + sys.argv[2:]

    if command == "regression":
        from bi_regression.run import main as regression_main
        sys.exit(regression_main())

    elif command == "validate":
        from main import main as validate_main
        validate_main()  # main.py calls sys.exit() internally

    else:
        print(f"Unknown command: '{command}'")
        print_usage()
        sys.exit(1)


if __name__ == "__main__":
    main()
