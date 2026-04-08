# Multi-Environment Redshift Support

## Overview

The framework now supports managing multiple Redshift environments (DEV, PREPROD, PROD, etc.) with different credentials, making it easy to validate data across environments.

## Setup

### 1. Configure Environments in `.env`

Copy `.env.example` to `.env` and configure your environments:

```bash
cp .env.example .env
```

Edit `.env`:

```bash
# Development Environment
DEV_JDBC_URL=jdbc:redshift://localhost:54391/ib-dl-it
DEV_USER=kkrishna
DEV_PASSWORD=
DEV_SCHEMA=public

# Development - RevOps Test User
DEV_REVOPS_JDBC_URL=jdbc:redshift://localhost:54391/ib-dl-it
DEV_REVOPS_USER=revops_test_qa
DEV_REVOPS_PASSWORD=456
DEV_REVOPS_SCHEMA=public

# Pre-Production Environment
PREPROD_JDBC_URL=jdbc:redshift://localhost:54392/ib-dl-it
PREPROD_USER=kkrishna
PREPROD_PASSWORD=123
PREPROD_SCHEMA=public

# Production Environment
PROD_JDBC_URL=jdbc:redshift://localhost:54391/ib-dl-it
PROD_USER=kkrishna
PROD_PASSWORD=
PROD_SCHEMA=public
```

### 2. Use Environment in Configuration

Simply specify `environment` in your YAML config:

```yaml
validations:
  - name: "DEV Validation"
    source:
      type: file
      path: ./data/source.csv
    target:
      type: table
      environment: DEV  # 👈 Specify environment name
      schema: edw_asis
      table: my_table
    primary_keys: id
```

## Features

### ✅ Multiple Environments

Define as many environments as you need:
- `DEV`, `PREPROD`, `PROD`
- Multiple users per environment: `DEV_REVOPS`, `DEV_ADMIN`
- Custom naming: `QA`, `STAGING`, `DR`

### ✅ JDBC URL Parsing

Automatically parses JDBC URLs:
```
jdbc:redshift://localhost:54391/ib-dl-it
```
Extracts:
- Host: `localhost`
- Port: `54391`
- Database: `ib-dl-it`

### ✅ Environment Validation

Framework validates environment configuration and provides helpful error messages:
```
Error loading environment 'DEV': Missing environment variable: DEV_JDBC_URL
Available environments: ['PREPROD', 'PROD']
```

## Usage Examples

### Example 1: Compare DEV vs PROD

```yaml
- name: "DEV to PROD Comparison"
  source:
    type: table
    environment: DEV
    schema: analytics
    table: metrics
  target:
    type: table
    environment: PROD
    schema: analytics
    table: metrics
  primary_keys: metric_id
```

### Example 2: Validate File Against Specific Environment

```yaml
- name: "CSV to PREPROD"
  source:
    type: file
    path: ./data/upload.csv
  target:
    type: table
    environment: PREPROD
    schema: staging
    table: import_table
  primary_keys: id
```

### Example 3: Different Users on Same Instance

```yaml
- name: "User Permission Check"
  source:
    type: table
    environment: DEV  # kkrishna user
    schema: edw_asis
    table: data
  target:
    type: table
    environment: DEV_REVOPS  # revops_test_qa user
    schema: edw_asis
    table: data
  primary_keys: id
```

## Environment Variable Format

For each environment, define:

```bash
{ENV_NAME}_JDBC_URL=jdbc:redshift://host:port/database
{ENV_NAME}_USER=username
{ENV_NAME}_PASSWORD=password
{ENV_NAME}_SCHEMA=schema_name  # Optional, defaults to 'public'
```

Example:
```bash
QA_JDBC_URL=jdbc:redshift://qa-cluster:5439/qa-db
QA_USER=qa_user
QA_PASSWORD=qa_pass
QA_SCHEMA=qa_schema
```

## Backward Compatibility

Legacy single-environment configuration still works:

```bash
# Old format (still supported)
REDSHIFT_HOST=cluster.redshift.amazonaws.com
REDSHIFT_DB=database
REDSHIFT_USER=user
REDSHIFT_PASSWORD=password
REDSHIFT_PORT=5439
REDSHIFT_SCHEMA=public
```

Use without `environment` in config:
```yaml
target:
  type: table
  schema: public
  table: my_table
  # No environment specified - uses legacy env vars
```

## Advanced: Mixed Configuration

You can mix environment-based and direct configuration:

```yaml
- name: "Mixed Config"
  source:
    type: table
    environment: DEV  # Use environment
    schema: source_schema
    table: source_table
  target:
    type: table
    # Direct configuration
    host: custom-host
    database: custom-db
    user: custom-user
    password: custom-pass
    port: 5439
    schema: target_schema
    table: target_table
  primary_keys: id
```

## Troubleshooting

### Environment Not Found

```
Error loading environment 'DEV': Missing environment variable: DEV_JDBC_URL
Available environments: ['PREPROD', 'PROD']
```

**Solution**: Add the environment to `.env`:
```bash
DEV_JDBC_URL=jdbc:redshift://localhost:54391/ib-dl-it
DEV_USER=your_user
DEV_PASSWORD=your_password
```

### Invalid JDBC URL

```
Error parsing JDBC URL for environment 'DEV': Invalid JDBC URL format
```

**Solution**: Ensure JDBC URL follows format:
```
jdbc:redshift://host:port/database
```

### List Available Environments

The framework automatically shows available environments in error messages, or you can check your `.env` file for all `*_JDBC_URL` variables.

## Benefits

✅ **Centralized Configuration**: All environment credentials in one `.env` file  
✅ **Easy Switching**: Change environment with one word in config  
✅ **Secure**: Passwords in `.env` (gitignored), not in YAML configs  
✅ **Flexible**: Mix environment-based and direct configuration  
✅ **Validated**: Automatic validation with helpful error messages  
✅ **Cross-Environment**: Easy to compare DEV vs PROD, PREPROD vs PROD, etc.

## See Also

- [multi_env_examples.yaml](file:///Users/kkrishna/Library/CloudStorage/OneDrive-InfobloxInc/PycharmProjects/infoblox-DE/1UniversalFramework/universal-validator/config/multi_env_examples.yaml) - Complete examples
- [.env.example](file:///Users/kkrishna/Library/CloudStorage/OneDrive-InfobloxInc/PycharmProjects/infoblox-DE/1UniversalFramework/universal-validator/.env.example) - Environment template
