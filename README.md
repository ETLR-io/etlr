# ETLR

[![image](https://img.shields.io/pypi/v/etlr.svg)](https://pypi.python.org/pypi/etlr)
[![image](https://img.shields.io/pypi/l/etlr.svg)](https://github.com/ETLR-io/etlr/blob/main/LICENSE)
[![image](https://img.shields.io/pypi/pyversions/etlr.svg)](https://pypi.python.org/pypi/etlr)
[![Discord](https://img.shields.io/badge/Discord-%235865F2.svg?logo=discord&logoColor=white)](https://discord.gg/VtMWjh6u3D)

Command-line interface for deploying and managing [ETLR](https://etlr.io) workflows.

**Quick reference:** See [QUICKSTART.md](QUICKSTART.md) for command cheat sheet.

## Table of Contents

- [Installation](#installation)
- [Authentication](#authentication)
- [Quick Start](#quick-start)
- [Environment Variables](#environment-variables)
- [Stage Management](#stage-management)
- [Commands](#commands)
- [Version Management](#version-management)
- [CI/CD Integration](#cicd-integration)
- [Development](#development)

## Installation

```bash
pip install etlr
```

## Authentication

### Get Your API Key

Get your API key from the ETLR dashboard:
👉 **https://app.etlr.io/developer**

### Recommended: Environment Variable

Set your API key once in your shell configuration:

```bash
# Add to ~/.zshrc or ~/.bashrc
export ETLR_API_KEY=your_api_key_here
```

Reload your shell or run:
```bash
source ~/.zshrc  # or ~/.bashrc
```

### Alternative: CLI Flag

Override or specify per-command:

```bash
etlr --api-key your_api_key_here list
```

**Priority:** CLI flag > `ETLR_API_KEY` environment variable

## Quick Start

### 1. Create a workflow

```yaml
# workflow.yaml
name: hello-world
stage: dev

input:
  type: http_webhook

steps:
  - type: print
    message: "Hello from ${input.data}!"
```

### 2. Deploy it

```bash
etlr deploy workflow.yaml
```

Output:
```
Pushing workflow...
✓ Workflow created: hello-world/dev
Deploying workflow...
✓ Workflow deployed and running
```

### 3. Check status

```bash
etlr status --name hello-world --stage dev
```

### 4. List all workflows

```bash
etlr list
```

That's it! Your workflow is running.

## Environment Variables

Declare environment variables in your workflow YAML, and the CLI automatically gathers them from your shell environment.

### Basic Usage

**1. Declare in workflow.yaml:**
```yaml
workflow:
  name: data-processor
  stage: dev

  environment:
    - name: API_KEY
      secret: true
    - name: DATABASE_URL
      secret: true
    - name: LOG_LEVEL

  input:
    type: http_webhook

  steps:
    - type: http_call
      url: https://api.example.com/data
      headers:
        Authorization: "Bearer ${env:API_KEY}"
```

**2. Set values in your shell:**
```bash
export API_KEY=sk-abc123...
export DATABASE_URL=postgres://...
export LOG_LEVEL=info
```

**3. Deploy:**
```bash
etlr deploy workflow.yaml
```

Output:
```
Environment variables:
  API_KEY: *** (secret)
  DATABASE_URL: *** (secret)
  LOG_LEVEL: info

Pushing workflow...
✓ Workflow deployed
```

### Secret Masking

Mark sensitive values as `secret: true` to hide them in CLI output:

```yaml
environment:
  - name: API_KEY
    secret: true       # Shows as ***
  - name: LOG_LEVEL
    secret: false      # Shows actual value
  - name: TIMEOUT      # Defaults to false
```

### CLI Overrides

Override declared env vars or add new ones with `-e` flag:

```bash
# Override
etlr deploy workflow.yaml -e API_KEY=different-key

# Add new variable
etlr deploy workflow.yaml -e EXTRA_VAR=value

# Multiple overrides
etlr deploy workflow.yaml -e API_KEY=xxx -e LOG_LEVEL=debug
```

### Missing Variables

If required env vars are missing, deployment fails with a helpful error:

```bash
$ etlr deploy workflow.yaml
Error: Missing required environment variables: API_KEY, DATABASE_URL

Set them with:
  export API_KEY=value
  export DATABASE_URL=value

Or use -e flags:
  etlr deploy workflow.yaml -e API_KEY=value -e DATABASE_URL=value
```

### Benefits

- ✅ **Self-documenting** - Anyone reading YAML knows what's needed
- ✅ **Validated** - Missing vars caught before deployment
- ✅ **No CLI clutter** - No need for multiple `-e` flags
- ✅ **Version controlled** - Variable *names* (not values) in git
- ✅ **Team friendly** - New developers see requirements immediately

## Stage Management

Stages (dev, staging, prod) let you run different versions of the same workflow in different environments.

### Four Ways to Set Stage

**Priority (highest to lowest):**
1. `--stage` CLI flag (explicit override)
2. `ETLR_STAGE` environment variable (session default)
3. `stage` field in YAML (file default)
4. `${env:STAGE}` in YAML (dynamic from environment)

### Method 1: Static in YAML (Simple)

```yaml
name: my-workflow
stage: dev
```

```bash
etlr deploy workflow.yaml           # Uses 'dev'
etlr deploy workflow.yaml --stage prod  # Override to 'prod'
```

**Use when:** Single environment or simple setup

### Method 2: ETLR_STAGE Variable (Recommended)

```bash
# Set once for your session
export ETLR_STAGE=dev

# Deploy without specifying stage
etlr deploy workflow.yaml           # Uses 'dev'

# Override when needed
etlr deploy workflow.yaml --stage prod
```

Add to `~/.zshrc` for persistence:
```bash
export ETLR_STAGE=dev
export ETLR_API_KEY=your_dev_key
```

**Use when:** Local development with occasional prod deploys

### Method 3: Dynamic in YAML (Flexible)

```yaml
name: my-workflow
stage: ${env:STAGE}     # or ${env:STAGE, dev} with default
```

```bash
STAGE=dev etlr deploy workflow.yaml
STAGE=prod etlr deploy workflow.yaml
```

**Use when:** CI/CD or multiple environments

### Method 4: CLI Flag (Most Explicit)

```bash
etlr deploy workflow.yaml --stage staging
etlr deploy workflow.yaml --stage prod
```

**Use when:** CI/CD pipelines or when you want explicit control

### Best Practices by Environment

**Local Development:**
```bash
# ~/.zshrc
export ETLR_STAGE=dev
export ETLR_API_KEY=dev_key

# Just deploy
cd my-project
etlr deploy workflow.yaml
```

**CI/CD:**
```yaml
# .github/workflows/deploy.yml
- name: Deploy to staging
  run: etlr deploy workflow.yaml --stage staging
  env:
    ETLR_API_KEY: ${{ secrets.STAGING_API_KEY }}

- name: Deploy to production
  run: etlr deploy workflow.yaml --stage prod
  env:
    ETLR_API_KEY: ${{ secrets.PROD_API_KEY }}
```

**Team with .env files:**
```bash
# .env.dev
ETLR_STAGE=dev
ETLR_API_KEY=dev_key

# .env.prod
ETLR_STAGE=prod
ETLR_API_KEY=prod_key

# Deploy
source .env.dev && etlr deploy workflow.yaml
source .env.prod && etlr deploy workflow.yaml
```

## Commands

### List Workflows

```bash
etlr list
```

### Deploy Workflow

Creates/updates and starts a workflow in one command.

```bash
# From file
etlr deploy workflow.yaml

# From workflow.yaml in current directory
etlr deploy

# Override stage
etlr deploy workflow.yaml --stage prod

# With environment variables
etlr deploy workflow.yaml -e API_KEY=xxx -e LOG_LEVEL=debug

# By identifier (if already pushed)
etlr deploy --id <workflow-uuid>
etlr deploy --name my-workflow --stage prod
```

### Get Workflow

```bash
# By ID
etlr get --id <workflow-uuid>

# By name and stage
etlr get --name my-workflow --stage prod
```

### Start Workflow

Start a workflow that was previously stopped or pushed but not started.

```bash
etlr start --id <workflow-uuid>
etlr start --name my-workflow --stage prod
```

### Stop Workflow

```bash
etlr stop --id <workflow-uuid>
etlr stop --name my-workflow --stage prod
```

### Get Status

```bash
etlr status --id <workflow-uuid>
etlr status --name my-workflow --stage prod
```

Output shows health status with color coding:
- 🟢 Green: Running normally
- 🟡 Yellow: Paused or warning
- 🔴 Red: Error or stopped

### Delete Workflow

```bash
# With confirmation prompt
etlr delete --id <workflow-uuid>
etlr delete --name my-workflow --stage prod

# Skip confirmation (for scripts)
etlr delete --name my-workflow --stage prod --yes
```

## Version Management

ETLR automatically versions workflows on each deploy. You can list, view, and restore previous versions.

### List Versions

```bash
etlr versions --id <workflow-uuid>
```

Output:
```
Versions for workflow abc-123:
  Version 3 (current) - 2025-12-17 14:23:10
  Version 2 - 2025-12-17 12:15:43
  Version 1 - 2025-12-16 09:30:22
```

### Get Specific Version

```bash
etlr get-version --id <workflow-uuid> --version 2
```

### Restore Previous Version

```bash
# With confirmation
etlr restore --id <workflow-uuid> --version 2

# Skip confirmation
etlr restore --id <workflow-uuid> --version 2 --yes
```

This creates a new version (e.g., version 4) with the content from version 2.

## CI/CD Integration

### GitHub Actions

```yaml
name: Deploy Workflow

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install ETLR CLI
        run: pip install etlr

      - name: Deploy to staging
        if: github.ref == 'refs/heads/main'
        run: etlr deploy workflow.yaml --stage staging
        env:
          ETLR_API_KEY: ${{ secrets.STAGING_API_KEY }}

      - name: Deploy to production
        if: github.ref == 'refs/heads/main' && github.event_name == 'release'
        run: etlr deploy workflow.yaml --stage prod
        env:
          ETLR_API_KEY: ${{ secrets.PROD_API_KEY }}
```

### GitLab CI

```yaml
stages:
  - deploy

deploy_staging:
  stage: deploy
  script:
    - pip install etlr
    - etlr deploy workflow.yaml --stage staging
  environment:
    name: staging
  variables:
    ETLR_API_KEY: $STAGING_API_KEY

deploy_production:
  stage: deploy
  script:
    - pip install etlr
    - etlr deploy workflow.yaml --stage prod
  environment:
    name: production
  variables:
    ETLR_API_KEY: $PROD_API_KEY
  when: manual
```

### Tips for CI/CD

- Store API keys in secret managers (`ETLR_API_KEY`)
- Use `--stage` flag for explicit environment targeting
- Use `--yes` flag to skip confirmations
- Set timeouts for deployment commands
- Add status checks after deployment

## Development

### Setup

```bash
git clone https://github.com/etlr-io/cli.git
cd cli

python3 -m venv .venv
source .venv/bin/activate

pip install -e ".[dev]"
```

### Run

```bash
etlr --help
```

### Testing

```bash
pytest
pytest -v  # Verbose
pytest tests/test_cli.py  # Specific file
```

### Code Quality

```bash
# Format
black src tests

# Lint
ruff check src tests

# Type check
mypy src
```

### Release

```bash
# Update version in pyproject.toml
# Commit and tag
git tag v1.2.3
git push origin v1.2.3

# Build and publish
python -m build
twine upload dist/*
```

## Tips & Tricks

### Per-Project Configuration

Use `.env` files or `direnv` for project-specific settings:

```bash
# .env
ETLR_API_KEY=project_specific_key
ETLR_STAGE=dev

# Load and deploy
source .env
etlr deploy workflow.yaml
```

Or use [direnv](https://direnv.net/) to auto-load when entering directory:

```bash
# .envrc
export ETLR_API_KEY=project_key
export ETLR_STAGE=dev
```

### Multiple Accounts

Switch between accounts with CLI flag:

```bash
# Production account
etlr --api-key $PROD_KEY deploy workflow.yaml

# Staging account
etlr --api-key $STAGING_KEY deploy workflow.yaml
```

### Workflow Aliases

Create shell aliases for common workflows:

```bash
# ~/.zshrc
alias deploy-prod='etlr deploy workflow.yaml --stage prod'
alias deploy-dev='etlr deploy workflow.yaml --stage dev'
alias check-prod='etlr status --name my-workflow --stage prod'
```

### Debugging

Enable verbose output (when available):

```bash
etlr --debug deploy workflow.yaml
```

Or check workflow logs via the web dashboard.

## Getting Help

- **Quick reference:** [QUICKSTART.md](QUICKSTART.md)
- **Issues:** https://github.com/etlr-io/cli/issues
- **Documentation:** https://etlr.io/docs/

## License

MIT
