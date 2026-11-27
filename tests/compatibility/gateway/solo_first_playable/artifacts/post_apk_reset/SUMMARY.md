# Post APK reset function test
Time: 2026-11-27T00:38:32.3924179+07:00

## Setup
- pm clear com.netease.chiji: Success
- loginapp.pubkey: re-pushed
- Duplicate dns/ros killed; start.cmd restarted
- LDPlayer net.dns1 set to 192.168.180.137 (was 192.168.180.23)

## Results
| Check | Result |
|-------|--------|
| Private-Server menu | OK |
| PLAY / Mercury login | OK after DNS fix (earlier: Failed to connect) |
| Account.handshake | OK |
| enterHall | OK (Existing account Kkkkkkk) |
| Lobby UI + character model | OK (visible with green hall vehicle) |
| Friend list requests | OK (5) |
| queryAvailableActivity stub | OK (3, empty catalogue) |
| Athlete Error handling | 0 |
| createHallTeam / START battle | not exercised |
| Mail claim | not exercised |

Artifacts: tests/compatibility/gateway/solo_first_playable/artifacts/post_apk_reset/
