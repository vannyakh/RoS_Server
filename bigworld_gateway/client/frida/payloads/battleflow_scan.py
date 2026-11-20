# READ-ONLY: map the client's battle flow (battle state, plane, safe zone / poison circle).
# Lists matching modules, constants and player/entity methods. Calls no game method.
import sys, types

out = open(OUT, 'w')
def w(s): out.write(s + '\n')

KEYS = ('plane', 'poison', 'safety', 'circle', 'battlestate', 'flight', 'parachute', 'airline', 'safearea', 'saferegion')

mods = sorted(k for k, v in sys.modules.items() if v is not None)
w('# modules matching')
for k in mods:
    if any(s in k.lower() for s in KEYS):
        w('MOD ' + k)

w('# constants')
for k in mods:
    mod = sys.modules[k]
    try:
        items = list(vars(mod).items())
    except Exception:
        continue
    for n, v in items:
        u = n.upper()
        if isinstance(v, (int, long, float, str)) and any(s in u for s in ('BATTLE_STATE', 'BATTLESTATE', 'FLIGHT_STAGE', 'FLIGHTSTAGE', 'POISON', 'PLANE', 'SAFE_AREA', 'CIRCLE')):
            w('CONST %s.%s = %r' % (k, n, v))
        if (isinstance(v, type) or type(v).__name__ == 'classobj') and any(s in n.lower() for s in ('battlestate', 'flightstage', 'poison', 'planestate', 'circle')):
            w('CLASS %s.%s %r' % (k, n, dict((a, b) for a, b in vars(v).items() if not a.startswith('__') and isinstance(b, (int, long, float, str)))))

w('# player / plane classes: matching methods')
import BigWorld
p = BigWorld.player()
w('player type %s module %s' % (type(p).__name__, type(p).__module__))
for cls in type(p).__mro__:
    for n in sorted(vars(cls)):
        l = n.lower()
        if any(s in l for s in ('battlestate', 'plane', 'poison', 'circle', 'flight', 'parachute', 'safety', 'jump', 'born', 'countdown', 'set_')):
            if l.startswith('set_') and not any(s in l for s in ('battle', 'plane', 'flight', 'poison', 'born', 'left')):
                continue
            w('M %s.%s' % (cls.__name__, n))
w('battleState=%r planeID=%r flightStage=%r position=%r spaceID=%r' % (
    getattr(p, 'battleState', None), getattr(p, 'planeID', None), getattr(p, 'flightStage', None),
    tuple(p.position), getattr(p, 'spaceID', None)))
out.close()
