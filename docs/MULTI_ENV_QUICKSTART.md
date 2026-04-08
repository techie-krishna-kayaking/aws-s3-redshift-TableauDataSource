# 🌍 Multi-Environment Quick Start

## What's New?

You can now easily manage multiple Redshift environments (DEV, PREPROD, PROD) with different credentials!

## Setup (2 Minutes)

### Step 1: Copy Your Environment Info

You already have this data:
```
env         jdbc_url                                    user            password
dev         jdbc:redshift://localhost:54391/ib-dl-it   kkrishna        
preprod     jdbc:redshift://localhost:54392/ib-dl-it   kkrishna        123
prod        jdbc:redshift://localhost:54393/ib-dl-it   kkrishna        
dev         jdbc:redshift://localhost:54391/ib-dl-it   revops_test_qa  456
```

### Step 2: Create `.env` File

```bash
cd universal-validator
cp .env.example .env
```

The `.env.example` already has your environments configured! Just copy it.

### Step 3: Use in Your Validations

```yaml
validations:
  - name: "My Validation"
    source:
      type: file
      path: ./data/source.csv
    target:
      type: table
      environment: DEV  # 👈 Just specify the environment!
      schema: edw_asis
      table: my_table
    primary_keys: id
```

## Available Environments

After copying `.env.example` to `.env`, you have:

- **DEV** - Development (kkrishna user)
- **DEV_REVOPS** - Development (revops_test_qa user)
- **PREPROD** - Pre-production
- **PROD** - Production

## Common Use Cases

### 1. Validate DEV vs PROD

```yaml
- name: "DEV to PROD Check"
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
  primary_keys: id
```

### 2. Upload File to Specific Environment

```yaml
- name: "Upload to PREPROD"
  source:
    type: file
    path: ./data/upload.csv
  target:
    type: table
    environment: PREPROD
    schema: staging
    table: import_data
  primary_keys: id
```

### 3. Compare Different Users

```yaml
- name: "User Access Check"
  source:
    type: table
    environment: DEV  # kkrishna
    schema: edw_asis
    table: data
  target:
    type: table
    environment: DEV_REVOPS  # revops_test_qa
    schema: edw_asis
    table: data
  primary_keys: id
```

## Run It!

```bash
python main.py --config config/multi_env_examples.yaml
```

## That's It!

No more hardcoding credentials in configs. Just specify the environment name and go! 🚀

## Full Documentation

See [MULTI_ENVIRONMENT.md](file:///Users/kkrishna/Library/CloudStorage/OneDrive-InfobloxInc/PycharmProjects/infoblox-DE/1UniversalFramework/universal-validator/docs/MULTI_ENVIRONMENT.md) for complete details.
