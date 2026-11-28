"""Hold Athlete.enterHall until the client's game thread is responsive.

Existing-account login: the gateway sends the onLogin/lobby bundle, then enterHall. On LDPlayer the
client sometimes starts loading the tutorial map's Level right then and its game thread blocks for
12-16 s. Network messages that arrive during the block are run as soon as it ends, before the
Level has registered its "Scene" GameObject. enterHall then runs PlayerAthlete._realEnterHall,
whose GameObject.Find('Scene').GetComponent('SceneSystem').loadHallScene(...) fails with
"AttributeError: 'NoneType' object has no attribute 'GetComponent'" (Athlete.py line 711), and the
client stays on the menu. In the runs that worked, Scene was registered before enterHall ran.

The client ACKs reliable packets only while its game thread runs, so ACK timing shows whether it is
blocked. HallGate sends enterHall only after every reliable packet is ACKed and the client keeps
ACKing small empty reliable probes promptly for `settle` seconds. A block resets the settle window.
After `max_wait` seconds enterHall is sent anyway (old behaviour).
"""

WAIT, PROBE, SEND = "wait", "probe", "send"


class HallGate:
    def __init__(self, now, settle=1.0, busy_after=0.25, max_wait=60.0):
        self.t0 = now
        self.settle = settle
        self.busy_after = busy_after
        self.max_wait = max_wait
        self.quiet_since = None
        self.blocked = False        # seen a reliable packet unacked for longer than busy_after

    def step(self, now, oldest_unacked_age):
        """oldest_unacked_age: seconds since the oldest unacked reliable packet was first sent,
        or None when everything is ACKed. Returns WAIT, PROBE (send one empty reliable packet)
        or SEND (send enterHall now)."""
        if now - self.t0 >= self.max_wait:
            return SEND
        if oldest_unacked_age is not None:
            if oldest_unacked_age > self.busy_after:
                self.blocked = True
                self.quiet_since = None
            return WAIT
        if self.quiet_since is None:
            self.quiet_since = now
            return PROBE
        if now - self.quiet_since >= self.settle:
            return SEND
        return PROBE
