# READ-ONLY: hall theme data tables (keys + DEFAULT_LIGHT) and the player's current theme id.
import sys
out = open(OUT, 'w')


def w(s):
    out.write(s[:1200] + '\n')


try:
    import shared
    import BigWorld
    lp = sys.modules.get('legacyProperties') or getattr(shared, 'legacyProperties', None)
    for n in sorted(dir(lp)):
        if 'Theme' in n and n.startswith('iter') and not n.endswith('RawData'):
            try:
                rows = list(getattr(lp, n)())
            except Exception as e:
                w('%s err %r' % (n, e))
                continue
            keys = [r[0] for r in rows]
            w('%s: %d rows keys=%r' % (n, len(rows), keys[:30]))
            if rows and hasattr(rows[0][1], 'DEFAULT_LIGHT'):
                w('   first DEFAULT_LIGHT=%r' % (rows[0][1].DEFAULT_LIGHT,))
    p = BigWorld.player()
    for a in ('dtsHallThemeID', 'hallThemeID', 'curHallThemeID'):
        if hasattr(p, a):
            w('player.%s = %r' % (a, getattr(p, a)))
except Exception:
    import traceback
    w(traceback.format_exc())
out.close()
