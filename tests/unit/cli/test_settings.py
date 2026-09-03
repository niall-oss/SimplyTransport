import click
from click.testing import CliRunner


def test_settings_command(cli_runner: CliRunner, cli_group: click.Group):
    result = cli_runner.invoke(cli_group.commands["settings"])

    assert result.exit_code == 0
    assert "LITESTAR_APP" in result.output
    assert "Debug" in result.output
    assert "Environment" in result.output
    assert "Database URL" in result.output
    assert "Database Echo" in result.output
    assert "Log Level" in result.output
