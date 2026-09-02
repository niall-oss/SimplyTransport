import click
import pytest
from click.testing import CliRunner


def pytest_collection_modifyitems(items: list[pytest.Item]):
    """Run unit tests first so they do not see integration-test env vars."""

    def is_unit(item: pytest.Item) -> bool:
        path = str(item.fspath)
        return "/tests/unit/" in path.replace("\\", "/")

    items[:] = [item for item in items if is_unit(item)] + [item for item in items if not is_unit(item)]


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
