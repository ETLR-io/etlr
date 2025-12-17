"""Tests for the ETLR CLI."""

import pytest
from click.testing import CliRunner

from etlr.main import cli


@pytest.fixture
def runner() -> CliRunner:
    """Create a CLI test runner."""
    return CliRunner()


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
