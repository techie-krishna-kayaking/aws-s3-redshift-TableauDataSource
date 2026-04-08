# Universal Data Validation Framework

A powerful, plugin-based data validation framework that supports multiple data sources with interactive HTML reports and drill-down visualizations.

## 🎯 Features

- **Universal Comparison**: Validate data across 5 different scenarios
  - File ↔ Redshift Table
  - Redshift Table ↔ Table  
  - File ↔ File
  - DataSource (TWBX) ↔ DataSource
  - DataSource ↔ Redshift Table

- **Multiple File Formats**: CSV, JSON, Parquet, Excel
- **Configuration-Driven**: YAML-based configuration for all scenarios
- **Interactive Reports**: HTML reports with Chart.js visualizations and drill-down tables
- **Comprehensive Validation**: Record counts, column counts, duplicates, nulls, empty strings, data values
- **Primary Key Support**: Intelligent comparison with or without primary keys
- **Failure Analysis**: Identifies culprit columns and specific data anomalies
- **Timestamped Results**: Each run creates new files with timestamps - never lose history!

## 🚀 Quick Start

### Step 1: One-Time Setup (5 minutes)

```bash
# Navigate to the project
cd /Users/kkrishna/Library/CloudStorage/OneDrive-InfobloxInc/PycharmProjects/infoblox-DE/1UniversalFramework/universal-validator

# Run setup script (creates virtual environment and installs dependencies)
./setup.sh

# Configure your Redshift environments
cp .env.example .env
# .env is already configured with your DEV, PREPROD, PROD instances!
```

### Step 2: Create Validation Config (2 minutes)

Create `config/my_validation.yaml`:

```yaml
validations:
  - name: "My First Validation"
    source:
      type: file
      path: ./data/source.csv
    target:
      type: table
      environment: DEV  # Uses your DEV Redshift instance
      schema: edw_asis
      table: my_table_name
    primary_keys: id
    output_dir: ./results
```

### Step 3: Run Validation

```bash
# Activate virtual environment
source venv/bin/activate

# Run validation
python main.py --config config/my_validation.yaml
```

### Step 4: View Results

Each run creates timestamped files (e.g., `my_first_validation_20260127_183711.csv`):

```bash
# Open HTML report in browser
open results/my_first_validation_*.html

# Or view CSV report
cat results/my_first_validation_*.csv
```

**What you'll see in the HTML report:**
- 📊 Summary dashboard with pass/fail metrics
- 🥧 Pie charts showing status distribution
- 📊 Bar charts for validation type breakdown
- 📈 Column analysis showing which columns have most failures
- 🔍 Drill-down tables with exact row-level details


## 📊 Configuration Examples

### Scenario 1: File vs Redshift Table

```yaml
- name: "CSV to Redshift"
  source:
    type: file
    path: ./data/source.csv
  target:
    type: table
    schema: edw_asis
    table: my_table
  primary_keys: id
  output_dir: ./results
```

### Scenario 2: Table vs Table

```yaml
- name: "Table Comparison"
  source:
    type: table
    schema: edw_asis
    table: source_table
  target:
    type: table
    schema: edw_tobe
    table: target_table
  primary_keys: customer_id
  output_dir: ./results
```

### Scenario 3: File vs File

```yaml
- name: "CSV to Parquet"
  source:
    type: file
    path: ./data/source.csv
  target:
    type: file
    path: ./data/target.parquet
  primary_keys: id
  output_dir: ./results
```

### Scenario 4: DataSource vs DataSource

```yaml
- name: "TWBX Comparison"
  source:
    type: datasource
    path: ./datasources/pre_rca.twbx
  target:
    type: datasource
    path: ./datasources/post_rca.twbx
  output_dir: ./results
```

### Scenario 5: DataSource vs Table

```yaml
- name: "TWBX to Table"
  source:
    type: datasource
    path: ./datasources/my_data.twbx
  target:
    type: table
    schema: edw_asis
    table: tableau_data
  primary_keys: record_id
  output_dir: ./results
```

## 🔍 Validation Checks

The framework performs the following validations:

1. **Record Count Check**: Compares total row counts
2. **Column Count Check**: Compares column counts and identifies missing columns
3. **Duplicate Check**: Detects duplicate primary keys
4. **Null Check**: Identifies null values in columns
5. **Empty String Check**: Detects empty strings
6. **Data Validation**: Compares actual data values with type coercion

## 📈 Interactive HTML Reports

The HTML reports include:

- **Summary Dashboard**: Pass/fail metrics with visual cards
- **Pie Chart**: Overall status distribution
- **Bar Charts**: Validation type breakdown
- **Column Analysis**: Horizontal bar chart showing top culprit columns
- **Drill-Down Tables**: Sortable, filterable, searchable tables with:
  - Failed checks (with primary key context)
  - Passed checks
  - All results
- **Collapsible Sections**: Clean organization of results

## ⚙️ Environment Variables

Create a `.env` file for Redshift credentials:

```bash
REDSHIFT_HOST=your-cluster.region.redshift.amazonaws.com
REDSHIFT_DB=your-database
REDSHIFT_USER=your-username
REDSHIFT_PASSWORD=your-password
REDSHIFT_PORT=5439
REDSHIFT_SCHEMA=public
```

## 🎨 File Format Support

### CSV
```yaml
source:
  type: file
  path: ./data/file.csv
  encoding: utf-8  # Optional: file encoding (auto-detects common formats if omitted)
```

### JSON
```yaml
source:
  type: file
  path: ./data/file.json
  json_orient: records  # Optional: records, index, columns, values
```

### Parquet
```yaml
source:
  type: file
  path: ./data/file.parquet
```

### Excel
```yaml
source:
  type: file
  path: ./data/file.xlsx
  sheet_name: 0  # Optional: sheet index or name
```

## 🔑 Primary Keys

Primary keys enable intelligent row-matching:

```yaml
# Single primary key
primary_keys: id

# Multiple primary keys (comma-separated)
primary_keys: id,user_id,timestamp

# No primary key (row-by-row comparison)
# primary_keys: (omit or leave empty)
```

## 📂 Relative Paths

All file paths are resolved relative to the project root:

```yaml
source:
  path: ./data/source.csv          # Relative to project root
  path: /absolute/path/to/file.csv # Absolute paths also supported
```

## 🛠️ Extending the Framework

### Adding a New Adapter

1. Create a new adapter class inheriting from `BaseAdapter`
2. Implement required methods: `load()`, `get_metadata()`
3. Register in `core/validator.py`

Example:

```python
from adapters.base_adapter import BaseAdapter

class MyAdapter(BaseAdapter):
    def load(self) -> pd.DataFrame:
        # Load data and return DataFrame
        pass
    
    def get_metadata(self) -> Dict[str, Any]:
        # Return metadata dictionary
        pass
```

## 📝 Output Files

Each validation generates two timestamped files:

- **CSV**: `{validation_name}_{YYYYMMDD_HHMMSS}.csv` - Machine-readable results
- **HTML**: `{validation_name}_{YYYYMMDD_HHMMSS}.html` - Interactive visual report

**Example:**
- `my_validation_20260127_183711.csv`
- `my_validation_20260127_183711.html`

**Benefit:** Each run creates new files, preserving complete history of all validation runs!

## 🐛 Troubleshooting

### File Not Found
- Ensure paths are relative to project root or use absolute paths
- Check file extensions match the format

### Redshift Connection Failed
- Verify `.env` file exists and contains correct credentials
- Check network connectivity and firewall rules

### No Common Columns
- Verify column names match between source and target
- Check for case sensitivity

### Primary Key Not Found
- Ensure primary key columns exist in both source and target
- Check column name spelling

## 📚 Advanced Usage

### Multiple Validations

Run multiple validations in sequence:

```yaml
validations:
  - name: "Validation 1"
    # ... config ...
  
  - name: "Validation 2"
    # ... config ...
  
  - name: "Validation 3"
    # ... config ...
```

### Custom Output Directory

Override output directory per validation:

```yaml
- name: "My Validation"
  # ... source/target config ...
  output_dir: ./custom_results
```

## 🤝 Contributing

This framework is designed to be extensible. To add new features:

1. Add new adapters in `adapters/`
2. Extend validation checks in `core/comparator.py`
3. Enhance reports in `core/reporter.py`

## 📄 License

Internal use only.

## 🙏 Acknowledgments

Built with:
- pandas (data manipulation)
- redshift-connector (Redshift connectivity)
- Chart.js (visualizations)
- DataTables (interactive tables)
