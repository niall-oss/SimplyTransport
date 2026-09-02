from unittest.mock import patch

import click
from click.testing import CliRunner


@patch("SimplyTransport.lib.db.services.recreate_indexes")
def test_recreate_indexes_command_without_table_abort(
    mock_recreate_indexes, cli_runner: CliRunner, cli_group: click.Group
):
    result = cli_runner.invoke(cli_group.commands["recreate_indexes"], input="n\n")

    assert result.exit_code == 0
    assert "Recreating indexes..." in result.output
    assert "No table specified to recreate indexes on from the -table argument" in result.output
    assert "You are about to recreate indexes on all tables. Press" in result.output
    assert "Aborting recreate indexes..." in result.output
    mock_recreate_indexes.assert_not_called()


@patch("SimplyTransport.lib.db.services.recreate_indexes")
def test_recreate_indexes_command_without_table_succeed(
    mock_recreate_indexes, cli_runner: CliRunner, cli_group: click.Group
):
    result = cli_runner.invoke(cli_group.commands["recreate_indexes"], input="y\n")

    assert result.exit_code == 0
    assert "Recreating indexes..." in result.output
    assert "No table specified to recreate indexes on from the -table argument" in result.output
    assert "You are about to recreate indexes on all tables. Press" in result.output
    assert "Finished recreating indexes in" in result.output
    mock_recreate_indexes.assert_called_once()


@patch("SimplyTransport.lib.db.services.recreate_indexes")
def test_recreate_indexes_command_with_table_succeed(
    mock_recreate_indexes, cli_runner: CliRunner, cli_group: click.Group
):
    result = cli_runner.invoke(cli_group.commands["recreate_indexes"], ["-table", "agency"], input="y\n")

    assert result.exit_code == 0
    assert "Recreating indexes..." in result.output
    assert "Recreating indexes on table agency" in result.output
    assert "Finished recreating indexes in" in result.output
    mock_recreate_indexes.assert_called_once_with("agency")


@patch("SimplyTransport.lib.db.services.recreate_indexes")
def test_recreate_indexes_command_with_table_abort(
    mock_recreate_indexes, cli_runner: CliRunner, cli_group: click.Group
):
    result = cli_runner.invoke(cli_group.commands["recreate_indexes"], ["-table", "agency"], input="n\n")

    assert result.exit_code == 0
    assert "Recreating indexes..." in result.output
    assert "Recreating indexes on table agency" in result.output
    assert "Aborting recreate indexes..." in result.output
    mock_recreate_indexes.assert_not_called()
