# Computron Metadata Validation Guide

## Overview

This guide explains how to use the new **Computron Metadata Validation** feature in the universal validator framework.

## What is Metadata Validation?

**Metadata validation** compares the **structure** of data sources without validating actual data values. This includes:

| Check | Description |
|-------|-------------|
| **Total Columns** | Compares the number of columns in source vs target |
| **Total Records** | Compares the number of rows in source vs target |
| **Column Count** | Validates the target has the same columns as source |
| **Record Count** | Ensures row counts match between source and target |

## Configuration File

**File:** `config/computron_metadata_validation.yaml`

This YAML file contains 10 pre-configured validations comparing:
- **Source:** CSV files from `./raw_data/computron/`
- **Target:** ASIS tables in Redshift (PREPROD environment)
- **Validations:** Column count & record count only

### Key Features

✅ **No column mapping** — Simple, straightforward validation
✅ **No data value comparison** — Only structure validation
✅ **Multiple datasets** — 10 pre-configured validations
✅ **Consolidated reporting** — Single CSV + Single HTML output
✅ **Auto-archiving** — Individual reports moved to `archive/` subfolder

## How to Run

### Option 1: Run all metadata validations

```bash
cd 1IB_universal-validator
source venv/bin/activate

# Run all 10 metadata validations
python3 main.py --config config/computron_metadata_validation.yaml
```

### Option 2: Run using CLI

```bash
python3 cli.py validate --config config/computron_metadata_validation.yaml
```

## Output Files

### Location
```
results/computron_metadata/
├── consolidated_20260611_120000.csv      # ✅ Single CSV with all results
├── consolidated_20260611_120000.html     # ✅ Single HTML with all results
├── consolidated_20260611_120000.xlsx     # Excel with tabs per validation
└── archive/                              # Individual reports moved here
    ├── computron_doo_headers_20260611_120000.csv
    ├── computron_doo_headers_20260611_120000.html
    └── ... (other individual reports)
```

### Consolidated CSV Format

The consolidated CSV contains **all validation results combined** with the following columns:

```
validation_name,validation,result,column,pk,detail,source_value,target_value
Computron DOO Headers,record_count_check,PASS,,,"Source: 1000 rows, Target: 1000 rows",1000,1000
Computron DOO Headers,column_count_check,PASS,,,"Source: 25 columns, Target: 25 columns",25,25
Computron DOO Lines,record_count_check,FAIL,,,"Source: 5000 rows, Target: 4999 rows",5000,4999
...
```

**Key Columns:**
- `validation_name` — Name of the validation run
- `validation` — Type of check (record_count_check, column_count_check, etc.)
- `result` — PASS or FAIL
- `detail` — Human-readable description
- `source_value` — Source value (e.g., row count)
- `target_value` — Target value (e.g., row count)

### Consolidated HTML Report

The consolidated HTML includes:

✅ **Summary Dashboard** — Overall pass/fail counts
✅ **Tabbed Navigation** — One tab per validation
✅ **Status Icons** — ✅ PASS or ❌ FAIL visual indicators
✅ **Metadata Panel** — Source/target info with row & column counts
✅ **QA Sign-off Block** — Copy-pasteable summary for approvals
✅ **Detailed Tables** — Sortable, searchable results
✅ **Charts** — Pass/fail distribution visualizations

## Adding More Validations

To add more Computron validations, edit `config/computron_metadata_validation.yaml`:

```yaml
  - name: "Computron VRM Billing Lines"
    regression: false
    source:
      type: file
      path: ./raw_data/computron/VRM_BILLING_LINE_DETAILS.csv
      format: csv
    target:
      type: table
      environment: PREPROD
      schema: edw_asis
      table: vrm_billing_line_details
    output_dir: ./results/computron_metadata
```

**Template:**
- `name` — Descriptive name for this validation
- `regression: false` — Use basic checks (not regression mode)
- `source.path` — Path to CSV file in `raw_data/computron/`
- `target.table` — Name of ASIS table in Redshift
- `output_dir` — Where to save reports

## Framework Integration

This metadata validation is **fully integrated** into the universal validator framework:

✅ **Same CLI commands** as data validation
✅ **Same report format** (CSV + HTML)
✅ **Same consolidation** (single files for multiple validations)
✅ **Same metadata extraction** (column types, row counts)
✅ **Same archiving** (individual reports auto-moved to archive/)

## What Gets Validated

When you run the metadata validations, the framework checks:

1. **Record Count** — `Source rows == Target rows?`
   - PASS: Counts match
   - FAIL: Counts differ

2. **Column Count** — `Source columns == Target columns?`
   - PASS: Column counts match
   - FAIL: Different number of columns

3. **Metadata Types** — `Source column types compatible with target?`
   - PASS: Types are compatible
   - FAIL: Type mismatch

## Example Output

```
╔════════════════════════════════════════════════════════════════╗
║  VALIDATION: Computron DOO Headers                            ║
║  Source: ./raw_data/computron/DOO_HEADERS_ALL.csv (25 cols)   ║
║  Target: edw_asis.oracle_fusion_dootop_header (25 cols)       ║
║                                                                ║
║  ✅ 2 passed  ·  ❌ 0 failed                                  ║
║                                                                ║
║  📊 CSV Report:  ./results/computron_metadata/.../...csv      ║
║  📊 HTML Report: ./results/computron_metadata/.../...html     ║
╚════════════════════════════════════════════════════════════════╝
```

## Command Line Options

```bash
# Run with target row limit (for quick tests on large tables)
python3 main.py --config config/computron_metadata_validation.yaml --target-limit 1000

# Run with quick PK sampling (faster for large datasets)
python3 main.py --config config/computron_metadata_validation.yaml --quick-sample-pks 100

# Activate debug logging
python3 main.py --config config/computron_metadata_validation.yaml --debug
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| **CSV file not found** | Check path in YAML is correct and file exists in `raw_data/computron/` |
| **Redshift connection failed** | Verify `.env` has valid PREPROD credentials |
| **No output generated** | Check if individual validations completed; see logs for errors |
| **Column count mismatch** | Expected if source/target have different schemas |

## Next Steps

- ✅ Run the validation: `python3 main.py --config config/computron_metadata_validation.yaml`
- 📊 Open `consolidated_*.html` in browser to view interactive report
- 📋 Export `consolidated_*.csv` for further analysis
- 🔄 Use individual archive reports for detailed debugging

---

**Questions?** Check the main [README.md](README.md) for more framework documentation.
