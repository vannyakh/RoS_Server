# READ-ONLY: list Robot* entities and BattleGroundSpace.aliveNum (RO-068 / RO-069).
# Same OUT-file pattern as entities_state.py for tools/probe.sh.
import BigWorld

out = open(OUT, "w")


def w(s):
    out.write(s + "\n")


rows = []
for eid, e in sorted(BigWorld.entities.items()):
    cls = type(e).__name__
    if "Robot" not in cls:
        continue
    pos = tuple(getattr(e, "position", ()) or ())
    rows.append(eid)
    w(
        "ROBOT %s %s nickname=%r characterType=%r hp=%r maxHp=%r deadInGame=%r "
        "robotVisible=%r battleState=%r planeID=%r pos=%r"
        % (
            eid,
            cls,
            getattr(e, "nickname", "<none>"),
            getattr(e, "characterType", "<none>"),
            getattr(e, "hp", "<none>"),
            getattr(e, "maxHp", "<none>"),
            getattr(e, "deadInGame", "<none>"),
            getattr(e, "robotVisible", "<none>"),
            getattr(e, "battleState", "<none>"),
            getattr(e, "planeID", "<none>"),
            pos,
        )
    )

w("ROBOT_COUNT %s" % len(rows))
try:
    import Globals

    se = getattr(Globals, "spaceEntity", None)
    w("spaceEntity=%r" % (se,))
    if se is not None:
        w("space.aliveNum=%r" % (getattr(se, "aliveNum", "<none>"),))
        w("space.mapID=%r" % (getattr(se, "mapID", "<none>"),))
        w("space.gameStatus=%r" % (getattr(se, "gameStatus", "<none>"),))
except Exception as exc:
    w("Globals err %r" % (exc,))

if not rows:
    w("ROBOT_NONE (expected until RO-069 spawns type 58)")
out.close()
