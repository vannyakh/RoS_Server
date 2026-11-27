"""Lobby mailbox (iMail) for the original client.

Mails come from lobby_mail.json (editable: id, type, title, sender, content, props, deadline_days).
Per-account state (read / claimed / deleted mail ids) lives in saved_accounts.json under
"mail:<gid>", handed in by ros_server as load/save callables.

Client side (entities/iChat.py, ui/UISystemMail.py, read with client/frida/payloads/mail_*.py):
  requestMails()               -> onMailUpdate(PYTHON mails, PYTHON topMails)
      mail dict: mailID, type (SysMailTypeEnum: TXT 0, PROPS 1), title, sender, when (epoch),
      deadline (epoch, 0 = none), unread (bool). topMails = list of pinned mail ids.
  requestMailDetail(INT32 id)  -> onLoadMailDetail(INT32 id, STRING content, PYTHON extra)
      extra["props"] = [[propID, count], ...]; the Get button shows while it is non-empty.
  getAwardFromMail(INT32 id)   -> onGetAwardFromMail(PYTHON {propID: count}); the client then asks requestMails.
      Never send it with an empty dict (generateArgsForUIItemDisplay IndexError hides the lobby UI).
  "deadline" only when the mail expires: with the key present the list always shows "LEFT ...".
  deleteMail(INT32 id) / delMails(PYTHON ids) -> onMailUpdate with the remaining mails.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
MAIL_FILE = os.path.join(HERE, "lobby_mail.json")

TXT, PROPS = 0, 1

DEFAULT_MAILS = [
    {"id": 1, "type": TXT, "title": "Welcome to the private server", "sender": "RoS Server",
     "content": "Welcome back, survivor!\nThis is a preservation server for Rules of Survival "
                "1.610637.617289. Lobby, store, supply, wardrobe and matches are being restored step by step.",
     "props": [], "deadline_days": 0},
    {"id": 2, "type": PROPS, "title": "Comeback gift", "sender": "RoS Server",
     "content": "Thanks for playing. Here is a small gift to get you started.",
     "props": [[120901, 1], [2990236, 1], [250175, 1]], "deadline_days": 0},
]


def award_result(props):
    """onGetAwardFromMail argument: {propID: count} (UIItemDisplay builds a Counter from it;
    a list of pairs raises 'unhashable type: list')."""
    out = {}
    for p, c in props:
        out[int(p)] = out.get(int(p), 0) + int(c)
    return out


def load_mails():
    """Mail definitions; writes the defaults to lobby_mail.json the first time."""
    if not os.path.exists(MAIL_FILE):
        with open(MAIL_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_MAILS, f, indent=2, ensure_ascii=False)
        return [dict(m) for m in DEFAULT_MAILS]
    with open(MAIL_FILE, "r", encoding="utf-8-sig") as f:
        return json.load(f)


class Mailbox:
    def __init__(self, load_state, save_state, now):
        """load_state() -> dict or None, save_state(dict); now = game clock (epoch seconds)."""
        self._load, self._save, self.now = load_state, save_state, int(now)
        st = load_state() or {}
        self.state = {k: set(st.get(k, [])) for k in ("read", "claimed", "deleted")}
        self.first_seen = int(st.get("first_seen") or self.now)
        if not st.get("first_seen"):
            self._persist()

    def _persist(self):
        out = {k: sorted(v) for k, v in self.state.items()}
        out["first_seen"] = self.first_seen
        self._save(out)

    def _visible(self):
        mails = []
        for m in load_mails():
            mid = int(m["id"])
            days = int(m.get("deadline_days") or 0)
            deadline = self.first_seen + days * 86400 if days else 0
            if mid in self.state["deleted"] or (deadline and deadline < self.now):
                continue
            mails.append((m, deadline))
        return mails

    def _find(self, mail_id):
        for m, deadline in self._visible():
            if int(m["id"]) == mail_id:
                return m
        return None

    def _props(self, m):
        if int(m["id"]) in self.state["claimed"]:
            return []
        return [[int(p), int(c)] for p, c in m.get("props", [])]

    def mail_list(self):
        """List for onMailUpdate, newest first."""
        out = []
        for m, deadline in self._visible():
            mid = int(m["id"])
            d = {"mailID": mid, "type": int(m.get("type", TXT)), "title": m.get("title", ""),
                 "sender": m.get("sender", ""), "when": self.first_seen - 3600 + mid * 60,
                 "unread": mid not in self.state["read"]}
            if deadline:                    # the client shows "LEFT ..." whenever the key exists
                d["deadline"] = deadline
            out.append(d)
        out.sort(key=lambda d: -d["mailID"])
        return out

    def unread_count(self):
        return sum(1 for d in self.mail_list() if d["unread"])

    def detail(self, mail_id):
        """(content, extra) for onLoadMailDetail, or None when the mail is gone. Marks it read."""
        m = self._find(mail_id)
        if m is None:
            return None
        self.state["read"].add(mail_id)
        self._persist()
        return m.get("content", ""), {"props": self._props(m)}

    def claim(self, mail_id):
        """Prop list [[id, count]] granted by this mail. The client shows Claim on every mail
        (it is the only button), so a mail with nothing left to claim is removed instead."""
        m = self._find(mail_id)
        if m is None:
            return []
        props = self._props(m)
        self.state["claimed"].add(mail_id)
        self.state["read"].add(mail_id)
        if not props:
            self.state["deleted"].add(mail_id)
        self._persist()
        return props

    def delete(self, mail_ids):
        """Delete mails; a mail with unclaimed props is kept (the client asks to claim first)."""
        for mid in mail_ids:
            m = self._find(int(mid))
            if m is not None and not self._props(m):
                self.state["deleted"].add(int(mid))
        self._persist()
