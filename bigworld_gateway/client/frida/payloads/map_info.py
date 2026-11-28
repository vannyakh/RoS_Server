# READ-ONLY: map 700 geometry from the space entity's mapData (size, centre, plane routes) and the minimap config.
import BigWorld, sys
out = open(OUT, 'w')
sp = BigWorld.entities.get(20001)
md = getattr(sp, 'mapData', None)
for a in sorted(dir(md)):
    if a.isupper():
        v = getattr(md, a)
        r = repr(v)
        if any(s in a for s in ('SIZE', 'CENTER', 'RANGE', 'PLANE', 'ROUTE', 'BORN', 'MAP', 'CIRCLE', 'WIDTH', 'HEIGHT', 'BOUND', 'ORIGIN', 'SCALE', 'AREA', 'POS', 'TIME')):
            out.write('%s = %s\n' % (a, r[:300]))
out.close()
