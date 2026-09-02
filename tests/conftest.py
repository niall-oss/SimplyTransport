import click
import pytest
from click.testing import CliRunner


@pytest.fixture(scope="session")
def cli_runner() -> CliRunner:
    return CliRunner()


@pytest.fixture(scope="session")
def cli_group() -> click.Group:
    from SimplyTransport.cli import CLIPlugin

    cli = CLIPlugin()
    group = click.Group()
    cli.on_cli_init(group)
    return group
