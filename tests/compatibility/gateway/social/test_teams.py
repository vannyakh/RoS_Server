"""server/teams.py: invite, accept, leave, kick, ready and the leader's START for two players."""

import struct
import time

import pytest

import athlete_requests
import social
import teams

A, B = 111, 222
ADDR = {A: ("10.0.0.1", 1), B: ("10.0.0.1", 2)}


class Gate:
    def __init__(self):
        self._last_recv = {a: time.time() for a in ADDR.values()}
        self._last_bf = {a: b"k" for a in ADDR.values()}
        self._last_client_seq, self._in_battle, self._handoff_bf = {}, {}, {}
        self.sent, self.active = [], None

    def _send_bundle(self, addr, body, seq, bf_key):
        self.sent.append((addr, body))

    def _enter_addr(self, addr):
        self.active = addr

    def _hall_team_member(self, addr, in_world=True):
        assert in_world is False                    # lobby: no "GAMING" tag
        assert self.active == addr                  # the member's own account state is loaded
        return b"{M%d}" % addr[1]

    def _hall_theme(self, addr):
        assert self.active == addr
        return 270000 + addr[1], [500 + addr[1]]

    def _enter_battle(self, addr):
        pass


def call(method, args):
    return b"<%s>" % method.encode() + args


@pytest.fixture
def gate(tmp_path, monkeypatch):
    monkeypatch.setattr(social, "STORE", str(tmp_path / "social.json"))
    social.ONLINE.clear(), teams.TEAMS.clear(), teams.INVITES.clear()
    social.ONLINE.update(ADDR)
    return Gate()


def ask(gate, gid, name, args=b"", later=None):
    jobs = [] if later is None else later
    return teams.handle(gate, ADDR[gid], name, athlete_requests.Reader(args), gid, "P%d" % gid, call,
                        lambda delay, fn, *a: jobs.append((fn, a)))


def theme(owner):
    n = ADDR[owner][1]
    return (b"<onUpdateDtsHallThemeID>" + struct.pack("<i", 270000 + n)
            + b"<onUpdateHallVehicleAppearanceList>" + struct.pack("<Ii", 1, 500 + n))


def invite(gate, mode=1):
    return ask(gate, A, "inviteHallTeamPlayer",
               struct.pack("<Q", B) + athlete_requests.blob("P222") + struct.pack("<ii", mode, 0))


def join(gate):
    invite(gate)
    team = teams.team_of(A)["id"]
    gate.sent.clear()
    return ask(gate, B, "acceptHallTeamInvitation", struct.pack("<q", team))


def test_solo_requests_stay_with_the_solo_code(gate):
    assert ask(gate, A, "createHallTeam", struct.pack("<i", 1)) is None
    for name in ("getReadyForBattleGround", "matchBattleGround", "notReadyForBattleGround"):
        assert ask(gate, A, name) is None


def test_invite_reaches_the_friend(gate):
    reply = invite(gate)
    assert reply.startswith(b"<onEnterHallTeam>" + struct.pack("<iQb", 1, A, 1))
    team = teams.team_of(A)["id"]
    expected = (struct.pack("<q", team) + athlete_requests.blob("P111") + struct.pack("<iQi", 1, A, 30) + b"\x00")
    assert gate.sent == [(ADDR[B], b"<onInvitedToHallTeam>" + expected)]


def test_accept_puts_both_in_one_team(gate):
    reply = join(gate)
    assert reply == (b"<onEnterHallTeam>" + struct.pack("<iQbI", 1, A, 4, 2) + b"{M1}{M2}"
                     + struct.pack("<i", 1) + b"\x00\x00" + theme(A))       # the leader's background
    assert gate.sent == [(ADDR[A], b"<addHallTeamMember>{M2}")]
    assert list(teams.team_of(A)["members"]) == [A, B]
    assert gate.active == ADDR[B]                    # the requester's account is loaded again


def test_accept_needs_an_invitation(gate):
    ask(gate, A, "createHallTeam", struct.pack("<i", 1))
    assert ask(gate, B, "acceptHallTeamInvitation", struct.pack("<q", teams.team_of(A)["id"])) == b""
    assert teams.team_of(B) is None


def test_member_ready_then_leader_start_takes_both(gate):
    join(gate)
    gate.sent.clear()
    assert ask(gate, B, "getReadyForBattleGround") == b"<syncReadyState>" + struct.pack("<QBB", B, 1, 0)
    assert gate.sent == [(ADDR[A], b"<syncReadyState>" + struct.pack("<QBB", B, 1, 0))]
    assert ask(gate, A, "getReadyForBattleGround") is None
    assert ask(gate, B, "matchBattleGround") == b""           # only the leader starts
    gate.sent.clear()
    jobs = []
    assert ask(gate, A, "matchBattleGround", later=jobs) is None
    assert gate.sent[0][0] == ADDR[B] and gate.sent[0][1].startswith(b"<syncMatchState>")
    assert jobs == [(gate._enter_battle, (ADDR[B],))] and gate._handoff_bf[ADDR[B]] == b"k"


def test_leader_leaving_hands_over_and_kick_removes(gate):
    join(gate)
    gate.sent.clear()
    assert ask(gate, A, "leaveHallTeam") == b"<onLeaveHallTeam>" + theme(A)        # own background back
    assert gate.sent == [(ADDR[B], b"<delHallTeamMember>" + struct.pack("<Q", A)),
                         (ADDR[B], b"<updateHallTeamLeaderGID>" + struct.pack("<Q", B) + theme(B))]
    teams.TEAMS.clear()
    join(gate)
    assert ask(gate, B, "kickHallTeamMember", struct.pack("<Q", A)) == b""      # not the leader
    gate.sent.clear()
    assert ask(gate, A, "kickHallTeamMember", struct.pack("<Q", B)) == b"<delHallTeamMember>" + struct.pack("<Q", B)
    assert (ADDR[B], b"<onLeaveHallTeam>" + theme(B)) in gate.sent and teams.team_of(B) is None


def test_disconnected_teammate_is_dropped(gate):
    join(gate)
    gate._last_recv[ADDR[B]] = time.time() - social.ONLINE_SECS - 1
    assert ask(gate, A, "getReadyForBattleGround") is None
    assert list(teams.team_of(A)["members"]) == [A]


def test_leader_can_hand_over(gate):
    join(gate)
    gate.sent.clear()
    assert ask(gate, B, "assignHallTeamLeader", struct.pack("<Q", B)) == b""          # not the leader
    reply = ask(gate, A, "assignHallTeamLeader", struct.pack("<Q", B))
    expected = b"<updateHallTeamLeaderGID>" + struct.pack("<Q", B) + theme(B)
    assert reply == expected and gate.sent == [(ADDR[B], expected)]
    assert teams.team_of(A)["leader"] == B


def test_dance_is_shown_to_the_teammate(gate):
    join(gate)
    gate.sent.clear()
    assert ask(gate, B, "playHallTeamAnimation", struct.pack("<i", 900001)) == b""
    expected = (b"<syncHallTeamAnimation>" + struct.pack("<Q", B) + athlete_requests.blob("display_film_hello")
                + bytes(1))
    assert gate.sent == [(ADDR[A], expected)]
    gate.sent.clear()
    assert ask(gate, B, "playHallTeamAnimation", struct.pack("<i", 123)) == b"" and gate.sent == []
