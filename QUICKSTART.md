# ETLR CLI - Quick Reference

> **Command cheat sheet.** For detailed explanations, see [README.md](README.md)

## Setup

```bash
pip install etlr
export ETLR_API_KEY=your_api_key_here
```

## Common Commands

```bash
# List workflows
etlr list

# Deploy (create/update + start)
etlr deploy workflow.yaml
etlr deploy workflow.yaml --stage prod
etlr deploy workflow.yaml -e API_KEY=xxx -e LOG_LEVEL=debug

# Get workflow
etlr get --name my-workflow --stage prod
etlr get --id <workflow-uuid>

# Start/Stop
etlr start --name my-workflow --stage prod
etlr stop --name my-workflow --stage prod

# Status
etlr status --name my-workflow --stage prod

# Delete
etlr delete --name my-workflow --stage prod --yes

# Versions
etlr versions --id <workflow-uuid>
etlr get-version --id <workflow-uuid> --version 2
etlr restore --id <workflow-uuid> --version 2
```

## Stage Management

```bash
# Method 1: Environment variable (recommended)
export ETLR_STAGE=dev
etlr deploy workflow.yaml

# Method 2: CLI flag (explicit)
etlr deploy workflow.yaml --stage prod

# Method 3: In YAML
# stage: prod

# Method 4: Dynamic in YAML
# stage: ${env:STAGE}
```

## Environment Variables

**In workflow.yaml:**
```yaml
workflow:
  environment:
    - name: API_KEY
      secret: true
    - name: LOG_LEVEL
```

**Deploy:**
```bash
export API_KEY=secret123
export LOG_LEVEL=info
etlr deploy workflow.yaml

# Or override
etlr deploy workflow.yaml -e API_KEY=different
```

## Global Options

```bash
--api-key TEXT    # Override ETLR_API_KEY
--help            # Show help
--version         # Show version
```

## Minimal Workflow Example

```yaml
name: hello-world
stage: dev

input:
  type: webhook

steps:
  - type: print
    message: "Hello ${input.data}"
```

## Tips

- Use `--yes` to skip confirmations in scripts
- All commands accept `--id` OR `--name` + `--stage`
- Set `ETLR_API_KEY` and `ETLR_STAGE` in `~/.zshrc` for convenience
- Use `-e KEY=VALUE` multiple times for multiple env vars

**For full documentation, see [README.md](README.md)**
