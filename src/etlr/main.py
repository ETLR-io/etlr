"""Main CLI entry point for ETLR."""

import json
import os
import sys
from pathlib import Path
from typing import Optional

import click
import yaml

from . import __version__
from .client import APIError, WorkflowsClient


def get_client(api_key: Optional[str] = None) -> WorkflowsClient:
    """Get an API client instance."""
    try:
        return WorkflowsClient(api_key=api_key)
    except APIError as e:
        click.echo(click.style(f"Error: {e.message}", fg="red"), err=True)
        sys.exit(1)


def format_output(data: dict, format_type: str = "json") -> str:
    """Format output data."""
    if format_type == "json":
        return json.dumps(data, indent=2)
    return str(data)


def handle_api_error(e: APIError) -> None:
    """Handle API errors consistently."""
    click.echo(click.style(f"Error: {e.message}", fg="red"), err=True)
    if e.status_code:
        click.echo(click.style(f"Status Code: {e.status_code}", fg="red"), err=True)
    if e.details:
        click.echo(click.style(f"Details: {json.dumps(e.details, indent=2)}", fg="red"), err=True)
    sys.exit(1)


def gather_environment_variables(yaml_content: str, cli_overrides: tuple) -> list[dict[str, str | bool]]:
    """Gather environment variables from YAML and environment.

    Args:
        yaml_content: YAML file content
        cli_overrides: Tuple of KEY=VALUE strings from CLI

    Returns:
        List of environment variable objects with name, value, and secret fields
        Format: [{"name": "VAR", "value": "val", "secret": false}, ...]

    Raises:
        click.ClickException: If required environment variables are missing
    """
    try:
        parsed = yaml.safe_load(yaml_content)
    except yaml.YAMLError as e:
        raise click.ClickException(f"Invalid YAML: {e}") from e

    # Environment declarations should be under workflow key
    workflow = parsed.get("workflow", {})
    env_declarations = workflow.get("environment", [])

    if not env_declarations:
        # No environment section, fall back to CLI overrides only
        env_dict = {}
        for item in cli_overrides:
            if "=" not in item:
                raise click.ClickException(f"Invalid env format: {item}. Use KEY=VALUE")
            key, value = item.split("=", 1)
            env_dict[key] = value
        # Convert to API format
        return [{"name": name, "value": value, "secret": False} for name, value in env_dict.items()]

    # Gather environment variables from declarations
    env_vars = {}
    missing = []
    secret_vars = set()

    for env_def in env_declarations:
        if isinstance(env_def, dict):
            name = env_def.get("name")
            is_secret = env_def.get("secret", False)  # Default to False
        else:
            # Support simple string format: environment: [VAR1, VAR2]
            name = env_def
            is_secret = False

        if not name:
            continue

        if is_secret:
            secret_vars.add(name)

        # Look up actual value from environment
        value = os.getenv(name)

        if value is None:
            missing.append(name)
        else:
            env_vars[name] = value

    # Apply CLI overrides (these take precedence)
    for item in cli_overrides:
        if "=" not in item:
            raise click.ClickException(f"Invalid env format: {item}. Use KEY=VALUE")
        key, value = item.split("=", 1)
        env_vars[key] = value

    # Error if required env vars are missing
    if missing:
        raise click.ClickException(
            f"Missing required environment variables: {', '.join(missing)}\n"
            f"Set them with:\n  export {missing[0]}=value\n"
            f"Or use the -e flag:\n  etlr deploy workflow.yaml -e {missing[0]}=value"
        )

    # Display environment variables
    if env_vars:
        click.echo("\nEnvironment variables:")
        for name, value in sorted(env_vars.items()):
            is_secret = name in secret_vars
            display_value = "***" if is_secret else value
            secret_label = " (secret)" if is_secret else ""
            click.echo(f"  {name}: {display_value}{secret_label}")
        click.echo()

    # Convert to API format: array of {name, value, secret} objects
    return [{"name": name, "value": value, "secret": name in secret_vars} for name, value in env_vars.items()]


@click.group()
@click.version_option(version=__version__, prog_name="etlr")
@click.option(
    "--api-key",
    envvar="ETLR_API_KEY",
    help="API key for authentication (reads from ETLR_API_KEY env var if not provided)",
)
@click.pass_context
def cli(ctx: click.Context, api_key: Optional[str]) -> None:
    """ETLR - Workflow automation tool.

    Manage workflows, deployments, and monitoring through the ETLR platform.

    Authentication (in priority order):
      1. --api-key flag
      2. ETLR_API_KEY environment variable

    Quick start:
      export ETLR_API_KEY=your_key_here
      etlr deploy workflow.yaml
    """
    ctx.ensure_object(dict)
    ctx.obj["api_key"] = api_key


@cli.command("list")
@click.option("--format", "output_format", default="json", type=click.Choice(["json"]), help="Output format")
@click.pass_context
def list_workflows_cmd(ctx: click.Context, output_format: str) -> None:
    """List all workflows."""
    client = get_client(ctx.obj.get("api_key"))
    try:
        result = client.list_workflows()
        click.echo(format_output(result, output_format))
    except APIError as e:
        handle_api_error(e)


@cli.command()
@click.option("--id", "workflow_id", help="Workflow ID")
@click.option("--name", help="Workflow name")
@click.option("--stage", help="Workflow stage (prod/dev)")
@click.option("--format", "output_format", default="json", type=click.Choice(["json"]), help="Output format")
@click.pass_context
def get(
    ctx: click.Context, workflow_id: Optional[str], name: Optional[str], stage: Optional[str], output_format: str
) -> None:
    """Get workflow details.

    Provide either --id or both --name and --stage.
    """
    client = get_client(ctx.obj.get("api_key"))
    try:
        result = client.get_workflow(workflow_id=workflow_id, name=name, stage=stage)
        click.echo(format_output(result, output_format))
    except APIError as e:
        handle_api_error(e)


@cli.command()
@click.option("--id", "workflow_id", help="Workflow ID")
@click.option("--name", help="Workflow name")
@click.option("--stage", help="Workflow stage (prod/dev)")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
@click.pass_context
def delete(
    ctx: click.Context, workflow_id: Optional[str], name: Optional[str], stage: Optional[str], yes: bool
) -> None:
    """Delete a workflow.

    Provide either --id or both --name and --stage.
    """
    if not yes:
        identifier = workflow_id if workflow_id else f"{name}/{stage}"
        if not click.confirm(f"Are you sure you want to delete workflow '{identifier}'?"):
            click.echo("Aborted.")
            return

    client = get_client(ctx.obj.get("api_key"))
    try:
        result = client.delete_workflow(workflow_id=workflow_id, name=name, stage=stage)
        click.echo(click.style("✓ Workflow deleted", fg="green"))
        click.echo(format_output(result, "json"))
    except APIError as e:
        handle_api_error(e)


@cli.command()
@click.argument("yaml_file", type=click.Path(exists=True, path_type=Path), required=False)
@click.option("--id", "workflow_id", help="Workflow ID (alternative to file)")
@click.option("--name", help="Workflow name (alternative to file)")
@click.option(
    "--stage",
    envvar="ETLR_STAGE",
    help="Deployment stage - overrides YAML (reads from ETLR_STAGE env var if not provided)",
)
@click.option("--env", "-e", multiple=True, help="Environment variables in KEY=VALUE format")
@click.pass_context
def deploy(
    ctx: click.Context,
    yaml_file: Optional[Path],
    workflow_id: Optional[str],
    name: Optional[str],
    stage: Optional[str],
    env: tuple,
) -> None:
    """Deploy a workflow by pushing and starting it.

    Deploy from YAML file (recommended):
        etlr deploy workflow.yaml
        etlr deploy workflow.yaml --stage prod
        etlr deploy  # Looks for workflow.yaml in current directory

    Stage priority (highest to lowest):
        1. --stage flag
        2. ETLR_STAGE environment variable
        3. stage in YAML file

    Or deploy by identifier:
        etlr deploy --id workflow-uuid
        etlr deploy --name my-workflow --stage prod
    """
    client = get_client(ctx.obj.get("api_key"))

    # Initialize deploy variables
    deploy_name = name
    deploy_stage = stage

    # If YAML file is provided or found, push it first then deploy
    if yaml_file or (not workflow_id and not name):
        # If no file specified, look for workflow.yaml in current directory
        if not yaml_file:
            yaml_file = Path("workflow.yaml")
            if not yaml_file.exists():
                click.echo(
                    click.style(
                        "Error: No workflow.yaml found in current directory. Provide a file or use --id/--name flags.",
                        fg="red",
                    ),
                    err=True,
                )
                sys.exit(1)

        # Read YAML file
        try:
            yaml_content = yaml_file.read_text()
        except Exception as e:
            click.echo(click.style(f"Error reading file: {str(e)}", fg="red"), err=True)
            sys.exit(1)

        # Gather environment variables from YAML and environment
        try:
            env_dict = gather_environment_variables(yaml_content, env)
        except click.ClickException as e:
            click.echo(click.style(f"Error: {e.format_message()}", fg="red"), err=True)
            sys.exit(1)

        # Push the workflow
        try:
            if stage:
                click.echo(f"Pushing workflow (stage override: {stage})...")
            else:
                click.echo("Pushing workflow...")

            push_result = client.upsert_workflow(yaml=yaml_content, env=env_dict if env_dict else None, stage=stage)

            if push_result.get("created"):
                click.echo(click.style("✓ Workflow created", fg="green"))
            else:
                click.echo(click.style("✓ Workflow updated", fg="green"))

            # Extract workflow info for deployment
            workflow_info = push_result.get("workflow", {})
            workflow_id = workflow_info.get("id")
            deploy_name = workflow_info.get("name")
            deploy_stage = workflow_info.get("stage")

            if not workflow_id:
                click.echo(click.style("Error: Could not get workflow ID from push response", fg="red"), err=True)
                sys.exit(1)

        except APIError as e:
            handle_api_error(e)

    # Deploy the workflow
    try:
        identifier = f" {deploy_name}/{deploy_stage}" if deploy_name and deploy_stage else ""
        click.echo(f"Deploying workflow{identifier}...")
        result = client.deploy_workflow(workflow_id=workflow_id, name=deploy_name, stage=deploy_stage)
        click.echo(click.style("✓ Workflow deployed and running", fg="green"))
        click.echo(format_output(result, "json"))
    except APIError as e:
        handle_api_error(e)


@cli.command()
@click.option("--id", "workflow_id", help="Workflow ID")
@click.option("--name", help="Workflow name")
@click.option("--stage", help="Workflow stage (prod/dev)")
@click.pass_context
def start(ctx: click.Context, workflow_id: Optional[str], name: Optional[str], stage: Optional[str]) -> None:
    """Start a workflow that has already been pushed.

    Use this to start an existing workflow without pushing changes.
    For push + start in one command, use 'etlr deploy'.

    Provide either --id or both --name and --stage.

    Examples:
        etlr start --id workflow-uuid
        etlr start --name my-workflow --stage prod
    """
    client = get_client(ctx.obj.get("api_key"))
    try:
        result = client.deploy_workflow(workflow_id=workflow_id, name=name, stage=stage)
        click.echo(click.style("✓ Workflow started", fg="green"))
        click.echo(format_output(result, "json"))
    except APIError as e:
        handle_api_error(e)


@cli.command()
@click.option("--id", "workflow_id", help="Workflow ID")
@click.option("--name", help="Workflow name")
@click.option("--stage", help="Workflow stage (prod/dev)")
@click.pass_context
def stop(ctx: click.Context, workflow_id: Optional[str], name: Optional[str], stage: Optional[str]) -> None:
    """Stop a running workflow.

    Provide either --id or both --name and --stage.
    """
    client = get_client(ctx.obj.get("api_key"))
    try:
        result = client.stop_workflow(workflow_id=workflow_id, name=name, stage=stage)
        click.echo(click.style("✓ Workflow stopped", fg="green"))
        click.echo(format_output(result, "json"))
    except APIError as e:
        handle_api_error(e)


@cli.command()
@click.option("--id", "workflow_id", help="Workflow ID")
@click.option("--name", help="Workflow name")
@click.option("--stage", help="Workflow stage (prod/dev)")
@click.option("--format", "output_format", default="json", type=click.Choice(["json"]), help="Output format")
@click.pass_context
def status(
    ctx: click.Context, workflow_id: Optional[str], name: Optional[str], stage: Optional[str], output_format: str
) -> None:
    """Get workflow deployment status.

    Provide either --id or both --name and --stage.
    """
    client = get_client(ctx.obj.get("api_key"))
    try:
        result = client.get_status(workflow_id=workflow_id, name=name, stage=stage)

        # Pretty print status
        if "runtime_health" in result:
            health = result["runtime_health"]
            status_val = health.get("status", "unknown")

            # Color code status
            if status_val == "ok":
                status_color = "green"
            elif status_val == "paused":
                status_color = "yellow"
            else:
                status_color = "red"

            click.echo(f"Status: {click.style(status_val, fg=status_color)}")
            click.echo(f"Ready: {health.get('ready', 'unknown')}")

            if health.get("last_event_received"):
                click.echo(f"Last Event: {health['last_event_received']}")

            if health.get("errors"):
                click.echo(click.style(f"Errors: {health['errors']}", fg="red"))

            click.echo()

        click.echo(format_output(result, output_format))
    except APIError as e:
        handle_api_error(e)


@cli.command()
@click.option("--id", "workflow_id", required=True, help="Workflow ID")
@click.option("--format", "output_format", default="json", type=click.Choice(["json"]), help="Output format")
@click.pass_context
def versions(ctx: click.Context, workflow_id: str, output_format: str) -> None:
    """List all versions of a workflow.

    Example:
        etlr versions --id workflow-uuid
    """
    client = get_client(ctx.obj.get("api_key"))
    try:
        result = client.list_versions(workflow_id=workflow_id)

        # Pretty print version list
        if "versions" in result:
            versions_list = result["versions"]
            if versions_list:
                click.echo(f"Found {len(versions_list)} version(s):\n")
                for v in versions_list:
                    version_num = v.get("version", "?")
                    created_at = v.get("created_at", "unknown")
                    is_current = v.get("is_current", False)

                    marker = click.style("★", fg="green") if is_current else " "
                    click.echo(f"{marker} Version {version_num} - Created: {created_at}")
                    if v.get("description"):
                        click.echo(f"  Description: {v['description']}")
                click.echo()
            else:
                click.echo("No versions found.")

        click.echo(format_output(result, output_format))
    except APIError as e:
        handle_api_error(e)


@cli.command()
@click.option("--id", "workflow_id", required=True, help="Workflow ID")
@click.option("--version", "version", required=True, type=int, help="Version number")
@click.option("--format", "output_format", default="json", type=click.Choice(["json"]), help="Output format")
@click.pass_context
def get_version(ctx: click.Context, workflow_id: str, version: int, output_format: str) -> None:
    """Get details of a specific workflow version.

    Example:
        etlr get-version --id workflow-uuid --version 2
    """
    client = get_client(ctx.obj.get("api_key"))
    try:
        result = client.get_version(workflow_id=workflow_id, version=version)
        click.echo(format_output(result, output_format))
    except APIError as e:
        handle_api_error(e)


@cli.command()
@click.option("--id", "workflow_id", required=True, help="Workflow ID")
@click.option("--version", "version", required=True, type=int, help="Version number to restore")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
@click.pass_context
def restore(ctx: click.Context, workflow_id: str, version: int, yes: bool) -> None:
    """Restore a workflow to a specific version.

    This creates a new version with the content from the specified version.

    Example:
        etlr restore --id workflow-uuid --version 2
    """
    if not yes and not click.confirm(f"Are you sure you want to restore workflow to version {version}?"):
        click.echo("Aborted.")
        return

    client = get_client(ctx.obj.get("api_key"))
    try:
        result = client.restore_version(workflow_id=workflow_id, version=version)
        click.echo(click.style(f"✓ Workflow restored to version {version}", fg="green"))

        if "workflow" in result:
            new_version = result["workflow"].get("version")
            if new_version:
                click.echo(f"New version created: {new_version}")

        click.echo(format_output(result, "json"))
    except APIError as e:
        handle_api_error(e)


if __name__ == "__main__":
    cli(obj={})
