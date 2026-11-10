# Monitoring guide

`GET /metrics` exposes the Prometheus text format. `tests/unit/test_observability.py` fetched it and found these names:

- `ros_http_requests_total`
- `ros_http_request_duration_seconds`
- `ros_game_tick_duration_seconds`
- `ros_database_query_duration_seconds`
- `ros_function_executions_total`

The same response also defines `ros_active_sessions`, `ros_active_lobbies`, `ros_active_matches`, `ros_game_tick_overruns_total`, `ros_database_pool_connections`, and `ros_function_duration_seconds`. The test asserted the body does not contain `player_id`.

`ros_active_lobbies` is the in-memory queue size, not a count of durable `lobbies` rows. The tick updates it without a database query.

Scrape config: `monitoring/prometheus/prometheus.yml` targets `127.0.0.1:8000`. Alerts: `monitoring/alerts/ros_server.yml`. Dashboard: `monitoring/grafana/dashboards/server.json` with panels for overview, API, database, sessions, lobby, matches, tick overruns, HTTP 5xx, and function/pool health.

Prometheus and Grafana were not started. The metrics page was served by the test client. No Sentry project was configured.
