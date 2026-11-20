# READ-ONLY: list client entities, Globals.spaceEntity and the battle-flow state of the player.
import BigWorld

out = open(OUT, 'w')
def w(s): out.write(s + '\n')

for eid, e in sorted(BigWorld.entities.items()):
    w('ENT %s %s pos=%r' % (eid, type(e).__name__, tuple(getattr(e, 'position', ()) or ())))
try:
    import Globals
    se = getattr(Globals, 'spaceEntity', None)
    w('spaceEntity=%r' % (se,))
    if se is not None:
        for n in ('mapID', 'gameStatus', 'circleStage', 'whiteCircleCenter', 'whiteCircleRadius', 'blueCircleCenter',
                  'blueCircleRadius', 'blueCircleStartCenter', 'blueCircleStartRadius', 'startTime', 'getOnPlaneTime',
                  'waitBornStatus', 'waitBornLeftTime', 'planeEntityIDs', 'aliveNum'):
            w('  space.%s=%r' % (n, getattr(se, n, '<none>')))
except Exception as e:
    w('Globals err %r' % (e,))
se2 = BigWorld.entities.get(20001)
if se2 is not None:
    for n in ('mapID', 'socketHint', 'gameStartTime', 'gameStatus', 'gameEnterType', 'circleStage', 'whiteCircleCenter',
              'whiteCircleRadius', 'blueCircleCenter', 'blueCircleRadius', 'blueCircleStartRadius', 'blueCircleStartCenter'):
        w('  ent20001.%s=%r' % (n, getattr(se2, n, '<none>')))
p = BigWorld.player()
for n in ('battleState', 'planeID', 'flightStage', 'fallPhase', 'glidePhase', 'leftPlayerNumOnPlane', 'isInPoisonArea', 'spaceID'):
    w('player.%s=%r' % (n, getattr(p, n, '<none>')))
w('player.position=%r' % (tuple(p.position),))
out.close()
