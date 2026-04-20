<div align="center">

# 🛡️ Universal Data Validation Framework

<p align="center">
  <strong>A powerful, plugin-based data validation engine for comparing data across files, databases, and Tableau datasources — with rich interactive HTML reports.</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.9+">
  <img src="https://img.shields.io/badge/pandas-2.0+-150458?style=for-the-badge&logo=pandas&logoColor=white" alt="Pandas">
  <img src="https://img.shields.io/badge/Amazon_Redshift-8C4FFF?style=for-the-badge&logo=amazonredshift&logoColor=white" alt="Redshift">
  <img src="https://img.shields.io/badge/Tableau-E97627?style=for-the-badge&logo=tableau&logoColor=white" alt="Tableau">
  <img src="https://img.shields.io/badge/Chart.js-FF6384?style=for-the-badge&logo=chartdotjs&logoColor=white" alt="Chart.js">
  <img src="https://img.shields.io/badge/YAML-CB171E?style=for-the-badge&logo=yaml&logoColor=white" alt="YAML">
</p>

<p align="center">
  <a href="#-quick-start">Quick Start</a> •
  <a href="#-features">Features</a> •
  <a href="#-comparison-scenarios">Scenarios</a> •
  <a href="#-tech-stack">Tech Stack</a> •
  <a href="#-configuration-examples">Config</a> •
  <a href="#-multi-environment-support">Multi-Env</a>
</p>

</div>

---

## 📸 What You Get

```
╔══════════════════════════════════════════════════════════════════════╗
║  VALIDATION: CSV to Redshift                                       ║
║  Source: 10,000 rows × 25 columns                                  ║
║  Target:  9,999 rows × 25 columns                                  ║
║                                                                      ║
║  ✅ 44 passed  ·  ❌ 3 failed  ·  ⏭ 0 skipped                      ║
║                                                                      ║
║  📊 CSV Report:  ./results/csv_to_redshift_20260420_184324.csv      ║
║  📊 HTML Report: ./results/csv_to_redshift_20260420_184324.html     ║
╚══════════════════════════════════════════════════════════════════════╝
```

---

## ✨ Features

### 🔄 5 Universal Comparison Scenarios

| Source | | Target | Use Case |
|:---|:---:|:---|:---|
| 📄 **File** (CSV/JSON/Parquet/Excel) | ↔ | 🗄️ **Redshift Table** | ETL pipeline validation |
| 🗄️ **Redshift Table** | ↔ | 🗄️ **Redshift Table** | Cross-schema / cross-env comparison |
| 📄 **File** | ↔ | 📄 **File** | Format migration, data export checks |
| 📊 **Tableau Datasource** (TWBX) | ↔ | 📊 **Tableau Datasource** | Pre/post-RCA comparison |
| 📊 **Tableau Datasource** | ↔ | 🗄️ **Redshift Table** | Dashboard data accuracy |

### 🔍 7 Comprehensive Validation Checks

| # | Check | Description |
|---|:------|:------------|
| 1 | **Record Count** | Compares total row counts between source and target |
| 2 | **Column Count** | Identifies matching, missing, and extra columns |
| 3 | **Metadata Types** | Validates data type compatibility across columns |
| 4 | **Duplicate Detection** | Finds duplicate primary key values with row counts |
| 5 | **Null Analysis** | Detects null/NA values per column with counts |
| 6 | **Empty String Detection** | Identifies empty strings in all columns |
| 7 | **Data Value Comparison** | PK-based record matching or row-by-row comparison with type coercion |

### 📊 Interactive HTML Reports

- **Summary Dashboard** — Pass/fail/skip count cards with status badges
- **Pie Chart** — Overall validation status distribution
- **Bar Charts** — Validation type breakdown (pass/fail per type)
- **Column Analysis** — Horizontal bar chart of top 20 culprit columns
- **Drill-Down Tables** — Sortable, searchable, paginated tables with primary key context
- **Collapsible Sections** — Clean, organized expand/collapse layout
- **Metadata Panel** — Source/target info with row & column counts

### 📦 Consolidated Reporting

When running multiple validations in one config, the framework automatically generates:

- 📗 **Single Excel workbook** — One sheet per validation + summary sheet
- 🌐 **Tabbed HTML report** — Single page with tabs for each validation
- 📁 **Auto-archiving** — Individual reports moved to `archive/` subfolder

### 🧠 Smart Data Handling

- **Auto Sub-setting** — When dataset sizes differ, filters to matching primary keys
- **Type Coercion** — Converts numeric strings to int/float for accurate comparison
- **NaN Equivalence** — Treats `NaN` and `None` as equal
- **Whitespace Normalization** — Strips spaces before comparison
- **Multi-Encoding Support** — Auto-tries UTF-8, UTF-16, ISO-8859-1, CP1252
- **Late-Binding View Support** — Handles Redshift views via `SELECT * LIMIT 0` fallback
- **Result Limiting** — Caps detailed failures at 100 rows to avoid report bloat

### 🌍 Multi-Environment Support

Seamlessly compare data across Redshift environments:

- Define **DEV**, **PREPROD**, **PROD**, and custom environments in a single `.env` file
- Reference by name in YAML config — no hardcoded credentials
- **JDBC URL Parsing** — Automatically extracts host, port, database
- **Backward Compatible** — Legacy `REDSHIFT_HOST`/`REDSHIFT_DB` variables still work
- Validate data migrations across **DEV → PREPROD → PROD** pipelines

### 🗂️ File Format Support

| Format | Extensions | Options |
|:-------|:-----------|:--------|
| **CSV** | `.csv` | `encoding` (auto-detects UTF-8, UTF-16, ISO-8859-1, CP1252) |
| **JSON** | `.json` | `json_orient` (records, index, columns, values) |
| **Parquet** | `.parquet` | — |
| **Excel** | `.xlsx`, `.xls` | `sheet_name` (index or name) |

### ⚡ CLI Interface

```bash
python main.py --config <path>                   # Run all validations
python main.py --config <path> --name "My Test"  # Run specific validation
python main.py --config <path> --debug           # Enable debug logging
```

### 🔑 Primary Key Intelligence

```yaml
primary_keys: id                    # Single key
primary_keys: id,user_id,timestamp  # Composite keys
# Omit for row-by-row positional comparison
```

- Shows **common**, **source-only**, and **target-only** primary keys
- Identifies top culprit columns across all failures
- Displays first 3–5 examples per failure type

### 📝 Timestamped Output — Never Lose History

Every run creates new timestamped files:
```
results/
├── my_validation_20260420_184324.csv    # Machine-readable
├── my_validation_20260420_184324.html   # Interactive visual report
├── consolidated_20260420_184324.html    # Tabbed multi-validation report
├── consolidated_20260420_184324.xlsx    # Excel workbook
└── archive/                            # Auto-archived individual reports
```

---

## 🏗️ Tech Stack

<table>
  <tr>
    <th align="center" colspan="2">Core / Data Processing</th>
  </tr>
  <tr>
    <td align="center" width="120">
      <img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python"><br>
      <sub>3.9+</sub>
    </td>
    <td align="center" width="120">
      <img src="https://img.shields.io/badge/Pandas-150458?style=for-the-badge&logo=pandas&logoColor=white" alt="Pandas"><br>
      <sub>2.0+</sub>
    </td>
  </tr>
  <tr>
    <td align="center" width="120">
      <img src="https://img.shields.io/badge/NumPy-013243?style=for-the-badge&logo=numpy&logoColor=white" alt="NumPy"><br>
      <sub>Data ops</sub>
    </td>
    <td align="center" width="120">
      <img src="https://img.shields.io/badge/PyArrow-EE4C2C?style=for-the-badge&logo=apache&logoColor=white" alt="PyArrow"><br>
      <sub>Parquet I/O</sub>
    </td>
  </tr>
  <tr>
    <th align="center" colspan="2">Database</th>
  </tr>
  <tr>
    <td align="center" width="120">
      <img src="https://img.shields.io/badge/Amazon_Redshift-8C4FFF?style=for-the-badge&logo=amazonredshift&logoColor=white" alt="Redshift"><br>
      <sub>redshift-connector 2.0+</sub>
    </td>
    <td align="center" width="120">
      <img src="https://img.shields.io/badge/AWS-232F3E?style=for-the-badge&logo=amazonaws&logoColor=white" alt="AWS"><br>
      <sub>Cloud data warehouse</sub>
    </td>
  </tr>
  <tr>
    <th align="center" colspan="2">Visualization / Reporting</th>
  </tr>
  <tr>
    <td align="center" width="120">
      <img src="https://img.shields.io/badge/Chart.js-FF6384?style=for-the-badge&logo=chartdotjs&logoColor=white" alt="Chart.js"><br>
      <sub>Pie & bar charts</sub>
    </td>
    <td align="center" width="120">
      <img src="https://img.shields.io/badge/DataTables-336791?style=for-the-badge&logo=jquery&logoColor=white" alt="DataTables"><br>
      <sub>Interactive tables</sub>
    </td>
  </tr>
  <tr>
    <td align="center" width="120">
      <img src="https://img.shields.io/badge/HTML5-E34F26?style=for-the-badge&logo=html5&logoColor=white" alt="HTML5"><br>
      <sub>Report output</sub>
    </td>
    <td align="center" width="120">
      <img src="https://img.shields.io/badge/CSS3-1572B6?style=for-the-badge&logo=css3&logoColor=white" alt="CSS3"><br>
      <sub>Responsive styling</sub>
    </td>
  </tr>
  <tr>
    <th align="center" colspan="2">Data Sources</th>
  </tr>
  <tr>
    <td align="center" width="120">
      <img src="https://img.shields.io/badge/Tableau-E97627?style=for-the-badge&logo=tableau&logoColor=white" alt="Tableau"><br>
      <sub>TWBX extraction</sub>
    </td>
    <td align="center" width="120">
      <img src="https://img.shields.io/badge/Excel-217346?style=for-the-badge&logo=microsoftexcel&logoColor=white" alt="Excel"><br>
      <sub>openpyxl engine</sub>
    </td>
  </tr>
  <tr>
    <th align="center" colspan="2">Configuration / Utilities</th>
  </tr>
  <tr>
    <td align="center" width="120">
      <img src="https://img.shields.io/badge/YAML-CB171E?style=for-the-badge&logo=yaml&logoColor=white" alt="YAML"><br>
      <sub>Config-driven</sub>
    </td>
    <td align="center" width="120">
      <img src="https://img.shields.io/badge/.ENV-ECD53F?style=for-the-badge&logo=dotenv&logoColor=black" alt="dotenv"><br>
      <sub>python-dotenv</sub>
    </td>
  </tr>
</table>

### 📋 Python Dependencies

```
pandas>=2.0.0          # Data manipulation & comparison
redshift-connector>=2.0.0  # Amazon Redshift connectivity
python-dotenv>=1.0.0   # Environment variable management
pyyaml>=6.0            # YAML configuration parsing
openpyxl>=3.1.0        # Excel read/write support
pyarrow>=12.0.0        # Parquet file I/O
```

---

## 🚀 Quick Start

### Step 1: One-Time Setup

```bash
# Clone / navigate to the project
cd universal-validator

# Run setup script (creates venv + installs all dependencies)
./setup.sh

# Configure Redshift environments
cp .env.example .env
# Edit .env with your DEV, PREPROD, PROD credentials
```

### Step 2: Create a Validation Config

Create `config/my_validation.yaml`:

```yaml
validations:
  - name: "My First Validation"
    source:
      type: file
      path: ./data/source.csv
    target:
      type: table
      environment: DEV
      schema: edw_asis
      table: my_table_name
    primary_keys: id
    output_dir: ./results
```

### Step 3: Run

```bash
source venv/bin/activate
python main.py --config config/my_validation.yaml
```

### Step 4: View Results

```bash
open results/my_first_validation_*.html   # Interactive HTML report
cat results/my_first_validation_*.csv     # Machine-readable CSV
```

---

## 📊 Configuration Examples

### Scenario 1: File vs Redshift Table

```yaml
- name: "CSV to Redshift"
  source:
    type: file
    path: ./data/source.csv
  target:
    type: table
    environment: DEV
    schema: edw_asis
    table: my_table
  primary_keys: id
  output_dir: ./results
```

### Scenario 2: Table vs Table (Cross-Environment)

```yaml
- name: "DEV vs PROD Comparison"
  source:
    type: table
    environment: DEV
    schema: edw_asis
    table: source_table
  target:
    type: table
    environment: PROD
    schema: edw_asis
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

### Scenario 4: Tableau DataSource vs DataSource

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

### Scenario 5: Tableau DataSource vs Table

```yaml
- name: "TWBX to Redshift"
  source:
    type: datasource
    path: ./datasources/my_data.twbx
  target:
    type: table
    environment: PREPROD
    schema: edw_asis
    table: tableau_data
  primary_keys: record_id
  output_dir: ./results
```

---

## 🌍 Multi-Environment Support

### `.env` Configuration

```bash
# DEV
DEV_JDBC_URL=jdbc:redshift://dev-cluster.region.redshift.amazonaws.com:5439/dev_db
DEV_USER=dev_user
DEV_PASSWORD=dev_password
DEV_SCHEMA=edw_asis

# PREPROD
PREPROD_JDBC_URL=jdbc:redshift://preprod-cluster.region.redshift.amazonaws.com:5439/preprod_db
PREPROD_USER=preprod_user
PREPROD_PASSWORD=preprod_password

# PROD
PROD_JDBC_URL=jdbc:redshift://prod-cluster.region.redshift.amazonaws.com:5439/prod_db
PROD_USER=prod_user
PROD_PASSWORD=prod_password
```

### Usage in YAML

```yaml
source:
  type: table
  environment: DEV        # Just reference by name!
  schema: edw_asis
  table: my_table
```

> **Tip:** Legacy `REDSHIFT_HOST` / `REDSHIFT_DB` variables are still supported for backward compatibility.

📖 See [Multi-Environment Guide](docs/MULTI_ENVIRONMENT.md) for full details.

---

## 🏛️ Architecture

```
universal-validator/
│
├── main.py                    # CLI entry point
│
├── core/                      # 🧠 Core engine
│   ├── validator.py           #    Orchestrates the full validation workflow
│   ├── comparator.py          #    7 validation check implementations
│   └── reporter.py            #    CSV, HTML, consolidated report generation
│
├── adapters/                  # 🔌 Plugin-based data source adapters
│   ├── base_adapter.py        #    Abstract base class (load, get_metadata)
│   ├── file_adapter.py        #    CSV, JSON, Parquet, Excel support
│   ├── table_adapter.py       #    Redshift with multi-env support
│   └── datasource_adapter.py  #    Tableau TWBX extraction & XML parsing
│
├── utils/                     # 🛠️ Utilities
│   ├── helpers.py             #    Type coercion, comparison, formatting
│   ├── env_config.py          #    Environment parsing, JDBC URL parsing
│   └── html_template.py       #    Chart.js + DataTables HTML template
│
├── config/                    # ⚙️ YAML validation configurations
│   ├── example_validations.yaml
│   └── multi_env_examples.yaml
│
├── results/                   # 📊 Output reports (timestamped, auto-archived)
│
└── docs/                      # 📖 Documentation
    ├── MULTI_ENVIRONMENT.md
    └── MULTI_ENV_QUICKSTART.md
```

---

## 🛠️ Extending the Framework

### Adding a New Adapter

1. Inherit from `BaseAdapter`
2. Implement `load()` → returns `pd.DataFrame`
3. Implement `get_metadata()` → returns `Dict[str, Any]`
4. Register in `core/validator.py`

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

---

## 🐛 Troubleshooting

| Problem | Solution |
|:--------|:---------|
| **File Not Found** | Use relative paths from project root, or absolute paths |
| **Redshift Connection Failed** | Verify `.env` credentials, check network/firewall rules |
| **No Common Columns** | Check column name spelling and case sensitivity |
| **Primary Key Not Found** | Ensure PK columns exist in both source and target |
| **Encoding Errors** | Framework auto-tries 4 encodings; specify `encoding` in config if needed |

---

## 📄 License

Internal use only.

---

<div align="center">

**Built with ❤️ for Data Engineering**

<p>
  <img src="https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Pandas-150458?style=flat-square&logo=pandas&logoColor=white" alt="Pandas">
  <img src="https://img.shields.io/badge/Redshift-8C4FFF?style=flat-square&logo=amazonredshift&logoColor=white" alt="Redshift">
  <img src="https://img.shields.io/badge/Tableau-E97627?style=flat-square&logo=tableau&logoColor=white" alt="Tableau">
  <img src="https://img.shields.io/badge/Chart.js-FF6384?style=flat-square&logo=chartdotjs&logoColor=white" alt="Chart.js">
  <img src="https://img.shields.io/badge/YAML-CB171E?style=flat-square&logo=yaml&logoColor=white" alt="YAML">
</p>

</div>
