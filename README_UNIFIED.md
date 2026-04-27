# BI Universal QA Tool

A unified quality assurance toolkit combining **two complementary testing tools** for BI/data engineering workflows:

| Tool | Command | What It Does |
|---|---|---|
| **Data Validation** | `cli.py validate` | Compares data across files, Redshift tables, and Tableau datasources |
| **Tableau Regression** | `cli.py regression` | Smoke, visual comparison, and performance testing of Tableau dashboards |

---

## Quick Start

```bash
# 1. Setup
./setup.sh            # creates venv, installs all dependencies

# 2. Activate
source venv/bin/activate
```

### Data Validation
```bash
python cli.py validate --config config/my_validation.yaml
python cli.py validate --config config/my_validation.yaml --name "CSV to Redshift"
python cli.py validate --config config/my_validation.yaml --debug
```

### Tableau Regression Testing
```bash
python cli.py regression --config bi_regression/configs/config.yaml
```

### Direct Entry Points (also still work)
```bash
python main.py --config config/my_validation.yaml           # data validation
python -m bi_regression.run --config bi_regression/configs/config.yaml  # regression
```

---

## Project Structure

```
.
├── cli.py                      # Unified CLI entry point
├── main.py                     # Data validation entry point (original)
├── requirements.txt            # Merged dependencies
├── setup.sh                    # Quick start setup script
│
├── adapters/                   # Data source adapters (file, table, datasource)
├── core/                       # Validation engine (comparator, reporter, validator)
├── utils/                      # Helpers, env config, HTML templates
├── config/                     # Validation YAML configs
│
├── bi_regression/              # Tableau Dashboard Testing Framework
│   ├── run.py                  # Regression CLI entry point
│   ├── browser_manager.py      # Edge browser lifecycle (Playwright)
│   ├── comparison_runner.py    # SSIM-based visual diff
│   ├── config_parser.py        # Pydantic config models
│   ├── filter_manager.py       # Tableau filter interaction
│   ├── logger.py               # Rich console logging
│   ├── output_manager.py       # Timestamped output directories
│   ├── performance_reporter.py # Performance HTML reports
│   ├── performance_tester.py   # Render/interaction timing
│   ├── reporter.py             # Smoke/comparison HTML reports
│   ├── smoke_tester.py         # UI standards validation
│   ├── tab_navigator.py        # Tableau tab detection
│   ├── visual_diff.py          # SSIM image comparison
│   └── configs/                # Regression YAML configs
│
├── scripts/                    # Helper scripts
│   ├── start_edge_debug.sh     # Launch Edge with remote debugging
│   └── inspect_dom.py          # Tableau DOM inspector utility
│
├── raw_data/                   # Source data files
├── results/                    # Output reports
└── docs/                       # Additional documentation
```

---

## Tool 1: Data Validation (`validate`)

Compares data across **5 scenarios** with **7 validation checks** and rich HTML reports.

**Scenarios:** File ↔ Table, Table ↔ Table, File ↔ File, TWBX ↔ TWBX, TWBX ↔ Table

**Checks:** Record count, column count, metadata types, duplicates, nulls, empty strings, data values

**Reports:** Interactive HTML with Chart.js, drill-down DataTables, consolidated Excel workbooks

See [docs/MULTI_ENVIRONMENT.md](docs/MULTI_ENVIRONMENT.md) for multi-environment Redshift setup.

---

## Tool 2: Tableau Regression (`regression`)

Three test modes for Tableau Cloud dashboards using Playwright + Edge.

| Mode | Config Key | What It Does |
|---|---|---|
| **Smoke** | `smoke:` | Validates fonts, colors, sizes against brand standards |
| **Comparison** | `comparison:` | SSIM pixel diff between two dashboard environments |
| **Performance** | `performance:` | Measures render & interaction timing across N iterations |

See [bi_regression/configs/exampleConfig.yaml](bi_regression/configs/exampleConfig.yaml) for config examples.

---

## Dependencies

All dependencies are in a single `requirements.txt`. Key libraries:

| Data Validation | Tableau Regression |
|---|---|
| pandas, pyarrow | playwright |
| redshift-connector | opencv-python, scikit-image |
| openpyxl | pydantic, jinja2 |
| python-dotenv | Pillow, numpy, rich |
| pyyaml | pyyaml |
