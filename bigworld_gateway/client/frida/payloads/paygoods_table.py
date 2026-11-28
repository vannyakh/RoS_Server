# READ-ONLY: dump the client's PayGoods table (Top-Up packs: goods id -> diamonds, bonus, price) as
# repr'd dicts, one per line. Calls no game method that changes state.
import shared.tables as T
out = open(OUT, 'w')
pg = T.PayGoods
for k in sorted(pg.keys()):
    item = pg.get(k)
    try:
        d = dict(item)
    except Exception:
        d = dict((a, getattr(item, a)) for a in dir(item) if not a.startswith('_') and not callable(getattr(item, a)))
    out.write('%r\t%r\n' % (k, d))
out.close()
