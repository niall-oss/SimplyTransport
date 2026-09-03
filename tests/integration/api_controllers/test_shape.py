import pytest
from litestar.testing import AsyncTestClient

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_shape_returns_points_in_ascending_sequence(async_client: AsyncTestClient) -> None:
    response = await async_client.get("/api/v1/shape/3623_278?orderBy=sequence&sortOrder=asc")
    assert response.status_code == 200
    points = response.json()
    assert len(points) == 1027
    assert points[0]["shape_id"] == "3623_278"
    assert points[0]["sequence"] == 1
    assert points[-1]["sequence"] == 1027


async def test_shape_returns_points_in_descending_sequence(async_client: AsyncTestClient) -> None:
    response = await async_client.get("/api/v1/shape/3623_278?orderBy=sequence&sortOrder=desc")
    assert response.status_code == 200
    points = response.json()
    assert len(points) == 1027
    assert points[0]["shape_id"] == "3623_278"
    assert points[0]["sequence"] == 1027
    assert points[-1]["sequence"] == 1


async def test_shape_returns_404_for_unknown_id(async_client: AsyncTestClient) -> None:
    response = await async_client.get("/api/v1/shape/3623323_279?orderBy=sequence&sortOrder=asc")
    assert response.status_code == 404
    assert response.json()["detail"] == "Shapes not found with id 3623323_279"
