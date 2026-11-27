# RO-056: read-only entity check after a `space` trigger (run via bash tools/probe.sh).
# Writes ENT list, Globals.spaceEntity, and BattleGroundSpace 20001 circle/map fields.
import BigWorld

out = open(OUT, 'w')

def w(s):
    out.write(s + '\n')

for eid, e in sorted(BigWorld.entities.items()):
    w('ENT %s %s pos=%r' % (eid, type(e).__name__, tuple(getattr(e, 'position', ()) or ())))

try:
    import Globals
    se = getattr(Globals, 'spaceEntity', None)
    w('spaceEntity=%r type=%s' % (se, type(se).__name__ if se is not None else None))
    if se is not None:
        for n in ('mapID', 'gameStatus', 'circleStage', 'whiteCircleCenter', 'whiteCircleRadius',
                  'blueCircleCenter', 'blueCircleRadius', 'aliveNum', 'planeEntityIDs'):
            w('  space.%s=%r' % (n, getattr(se, n, '<none>')))
except Exception as e:
    w('Globals err %r' % (e,))

e20001 = BigWorld.entities.get(20001)
if e20001 is None:
    w('ent20001=MISSING')
else:
    w('ent20001 type=%s' % type(e20001).__name__)
    for n in ('mapID', 'gameStatus', 'circleStage', 'whiteCircleCenter', 'whiteCircleRadius',
              'blueCircleCenter', 'blueCircleRadius', 'aliveNum'):
        w('  ent20001.%s=%r' % (n, getattr(e20001, n, '<none>')))

p = BigWorld.player()
w('player type=%s spaceID=%r' % (type(p).__name__, getattr(p, 'spaceID', None)))
out.close()