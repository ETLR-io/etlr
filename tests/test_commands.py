"""Tests for the ETLR CLI commands."""

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from etlr.client import APIError
from etlr.main import cli


@pytest.fixture
def runner() -> CliRunner:
    """Create a CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_client():
    """Create a mock workflow client."""
    with patch("etlr.main.WorkflowsClient") as mock:
        yield mock


def test_cli_help(runner: CliRunner) -> None:
    """Test that --help works."""
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "ETLR" in result.output
    assert "Workflow automation tool" in result.output


def test_cli_version(runner: CliRunner) -> None:
    """Test that --version works."""
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "etlr, version" in result.output


def test_list_workflows(runner: CliRunner, mock_client) -> None:
    """Test list command."""
    mock_instance = MagicMock()
    mock_instance.list_workflows.return_value = {"workflows": [{"id": "123", "name": "test-workflow"}]}
    mock_client.return_value = mock_instance

    result = runner.invoke(cli, ["--api-key", "test-key", "list"])
    assert result.exit_code == 0
    assert "123" in result.output
    assert "test-workflow" in result.output
    mock_instance.list_workflows.assert_called_once()


def test_get_workflow_by_id(runner: CliRunner, mock_client) -> None:
    """Test get command with workflow ID."""
    mock_instance = MagicMock()
    mock_instance.get_workflow.return_value = {"id": "123", "name": "test-workflow", "stage": "prod"}
    mock_client.return_value = mock_instance

    result = runner.invoke(cli, ["--api-key", "test-key", "get", "--id", "123"])
    assert result.exit_code == 0
    assert "123" in result.output
    mock_instance.get_workflow.assert_called_once_with(workflow_id="123", name=None, stage=None)


def test_get_workflow_by_name_stage(runner: CliRunner, mock_client) -> None:
    """Test get command with name and stage."""
    mock_instance = MagicMock()
    mock_instance.get_workflow.return_value = {"id": "123", "name": "test-workflow", "stage": "prod"}
    mock_client.return_value = mock_instance

    result = runner.invoke(cli, ["--api-key", "test-key", "get", "--name", "test-workflow", "--stage", "prod"])
    assert result.exit_code == 0
    mock_instance.get_workflow.assert_called_once_with(workflow_id=None, name="test-workflow", stage="prod")


def test_delete_workflow_with_confirmation(runner: CliRunner, mock_client) -> None:
    """Test delete command with confirmation."""
    mock_instance = MagicMock()
    mock_instance.delete_workflow.return_value = {"message": "deleted"}
    mock_client.return_value = mock_instance

    result = runner.invoke(cli, ["--api-key", "test-key", "delete", "--id", "123"], input="y\n")
    assert result.exit_code == 0
    assert "deleted" in result.output.lower()
    mock_instance.delete_workflow.assert_called_once()


def test_delete_workflow_skip_confirmation(runner: CliRunner, mock_client) -> None:
    """Test delete command with --yes flag."""
    mock_instance = MagicMock()
    mock_instance.delete_workflow.return_value = {"message": "deleted"}
    mock_client.return_value = mock_instance

    result = runner.invoke(cli, ["--api-key", "test-key", "delete", "--name", "test", "--stage", "prod", "--yes"])
    assert result.exit_code == 0
    mock_instance.delete_workflow.assert_called_once_with(workflow_id=None, name="test", stage="prod")


def test_deploy_workflow_by_id(runner: CliRunner, mock_client) -> None:
    """Test deploy command with workflow ID."""
    mock_instance = MagicMock()
    mock_instance.deploy_workflow.return_value = {"status": "deployed"}
    mock_client.return_value = mock_instance

    result = runner.invoke(cli, ["--api-key", "test-key", "deploy", "--id", "123"])
    assert result.exit_code == 0
    assert "deployed" in result.output.lower()
    mock_instance.deploy_workflow.assert_called_once_with(workflow_id="123", name=None, stage=None)


def test_deploy_workflow_from_file(runner: CliRunner, mock_client, tmp_path) -> None:
    """Test deploy command from YAML file (push + deploy)."""
    # Create a temporary YAML file
    yaml_file = tmp_path / "workflow.yaml"
    yaml_file.write_text("workflow:\n  name: test-workflow\n  stage: prod\n  input:\n    type: webhook\n")

    mock_instance = MagicMock()
    # Mock the upsert (push) response
    mock_instance.upsert_workflow.return_value = {
        "created": True,
        "workflow": {"id": "123", "name": "test-workflow", "stage": "prod"},
    }
    # Mock the deploy response
    mock_instance.deploy_workflow.return_value = {"status": "deployed"}
    mock_client.return_value = mock_instance

    result = runner.invoke(cli, ["--api-key", "test-key", "deploy", str(yaml_file)])
    assert result.exit_code == 0
    assert "created" in result.output.lower() or "updated" in result.output.lower()
    assert "deployed" in result.output.lower()

    # Verify both push and deploy were called
    mock_instance.upsert_workflow.assert_called_once()
    mock_instance.deploy_workflow.assert_called_once()


def test_deploy_with_stage_override(runner: CliRunner, mock_client, tmp_path) -> None:
    """Test deploy command with --stage flag override."""
    yaml_file = tmp_path / "workflow.yaml"
    yaml_file.write_text("workflow:\n  name: test-workflow\n  stage: dev\n  input:\n    type: webhook\n")

    mock_instance = MagicMock()
    mock_instance.upsert_workflow.return_value = {
        "created": False,
        "workflow": {"id": "123", "name": "test-workflow", "stage": "prod"},
    }
    mock_instance.deploy_workflow.return_value = {"status": "deployed"}
    mock_client.return_value = mock_instance

    result = runner.invoke(cli, ["--api-key", "test-key", "deploy", str(yaml_file), "--stage", "prod"])
    assert result.exit_code == 0
    assert "stage override: prod" in result.output.lower()

    # Verify stage was passed to upsert_workflow
    call_args = mock_instance.upsert_workflow.call_args
    assert call_args.kwargs["stage"] == "prod"


def test_deploy_with_etlr_stage_env(runner: CliRunner, mock_client, tmp_path, monkeypatch) -> None:
    """Test deploy command with ETLR_STAGE environment variable."""
    monkeypatch.setenv("ETLR_STAGE", "staging")

    yaml_file = tmp_path / "workflow.yaml"
    yaml_file.write_text("workflow:\n  name: test-workflow\n  stage: dev\n  input:\n    type: webhook\n")

    mock_instance = MagicMock()
    mock_instance.upsert_workflow.return_value = {
        "created": False,
        "workflow": {"id": "123", "name": "test-workflow", "stage": "staging"},
    }
    mock_instance.deploy_workflow.return_value = {"status": "deployed"}
    mock_client.return_value = mock_instance

    result = runner.invoke(cli, ["--api-key", "test-key", "deploy", str(yaml_file)])
    assert result.exit_code == 0

    # Verify stage from env var was passed
    call_args = mock_instance.upsert_workflow.call_args
    assert call_args.kwargs["stage"] == "staging"


def test_deploy_stage_flag_overrides_env(runner: CliRunner, mock_client, tmp_path, monkeypatch) -> None:
    """Test that --stage flag overrides ETLR_STAGE env var."""
    monkeypatch.setenv("ETLR_STAGE", "dev")

    yaml_file = tmp_path / "workflow.yaml"
    yaml_file.write_text("workflow:\n  name: test-workflow\n  stage: dev\n  input:\n    type: webhook\n")

    mock_instance = MagicMock()
    mock_instance.upsert_workflow.return_value = {
        "created": False,
        "workflow": {"id": "123", "name": "test-workflow", "stage": "prod"},
    }
    mock_instance.deploy_workflow.return_value = {"status": "deployed"}
    mock_client.return_value = mock_instance

    result = runner.invoke(cli, ["--api-key", "test-key", "deploy", str(yaml_file), "--stage", "prod"])
    assert result.exit_code == 0

    # Verify flag overrides env var
    call_args = mock_instance.upsert_workflow.call_args
    assert call_args.kwargs["stage"] == "prod"


def test_deploy_with_environment_vars_from_yaml(runner: CliRunner, mock_client, tmp_path, monkeypatch) -> None:
    """Test deploy gathers environment variables declared in YAML."""
    yaml_file = tmp_path / "workflow.yaml"
    yaml_file.write_text(
        """workflow:
  name: test-workflow
  stage: dev
  environment:
    - name: API_KEY
      secret: true
    - name: LOG_LEVEL
      secret: false
  input:
    type: webhook
"""
    )

    # Set environment variables
    monkeypatch.setenv("API_KEY", "secret-key-123")
    monkeypatch.setenv("LOG_LEVEL", "info")

    mock_instance = MagicMock()
    mock_instance.upsert_workflow.return_value = {
        "created": True,
        "workflow": {"id": "123", "name": "test-workflow", "stage": "dev"},
    }
    mock_instance.deploy_workflow.return_value = {"status": "deployed"}
    mock_client.return_value = mock_instance

    result = runner.invoke(cli, ["--api-key", "test-key", "deploy", str(yaml_file)])
    assert result.exit_code == 0
    assert "API_KEY: ***" in result.output  # Secret should be masked
    assert "LOG_LEVEL: info" in result.output  # Non-secret should be visible

    # Verify env vars were passed to API in correct format
    call_args = mock_instance.upsert_workflow.call_args
    env_vars = call_args.kwargs["env"]
    assert len(env_vars) == 2
    assert {"name": "API_KEY", "value": "secret-key-123", "secret": True} in env_vars
    assert {"name": "LOG_LEVEL", "value": "info", "secret": False} in env_vars


def test_deploy_with_missing_environment_vars(runner: CliRunner, mock_client, tmp_path, monkeypatch) -> None:
    """Test deploy fails when required environment variables are missing."""
    yaml_file = tmp_path / "workflow.yaml"
    yaml_file.write_text(
        """workflow:
  name: test-workflow
  stage: dev
  environment:
    - name: API_KEY
      secret: true
    - name: DATABASE_URL
      secret: true
  input:
    type: webhook
"""
    )

    # Only set one of the required env vars
    monkeypatch.setenv("API_KEY", "secret-key-123")
    # DATABASE_URL is missing

    mock_instance = MagicMock()
    mock_client.return_value = mock_instance

    result = runner.invoke(cli, ["--api-key", "test-key", "deploy", str(yaml_file)])
    assert result.exit_code == 1
    assert "Missing required environment variables" in result.output
    assert "DATABASE_URL" in result.output


def test_deploy_cli_env_overrides_yaml(runner: CliRunner, mock_client, tmp_path, monkeypatch) -> None:
    """Test that -e flag overrides environment variables from YAML."""
    yaml_file = tmp_path / "workflow.yaml"
    yaml_file.write_text(
        """workflow:
  name: test-workflow
  stage: dev
  environment:
    - name: API_KEY
      secret: true
  input:
    type: webhook
"""
    )

    # Set env var in environment
    monkeypatch.setenv("API_KEY", "env-key")

    mock_instance = MagicMock()
    mock_instance.upsert_workflow.return_value = {
        "created": True,
        "workflow": {"id": "123", "name": "test-workflow", "stage": "dev"},
    }
    mock_instance.deploy_workflow.return_value = {"status": "deployed"}
    mock_client.return_value = mock_instance

    # Override with CLI flag
    result = runner.invoke(cli, ["--api-key", "test-key", "deploy", str(yaml_file), "-e", "API_KEY=cli-override"])
    assert result.exit_code == 0

    # Verify CLI override was used
    call_args = mock_instance.upsert_workflow.call_args
    env_vars = call_args.kwargs["env"]
    assert len(env_vars) == 1
    assert env_vars[0]["name"] == "API_KEY"
    assert env_vars[0]["value"] == "cli-override"
    assert env_vars[0]["secret"] is True  # Should still be marked as secret from YAML


def test_deploy_without_environment_section(runner: CliRunner, mock_client, tmp_path) -> None:
    """Test deploy works without environment section (backward compatibility)."""
    yaml_file = tmp_path / "workflow.yaml"
    yaml_file.write_text("workflow:\n  name: test-workflow\n  stage: dev\n  input:\n    type: webhook\n")

    mock_instance = MagicMock()
    mock_instance.upsert_workflow.return_value = {
        "created": True,
        "workflow": {"id": "123", "name": "test-workflow", "stage": "dev"},
    }
    mock_instance.deploy_workflow.return_value = {"status": "deployed"}
    mock_client.return_value = mock_instance

    # Deploy with CLI env vars only
    result = runner.invoke(cli, ["--api-key", "test-key", "deploy", str(yaml_file), "-e", "API_KEY=test"])
    assert result.exit_code == 0

    # Verify env var was passed in correct format
    call_args = mock_instance.upsert_workflow.call_args
    env_vars = call_args.kwargs["env"]
    assert len(env_vars) == 1
    assert env_vars[0] == {"name": "API_KEY", "value": "test", "secret": False}


def test_deploy_environment_var_without_secret_defaults_false(
    runner: CliRunner, mock_client, tmp_path, monkeypatch
) -> None:
    """Test that environment variables without 'secret' field default to secret: false."""
    yaml_file = tmp_path / "workflow.yaml"
    yaml_file.write_text(
        """workflow:
  name: test-workflow
  stage: dev
  environment:
    - name: LOG_LEVEL
  input:
    type: webhook
"""
    )

    monkeypatch.setenv("LOG_LEVEL", "debug")

    mock_instance = MagicMock()
    mock_instance.upsert_workflow.return_value = {
        "created": True,
        "workflow": {"id": "123", "name": "test-workflow", "stage": "dev"},
    }
    mock_instance.deploy_workflow.return_value = {"status": "deployed"}
    mock_client.return_value = mock_instance

    result = runner.invoke(cli, ["--api-key", "test-key", "deploy", str(yaml_file)])
    assert result.exit_code == 0
    # Should show value since secret defaults to false
    assert "LOG_LEVEL: debug" in result.output
    assert "***" not in result.output


def test_start_workflow(runner: CliRunner, mock_client) -> None:
    """Test start command."""
    mock_instance = MagicMock()
    mock_instance.deploy_workflow.return_value = {"status": "started"}
    mock_client.return_value = mock_instance

    result = runner.invoke(cli, ["--api-key", "test-key", "start", "--name", "test", "--stage", "prod"])
    assert result.exit_code == 0
    assert "started" in result.output.lower()
    mock_instance.deploy_workflow.assert_called_once_with(workflow_id=None, name="test", stage="prod")


def test_stop_workflow(runner: CliRunner, mock_client) -> None:
    """Test stop command."""
    mock_instance = MagicMock()
    mock_instance.stop_workflow.return_value = {"status": "stopped"}
    mock_client.return_value = mock_instance

    result = runner.invoke(cli, ["--api-key", "test-key", "stop", "--name", "test", "--stage", "prod"])
    assert result.exit_code == 0
    assert "stopped" in result.output.lower()
    mock_instance.stop_workflow.assert_called_once_with(workflow_id=None, name="test", stage="prod")


def test_status_workflow(runner: CliRunner, mock_client) -> None:
    """Test status command."""
    mock_instance = MagicMock()
    mock_instance.get_status.return_value = {
        "runtime_health": {"status": "ok", "ready": True, "last_event_received": "2025-12-11T10:00:00Z"}
    }
    mock_client.return_value = mock_instance

    result = runner.invoke(cli, ["--api-key", "test-key", "status", "--id", "123"])
    assert result.exit_code == 0
    assert "ok" in result.output.lower()
    assert "ready" in result.output.lower()
    mock_instance.get_status.assert_called_once_with(workflow_id="123", name=None, stage=None)


def test_api_error_handling(runner: CliRunner, mock_client) -> None:
    """Test that API errors are handled properly."""
    mock_instance = MagicMock()
    mock_instance.list_workflows.side_effect = APIError("Test error", status_code=400, details={"info": "test"})
    mock_client.return_value = mock_instance

    result = runner.invoke(cli, ["--api-key", "test-key", "list"])
    assert result.exit_code == 1
    assert "Error: Test error" in result.output
    assert "400" in result.output


def test_missing_api_key(runner: CliRunner) -> None:
    """Test that missing API key is handled."""
    with patch("etlr.main.WorkflowsClient") as mock:
        mock.side_effect = APIError("API key not provided")
        result = runner.invoke(cli, ["list"])
        assert result.exit_code == 1
        assert "Error" in result.output


def test_api_key_from_env(runner: CliRunner, mock_client, monkeypatch) -> None:
    """Test that API key is read from environment variable."""
    monkeypatch.setenv("ETLR_API_KEY", "env-key")

    mock_instance = MagicMock()
    mock_instance.list_workflows.return_value = {"workflows": []}
    mock_client.return_value = mock_instance

    result = runner.invoke(cli, ["list"])
    assert result.exit_code == 0

    # Verify client was initialized (api_key would be passed from env)
    mock_client.assert_called_once()


def test_api_key_flag_overrides_env(runner: CliRunner, mock_client, monkeypatch) -> None:
    """Test that --api-key flag overrides environment variable."""
    monkeypatch.setenv("ETLR_API_KEY", "env-key")

    mock_instance = MagicMock()
    mock_instance.list_workflows.return_value = {"workflows": []}
    mock_client.return_value = mock_instance

    # Pass explicit API key via flag
    result = runner.invoke(cli, ["--api-key", "flag-key", "list"])
    assert result.exit_code == 0

    # Verify client was called with the flag key (overriding env)
    mock_client.assert_called_once_with(api_key="flag-key")


def test_list_versions(runner: CliRunner, mock_client) -> None:
    """Test versions command."""
    mock_instance = MagicMock()
    mock_instance.list_versions.return_value = {
        "versions": [
            {"version": 1, "created_at": "2025-12-01", "is_current": False},
            {"version": 2, "created_at": "2025-12-11", "is_current": True},
        ]
    }
    mock_client.return_value = mock_instance

    result = runner.invoke(cli, ["--api-key", "test-key", "versions", "--id", "123"])
    assert result.exit_code == 0
    assert "Version 1" in result.output
    assert "Version 2" in result.output
    mock_instance.list_versions.assert_called_once_with(workflow_id="123")


def test_get_version(runner: CliRunner, mock_client) -> None:
    """Test get-version command."""
    mock_instance = MagicMock()
    mock_instance.get_version.return_value = {
        "version": 2,
        "workflow_yaml": "name: test\nstage: prod",
        "created_at": "2025-12-11",
    }
    mock_client.return_value = mock_instance

    result = runner.invoke(cli, ["--api-key", "test-key", "get-version", "--id", "123", "--version", "2"])
    assert result.exit_code == 0
    assert "workflow_yaml" in result.output
    mock_instance.get_version.assert_called_once_with(workflow_id="123", version=2)


def test_restore_version_with_confirmation(runner: CliRunner, mock_client) -> None:
    """Test restore command with confirmation."""
    mock_instance = MagicMock()
    mock_instance.restore_version.return_value = {"workflow": {"version": 3}, "message": "restored"}
    mock_client.return_value = mock_instance

    result = runner.invoke(cli, ["--api-key", "test-key", "restore", "--id", "123", "--version", "2"], input="y\n")
    assert result.exit_code == 0
    assert "restored" in result.output.lower()
    mock_instance.restore_version.assert_called_once_with(workflow_id="123", version=2)


def test_restore_version_skip_confirmation(runner: CliRunner, mock_client) -> None:
    """Test restore command with --yes flag."""
    mock_instance = MagicMock()
    mock_instance.restore_version.return_value = {"workflow": {"version": 3}}
    mock_client.return_value = mock_instance

    result = runner.invoke(cli, ["--api-key", "test-key", "restore", "--id", "123", "--version", "2", "--yes"])
    assert result.exit_code == 0
    mock_instance.restore_version.assert_called_once_with(workflow_id="123", version=2)
