from unittest.mock import AsyncMock, Mock, patch

from fastapi.testclient import TestClient


with patch("nicegui.ui.run"):
    from src.app import main


def test_health_endpoint_is_small_plain_text_response() -> None:
    health_route = next(route for route in main.app.routes if route.path == "/health")
    root_route = next(route for route in main.app.routes if route.path == "/")
    response = TestClient(main.app).get("/health")

    assert health_route.endpoint is main.health
    assert health_route.endpoint is not root_route.endpoint
    assert response.status_code == 200
    assert response.content == b"OK"
    assert len(response.content) < 64
    assert response.headers["content-type"].startswith("text/plain")
    assert "set-cookie" not in response.headers


def test_health_endpoint_does_not_call_dashboard_database_or_pandas() -> None:
    dashboard = Mock(side_effect=AssertionError("dashboard must not be called"))
    query_df = AsyncMock(side_effect=AssertionError("query_df must not be called"))
    read_dataframe = AsyncMock(
        side_effect=AssertionError("read_dataframe must not be called")
    )
    read_scalar = AsyncMock(side_effect=AssertionError("read_scalar must not be called"))
    pandas_read_sql = Mock(side_effect=AssertionError("pandas must not load SQL"))
    pandas_read_csv = Mock(side_effect=AssertionError("pandas must not load CSV"))
    pandas_read_parquet = Mock(
        side_effect=AssertionError("pandas must not load parquet")
    )

    with (
        patch.object(main, "dashboard", dashboard),
        patch.object(main, "query_df", query_df),
        patch.object(main, "read_dataframe", read_dataframe),
        patch.object(main, "read_scalar", read_scalar),
        patch.object(main.pd, "read_sql", pandas_read_sql),
        patch.object(main.pd, "read_csv", pandas_read_csv),
        patch.object(main.pd, "read_parquet", pandas_read_parquet),
    ):
        response = TestClient(main.app).get("/health")

    assert response.status_code == 200
    assert response.content == b"OK"
    dashboard.assert_not_called()
    query_df.assert_not_awaited()
    read_dataframe.assert_not_awaited()
    read_scalar.assert_not_awaited()
    pandas_read_sql.assert_not_called()
    pandas_read_csv.assert_not_called()
    pandas_read_parquet.assert_not_called()
