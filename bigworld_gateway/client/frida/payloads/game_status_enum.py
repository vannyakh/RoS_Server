# READ-ONLY: BattleGroundGameStatusEnum, PlaneWorkMode, PlayerState values and the map's PREPARE_TIME.
import sys
out = open(OUT, 'w')
for modname, mod in sorted(sys.modules.items()):
    if mod is None:
        continue
    for name in ('BattleGroundGameStatusEnum', 'PlaneWorkMode', 'PlayerState'):
        v = getattr(mod, name, None)
        if v is not None and not callable(getattr(v, '__call__', None)) or (v is not None and hasattr(v, '__dict__')):
            try:
                d = dict((a, b) for a, b in vars(v).items() if not a.startswith('_') and isinstance(b, (int, long)))
            except Exception:
                continue
            if d:
                out.write('%s.%s = %r\n' % (modname, name, d))
import BigWorld
sp = BigWorld.entities.get(20001)
md = getattr(sp, 'mapData', None)
for k in ('PREPARE_TIME', 'MATCH_MIN_NUM', 'CENTER'):
    out.write('mapData.%s = %r\n' % (k, getattr(md, k, None) if md is not None else None))
out.close()
