# RosGG-Server-v2 → bigworld_gateway sync (2026-11-27)

## What was synced
- Source: RosGG-Server-v2 `main` at `b967a5a` (already up to date with `origin/main` after `git fetch`).
- Previous sync point: RosGG `407ad11`. Before this change, `bigworld_gateway/` matched `407ad11`
  blob for blob. The only extra files on the RoS_Server side were captures and keys, which are not synced.
- New upstream work: `82fb509` (lobby mail/rank/topup/vip, match room/results, battle world,
  Event panel activities, parachute phases, 53 Frida payloads, gameplay docs) and `b967a5a`
  (LAN IP in `config.cmd` / `server/real/server_list_ad.local.txt`, set to this PC's current IP).
- 92 files (83 added, 9 modified, 0 deleted). After the apply, every file was hash-checked
  against `b967a5a`, and all of them matched.

## Sync tool
`scripts/sync_rosgg_gateway.py` (`init`, `status`, `pull`, `push`) uses a three-way rule per file.
The base is the RosGG commit recorded in `bigworld_gateway/UPSTREAM_SYNC.json`. Files changed on
both sides are reported as conflicts and left alone. Keys, `.env`, captures, logs,
`saved_accounts.json` and APKs are never copied. The tool never commits in either repository.
Usage is in `bigworld_gateway/README.md` under "Sync with RosGG-Server-v2".

```
> python scripts/sync_rosgg_gateway.py status   (ROSGG_SERVER_V2=..\Server\ros_server_v2)
base b967a5a87c  upstream HEAD = b967a5a87c
RosGG changes to pull: 0
RosGG deletions to pull: 0
RoS_Server-only changes (push candidates): 0
conflicts (changed on both sides): 0
```

## Tests
`pytest tests/unit -k "gateway or sync_rosgg" tests/compatibility/gateway`

| Run | Result |
|---|---|
| Before sync (HEAD `192548d`, separate worktree) | 18 failed, 1551 passed |
| After sync, before test updates | 21 failed, 1553 passed |
| After sync and test updates | 18 failed, 1556 passed |
| After fixing the 18 pre-existing failures | **0 failed, 1574 passed** |

The 18 failures had been there before the sync. They were test-side bugs:
- `test_store_linked.py` (13), `test_gateway_store_listings.py` (2) and `test_gateway_lobby_theme.py` (1):
  the fake RoS_Server API took only `(method, path, body)`, but `account_link._call` also passes
  `retry_stale=`. The fakes now accept the keyword. The store `FakeApi` also records it in `retry_stale`.
- `test_login_stream_cache.py` (2, failed some of the time): the startup fixture reloaded only five
  gateway modules. `training_event` kept the previous test's `athlete_requests`, so the patched fixed
  `game_now` did not reach it. The Spec Train `endTime` then followed the live clock and changed by one
  second between builds. The fixture now reloads every loaded module from `bigworld_gateway/server`.
  `tests/compatibility/gateway/startup` passed 3 runs in a row (6 passed each time).

The sync caused three failures. In each case the test was out of date, not the code:
- `test_login_stream_method_order_snapshot` and `test_create_character_sends_the_lobby_stream_before_enter_hall`:
  the login stream now also sends the six Event panel activity syncs, `syncTelkomseOpenStatus` and
  `onSetPortrait`. The snapshot was updated. The supply order test still passes without changes.
- `test_suicide_inbound_triggers_end`: RosGG moved the start of the BattleGroundAvatar exposed index
  shift from 60 to 180. The measurement behind it: `requestGetOffPlane` (77) and `verifyClientValue`
  (150) arrive unshifted. `suicideFromClient` (raw 61) therefore arrives as `0xBC` with sub-byte 1, not 3.
  The test now uses sub-byte 1 and checks the decode.

New sync tool tests: `tests/unit/test_sync_rosgg_gateway.py`, 5 passed.

Registry: `validate_agent_registry.py` gave `OK: 13 agents, 128 tasks`. `validate_project_management.py`
gave `OK: 128 tasks, 12 discoveries, 43 compatibility features`.

## Not done / not verified
- Not run on a device. The new lobby screens and match flow have not been checked in LDPlayer.
- Nothing is committed. A human reviews and merges.
- `bigworld_gateway/README.md` now refers to `scripts/sync_rosgg_gateway.py`, which exists only in
  RoS_Server. A `push` would copy that README into RosGG.

## Review and QA follow-up (same day)

### Security
- `delMails` ran `pickle.loads` on client bytes (remote code execution from UDP :25000). It now decodes
  with `server/client_pickle.py`, which refuses every class or function reference and data over 64 KiB.
  Tests: `tests/unit/test_gateway_client_pickle.py`, plus the `delMails` tests in `lobby_new/`.
- `pytest.ini` gained `testpaths = tests`. Without it, plain `pytest` collected a Frida payload.

### Bugs from the offline QA check, all fixed
| # | Bug | Fix |
|---|---|---|
| 1 | `extract/daily_activity.json` is missing (RosGG has no copy either), so every Activity Points call raised `FileNotFoundError` | `lobby_events.activity_table()` falls back to a shape-only table: 14 activities and 30/60/90/120 and 300/600 tiers, the client's fresh-day values. Nothing can be claimed until the real table is extracted. Login bytes are unchanged. |
| 2 | `getActivityReward` / `getDailyActivityReward` / `getWeeklyActivityReward` had no handler | `GateUDP._activity_reward` handles them, with state per account (`activity:<gid>`). Props are settled on RoS_Server and then granted. When nothing can be claimed, the reply is the unchanged state. Login now sends the stored state. |
| 3 | Top-up credited heuristic amounts (121 of 121 client packs were wrong), and the `lobby_topup` branch could never be reached | `_complete_private_pay` uses `lobby_topup.grant` (AMOUNT + NORMAL_PRESENT from `pay_goods.json`) first, and the heuristic only for unknown ids. The unreachable `_topup_reply` was removed and the `lobby_topup` docstring corrected. |
| 4 | Two mail systems: `delMails` went to `lobby_mail`, the other four requests to RoS_Server | When linked, all five go to RoS_Server; `delMails` deletes each id through `account_link.delete_mail`. When not linked, all five use the local `lobby_mail.json` mailbox. `LOCAL_MAIL=off` restores the old empty mailbox, and the existing RoS_Server mail tests set it. |
| 5 | Sign-in state was stored under one global `signin` key | It is now stored per account, under `signin:<gid>`. |

Also: `lobby_events.week_of` no longer uses the deprecated `utcfromtimestamp`.

Tests: `pytest tests/compatibility/gateway tests/unit -k "gateway or lobby_new or sync_rosgg"`
gave **1662 passed, 1 xfailed**. The one strict xfail is the real `daily_activity.json` data, which
needs a read-only Frida dump of `iterDailyActivityData` / `getActivityRewardData` on a device.

Still to do:
- These fixes exist only in RoS_Server. `python scripts/sync_rosgg_gateway.py push` copies them into
  the RosGG working tree for the other team to commit.
- Nothing has been checked on a device yet. The running LDPlayer session uses RosGG's copy of the
  gateway.
- A previous global `signin` value is not carried over, so each account starts its sign-in streak again.
