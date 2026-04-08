# 🎉 Universal Data Validation Framework - Quick Start Guide

## What You Got

A complete, production-ready data validation framework with:

✅ **5 Comparison Scenarios**
- File ↔ Redshift Table
- Table ↔ Table
- File ↔ File
- DataSource (TWBX) ↔ DataSource
- DataSource ↔ Table

✅ **4 File Formats**: CSV, JSON, Parquet, Excel

✅ **Interactive HTML Reports** with drill-down visualizations

✅ **Configuration-Driven** - No code changes needed

---

## 🚀 Get Started in 3 Steps

### Step 1: Setup (One-time)

```bash
cd universal-validator
./setup.sh
```

This will:
- Create virtual environment
- Install all dependencies (pandas, redshift-connector, pyyaml, etc.)

### Step 2: Configure (if using Redshift)

```bash
cp .env.example .env
# Edit .env with your Redshift credentials
```

### Step 3: Run Your First Validation

```bash
# Test with sample data (no Redshift needed)
source venv/bin/activate
python main.py --config config/test_validation.yaml

# View the HTML report
open results/sample_csv_validation_test.html
```

---

## 📝 Create Your Own Validation

### Example: CSV to Redshift

Create `config/my_validation.yaml`:

```yaml
validations:
  - name: "My CSV to Redshift Validation"
    source:
      type: file
      path: ./data/my_source.csv
    target:
      type: table
      schema: edw_asis
      table: my_table_name
    primary_keys: id,user_id
    output_dir: ./results
```

Run it:

```bash
python main.py --config config/my_validation.yaml
```

---

## 📊 What You'll Get

### CSV Report
`results/my_csv_to_redshift_validation.csv`
- Machine-readable
- All validation results
- Perfect for CI/CD pipelines

### HTML Report
`results/my_csv_to_redshift_validation.html`
- Interactive visualizations
- Drill-down tables
- Column-level failure analysis
- Identifies culprit columns

---

## 🎯 Common Use Cases

### 1. Validate ETL Pipeline

```yaml
- name: "ETL Validation"
  source:
    type: file
    path: ./staging/extract.csv
  target:
    type: table
    schema: production
    table: final_table
  primary_keys: transaction_id
```

### 2. Compare Tables Across Schemas

```yaml
- name: "Schema Migration Check"
  source:
    type: table
    schema: old_schema
    table: customers
  target:
    type: table
    schema: new_schema
    table: customers
  primary_keys: customer_id
```

### 3. Validate Tableau Datasource

```yaml
- name: "Tableau Data Validation"
  source:
    type: datasource
    path: ./tableau/my_report.twbx
  target:
    type: table
    schema: analytics
    table: report_data
  primary_keys: record_id
```

---

## 🔍 Understanding Results

### HTML Report Sections

1. **Summary Cards**: Quick pass/fail overview
2. **Pie Chart**: Status distribution
3. **Bar Charts**: Validation type breakdown
4. **Column Analysis**: Top culprit columns (shows which columns have most failures)
5. **Failed Checks Table**: Drill-down with primary key context
6. **Passed Checks Table**: Successful validations
7. **All Results Table**: Complete log

### Validation Checks Performed

- ✅ Record count comparison
- ✅ Column count comparison
- ✅ Duplicate detection
- ✅ Null value analysis
- ✅ Empty string detection
- ✅ Data value comparison (with type coercion)

---

## 💡 Pro Tips

### Tip 1: Use Primary Keys
```yaml
primary_keys: id,user_id  # Enables intelligent row matching
```

### Tip 2: Relative Paths
```yaml
path: ./data/file.csv  # Relative to project root
```

### Tip 3: Multiple Validations
```yaml
validations:
  - name: "Validation 1"
    # ...
  - name: "Validation 2"
    # ...
```

Run specific validation:
```bash
python main.py --config config/validations.yaml --name "Validation 1"
```

### Tip 4: Debug Mode
```bash
python main.py --config config/validations.yaml --debug
```

---

## 📁 Project Structure

```
universal-validator/
├── adapters/          # Data source plugins
├── core/             # Validation engine
├── utils/            # Helper functions
├── config/           # Your YAML configs
├── results/          # Generated reports
├── tests/data/       # Sample test data
├── main.py          # Run this!
├── setup.sh         # Setup script
└── README.md        # Full documentation
```

---

## 🆘 Troubleshooting

### "Module not found"
```bash
source venv/bin/activate  # Activate virtual environment
```

### "File not found"
- Check path is relative to project root
- Use absolute path if needed: `/full/path/to/file.csv`

### "Redshift connection failed"
- Verify `.env` file exists
- Check credentials are correct
- Test network connectivity

### "No common columns"
- Verify column names match
- Check for case sensitivity

---

## 📚 Full Documentation

- **README.md**: Complete documentation
- **config/example_validations.yaml**: All 5 scenarios with examples
- **Walkthrough**: See artifact for implementation details

---

## 🎊 You're Ready!

The framework is production-ready and handles all your validation scenarios. Just:

1. Run `./setup.sh` (one time)
2. Create your YAML config
3. Run `python main.py --config your_config.yaml`
4. Open the HTML report

**Happy Validating! 🚀**
