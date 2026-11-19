# READ-ONLY: fields of season 21 (NewSeason + BountySeason) data rows.
import sys
out = open(OUT, 'w')
def w(s): out.write(s[:800] + '\n')
def dump(label, obj):
    names = [n for n in dir(obj) if not n.startswith('_')]
    w('== %s' % label)
    for n in names:
        try:
            v = getattr(obj, n)
        except Exception:
            continue
        if not callable(v):
            w('   %s = %r' % (n, v))
try:
    import shared
    lp = sys.modules.get('legacyProperties') or getattr(shared, 'legacyProperties', None)
    dump('NewSeason 21', dict(lp.iterNewSeasonData())[21])
    dump('NewSeason 20', dict(lp.iterNewSeasonData())[20])
    dump('BountySeason 21', dict(lp.iterBountySeasonData())[21])
except Exception:
    import traceback; w(traceback.format_exc())
out.close()
