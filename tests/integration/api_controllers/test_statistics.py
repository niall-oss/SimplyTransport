from datetime import UTC, datetime

from litestar.testing import TestClient


def test_statistics_most_recent_gtfs(client: TestClient) -> None:
    response = client.get("api/v1/statistics/gtfs.record.counts")
    assert response.status_code == 200
    response_json = response.json()
    assert len(response_json) == 9

    for i in range(0, len(response_json)):
        assert response_json[i]["statistic_type"] == "gtfs.record.counts"


def test_statistics_most_recent_operators(client: TestClient) -> None:
    response = client.get("api/v1/statistics/operator.route.counts")
    assert response.status_code == 200
    response_json = response.json()
    assert len(response_json) == 1  # 1 is the number of operators in the test database with at least 1 route
    # with statistics on a fresh database.
    # This is will fail locally if you have existing statistics in your DB.

    for i in range(0, len(response_json)):
        assert response_json[i]["statistic_type"] == "operator.route.counts"


def test_statistics_on_day(client: TestClient) -> None:
    current_day = datetime.now(UTC).date().isoformat()
    response = client.get(f"api/v1/statistics/gtfs.record.counts/{current_day}")
    assert response.status_code == 200
    response_json = response.json()
    assert len(response_json) == 9

    for i in range(0, len(response_json)):
        assert response_json[i]["statistic_type"] == "gtfs.record.counts"


def test_statistics_on_day_404(client: TestClient) -> None:
    response = client.get("api/v1/statistics/gtfs.record.counts/2021-01-01")
    assert response.status_code == 404
