# Testing guide

Tests use pytest. The runner refuses a `DATABASE_URL` that contains `ros_server.db`. The pytest session itself points at `test_ros.db`, which is disposable.

```powershell
python -m tools.test_runner --category compatibility
python -m tools.test_runner --feature authentication
python -m tools.test_runner --feature lobby
python -m tools.test_runner --all
```

Each command writes `reports/<label>/latest.json` and `latest.html`. The previous `latest.json` is copied to `previous.json` before it is replaced. The process exit code is pytest's exit code, or 2 when the database guard rejects the URL.

Feature directories:

- `tests/compatibility/authentication`
- `tests/compatibility/player`
- `tests/compatibility/lobby`
- `tests/compatibility/matchmaking`
- `tests/compatibility/gameplay`
- `tests/compatibility/inventory`
- `tests/compatibility/weapons`
- `tests/compatibility/match_results`

`tools/game_simulator` runs the seeded lobby and match scenario. `tools/protocol_validator` checks this server's JSON messages. `tools/player_simulator` calls the HTTP account routes.

A passing test updates test status only. Original Rules of Survival compatibility stays `unknown` until an authorized reference exists.
