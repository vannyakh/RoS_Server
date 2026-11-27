# System mail in the original client (build 1.610637.617289)

Read with the read-only payloads `client/frida/payloads/mail_discover.py`, `mail_ui_fields.py` and
`mail_types.py` on LDPlayer, 2026-11-26. Names and string constants only; nothing here was seen on
the wire from a real server.

## Methods (Athlete, `extract/entities_out/556_cef42fce.bin`)

| Direction | Method | Args |
|---|---|---|
| client -> base | `requestMails` | none |
| client -> base | `requestMailDetail` | INT32 mailID |
| client -> base | `getAwardFromMail` | INT32 mailID (the UI calls `requestMails` right after) |
| client -> base | `deleteMail` | INT32 mailID |
| base -> client | `onMailUpdate` | PYTHON mails, PYTHON topMails |
| base -> client | `onLoadMailDetail` | INT32 mailID, STRING content, PYTHON extraInfo |
| base -> client | `onLoadMailDetailFailed` | INT32 mailID (shows I_DELETED_MAIL_CONTENT) |
| base -> client | `onGetAwardFromMail` | PYTHON props (list of prop ids, shown by `UISystemMail.showMailResult` -> UIItemDisplay) |

Handlers live in `iChat` (`chatCache.mailsCache`), the screen is `ui.UISystemMail`.

## Mail list entry (`iChat.onMailUpdate`, `UISystemMail.refreshMailList`)

A dict per mail. Keys the client reads: `mailID`, `type`, `unread`, `title`, `when` (shown with
`time.strftime('%m-%d %H:%M', localtime(when))`), `deadline` (rest-time text), `mail_abstract`,
`sender`. `onMailUpdate` reverses `mails` before caching; `topMails` is a second list shown pinned.

`SysMailTypeEnum`: TXT 0, PROPS 1, NPC 2, TXT_PRIVATE 3, PROPS_PRIVATE 4, LEGION 5, QUIZ 6,
ROS2_TXT 1000, ROS2_PROPS 1001, ROS2_TXT_PRIVATE 1002, ROS2_PROPS_PRIVATE 1003,
ROS2_PROPS_IN_BATTLE 1004. PROPS / PROPS_PRIVATE show the gift icon.

## Detail (`UISystemMail.onLoadMailDetail(mailID, content, extraInfo, failed)`)

Locals: `rewardTitle, i, propID, cnt, propSmallID, pic`. Constants: `'props', 1, 7, 'prop_%d',
'count', 'x', 'prop', 'gid', 'unread'`. So `extraInfo['props']` is read for `i in xrange(1, 7)`
(at most 6 attachments) as `prop_%d` widgets, each with a prop id and `count`. The exact container
(list of `[propID, cnt]`, or dicts with `prop`/`count`) is not confirmed: check the claim button and
icons in game. `content` may hold `#E...#e` link markup.

## Not confirmed

- The exact `extraInfo['props']` shape (see above).
- Whether the client wants `unread` as bool or int (both are falsy-compatible).
- `topMails` content (send `[]`).
