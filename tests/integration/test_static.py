import pytest
from litestar.testing import AsyncTestClient
from SimplyTransport.lib.constants import STATIC_DIR

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.mark.parametrize(
    ("filename", "content_type"),
    [
        ("favicon.ico", "image/vnd.microsoft.icon"),
        ("site.webmanifest", "application/manifest+json"),
        ("robots.txt", "text/plain; charset=utf-8"),
        ("favicon-16x16.png", "image/png"),
        ("favicon-32x32.png", "image/png"),
        ("apple-touch-icon.png", "image/png"),
        ("android-chrome-192x192.png", "image/png"),
        ("android-chrome-512x512.png", "image/png"),
    ],
)
async def test_static_file_on_root(filename: str, content_type: str, async_client: AsyncTestClient) -> None:
    response = await async_client.get(f"/{filename}")
    assert response.status_code == 200
    assert response.headers["content-type"] == content_type


@pytest.mark.parametrize(
    ("filename", "content_type"),
    [
        ("event.css", "text/css; charset=utf-8"),
        ("style.css", "text/css; charset=utf-8"),
        ("loader.svg", "image/svg+xml"),
        ("simply_transport_logo.svg", "image/svg+xml"),
    ],
)
async def test_static_file_in_static(filename: str, content_type: str, async_client: AsyncTestClient) -> None:
    response = await async_client.get(f"/{STATIC_DIR}/{filename}")
    assert response.status_code == 200
    assert response.headers["content-type"] == content_type


async def test_static_files_have_max_age_header(async_client: AsyncTestClient) -> None:
    response = await async_client.get(f"/{STATIC_DIR}/loader.svg")
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "max-age=15552000"
