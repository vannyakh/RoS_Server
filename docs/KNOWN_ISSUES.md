# Known issues (mobile restoration)

Live tracker: [RESTORATION_STATUS.md](RESTORATION_STATUS.md). Historical detail: [LOBBY_FINDINGS.md](../bigworld_gateway/docs/LOBBY_FINDINGS.md).

## Blockers

1. **RO-056 incomplete emulator proof** — createEntity property stream documented statically; fresh `space` + `entities_state.py` + 60s no-RESEND not finished.
2. **Per-address battle worlds** — `_battle_match(addr)` isolates players; no shared authoritative match.
3. **Workshop incomplete** — RO-095..RO-099 in flight; not mobile-verified.
4. **LDPlayer hall.scn load / inactivity** — long first load can drop the session before HALL timeout extends.
5. **Monthly Supreme Supply blank** (FIXED pending LDPlayer verify): the client picks the monthly box with the **device** clock, not `GAME_DATE`. Re-run `bigworld_gateway/client/scripts/setup_emulator.ps1` after each LDPlayer cold start (sets `2022-04-20` and disables auto time). `config.cmd` should keep `SysEnableMonthSupply` off the `LOBBY_SWITCHES_OFF` list when using that date. See [SUPPLY_RESTORATION.md](SUPPLY_RESTORATION.md).
6. **Weekly Supply push reopens at every login** (FIXED, RO-105; device check pending): the handler now takes no argument, as the `.def` declares, and saves this week's box (`athlete_requests.this_week_supply_id()`, which gives 9778). The data flags both 9778 and 9779, and nothing in the repo shows which one the client compares against. The monthly push (`hasAlreadyShowMonthSupply`) still repeats.
7. **Supply draw validation** (FIXED, RO-105): an unknown box id or a currency the box does not accept now fails, and a refused free draw gives nothing. The tests are in `tests/compatibility/gateway/supply/`. Check on the device that real ticket and diamond draws still succeed.
8. **Device performance not measured** (BLOCKED, RO-104): no adb on the host; FPS, frame time and memory are unknown.
9. **Store purchase gaps** (FIXED, RO-122/RO-123; device check pending): these are fixed and covered by tests in `tests/compatibility/gateway/store/`:
   - A linked buy or draw is now refused when RoS_Server is unreachable.
   - Each purchase carries a `request_id`, and the API replays a repeated id instead of charging again.
   - Coin goods are now charged; linked coin buys go through `workshop/compound`, and their ledger rows are labelled workshop.
   - Unpriced hall props are refused, and `num` is limited to 1..99.
   - The local wallet is per account.
   - A reply is always sent after a charge.
   Still open:
   - Local-mode coins are not saved.
   - Idempotency is safe only while the API runs as a single process.
10. **Gateway store and bridge** (FIXED, RO-123): `saved_accounts.json` goes through `local_store.py`, which is cached and written atomically. RoS_Server calls go through `api_client.py`, which keeps connections alive and never retries a POST.
11. **Hall-start tests depend on test order** (FIXED, RO-125): `tests/compatibility/gateway/session` gives each test its own event loop. The full `tests/unit` and `tests/compatibility/gateway` run passes (1572 tests).

## Operational

- One LAN IP everywhere: `ROS_PC_IP`, server list, DNS, adb scripts.
- Do not start frida-server before the game (DCTOOL crash); start after menu when probing.
- `app/` must not import `bigworld_gateway/`; persistence only via `/api/v1/gateway`.
- Original compatibility matrix remains **0 compatible** until a reviewed task says otherwise.
