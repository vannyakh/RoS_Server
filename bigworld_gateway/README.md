# BigWorld gateway (RoS open play server v2)

Preservation/research server for Rules of Survival 1.610637.617289 (BigWorld Mercury, UDP/TCP :25000).
Imported from RosGG-Server-v2 (commit 48522b6). This folder is the gateway for the original client: `server/ros_server.py` handles login, lobby, HTTP/HTTPS/DNS targets and the UDP/TCP gates. It runs on its own, separate from the FastAPI app in `app/`, and uses the repository `.venv`.

```
bigworld_gateway/
  start.cmd / stop.cmd     launcher (DNS + game server), reads config.cmd
  config.cmd               PC IP, test account, lobby route settings
  requirements.txt
  server/                  everything the server needs (paths are relative to these files)
    ros_server.py          main server: HTTP/HTTPS targets, UDP/TCP gates, Athlete lobby entity
    bwdefs.py              BigWorld .def parser (plain import, no sys.path hacks)
    loginapp.py            Mercury login reply
    dns_server.py
    certs/  real/  server_keys/  saved_accounts.json
    extract/               data only: entity defs, hall_props.json, supplement_info.json
  client/
    apk/                   put the XAPK here (see README)
    scripts/               adb install/setup/DNS scripts (point at ../../server/...)
    frida/                 read-only inspection payloads
  tools/                   probes, test cycles (bash, need adb + frida)
  docs/                    findings (LOBBY_FINDINGS.md), original README, decompile notes
  logs/                    server/dns logs
```

## Run
1. Edit `config.cmd` (`ROS_PC_IP` must be this PC's LAN IP; same value in the device's DNS).
2. `pip install -r requirements.txt` (or reuse the parent `.venv`).
3. `start.cmd`, then `client\scripts\sync_server_list.ps1` and `client\scripts\verify_play_path.ps1`.
4. Install the game: `client\scripts\install_ros.ps1`. Launch it and press PLAY.

## Accounts and admin console (`.env`)
From the repo root, run `python scripts/sync_gateway_env.py` after you change `GATEWAY_API_KEY` in `RoS_Server/.env` (writes `bigworld_gateway/.env`). Or copy `bigworld_gateway/.env.example` by hand.
`server/account_link.py` reads the environment first, then this folder `.env`, then `RoS_Server/.env`.

| Setting | Used by | Meaning |
|---|---|---|
| `ROS_API_URL` | gateway | RoS_Server API, default `http://127.0.0.1:8000` |
| `GATEWAY_API_KEY` | gateway + RoS_Server | shared key, must match `RoS_Server/.env`; empty = no link |
| `ROS_API_TIMEOUT` | gateway | seconds before falling back to local accounts (default 2) |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | RoS_Server | admin console login; RoS_Server creates this operator on startup |

- **Linked** (`GATEWAY_API_KEY` set and RoS_Server running): each device logs in as `gw_<uid>`.
  The admin console lists, renames and bans these accounts. A banned or suspended account gets no login reply.
- **Not linked**: accounts are kept in `server/saved_accounts.json`. `TEST_ACCOUNT_NAME` in `config.cmd`
  sets the lobby name of the test account.
- The admin password belongs only in `.env` files. Ask the server owner for it. Don't put it in the README, the code or chat.

## Status (2026-11-18)
Login -> lobby works (base-only Athlete). Lobby UI loads; remaining work and the debugging
pattern are in `docs/LOBBY_FINDINGS.md`. Character type is set in `server/saved_accounts.json`
(`20001` = normal male hero, `20002` = normal female hero). Any other type (10001, 10002, the
30001 robot placeholder, unknown values) is mapped to the hero of the saved gender by
`server/hero_rules.py`.

## Next: real launcher
A single GUI/CLI launcher can wrap `start.cmd` + `install_ros.ps1`: detect adb device,
write the PC IP into config + server list, start the server, install/launch the APK.

## Accounts in RoS_Server
`server/account_link.py` links each login to a RoS_Server account through `/api/v1/gateway`. It reads `GATEWAY_API_KEY` (and optional `ROS_API_URL`, default `http://127.0.0.1:8000`) from the environment or from the repository `.env`. Start the FastAPI server first. Then:
- each device gets its own uid, hashed from the `ci=` device id in its SDK requests (`CBP_GID` pins one uid, `DEVICE_UIDS=off` shares `9000000001`);
- the first login creates account `gw_<uid>`, visible in the admin console;
- with `TEST_ACCOUNT_NAME` set, a new account gets that nickname (or `<name>_<last 4 uid digits>` if taken) and `ATHLETE_CHAR` without the character screen;
- a nickname changed in the admin console is used on the next login;
- a suspended or banned account gets no login reply.
If the key is empty or the API is down, the gateway falls back to `server/saved_accounts.json`.
