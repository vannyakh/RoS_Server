# READ-ONLY: for test entities 21000+k created with one tagged property (index k, INT32 value
# 0x11000000+k), report which attribute received the value. Maps the client's property indices.
import BigWorld
out = open(OUT, 'w')
def w(s): out.write(s + '\n')
present = 0
for k in range(0, 160):
    e = BigWorld.entities.get(21000 + k)
    if e is None:
        continue
    present += 1
    want = 0x11000000 + k
    hits = []
    for n in dir(e):
        if n.startswith('__'):
            continue
        try:
            v = getattr(e, n)
        except Exception:
            continue
        if isinstance(v, (int, long)) and v == want:
            hits.append(n)
        elif isinstance(v, float) and abs(v - want) < 1:
            hits.append(n + '(float)')
    w('k=%d %s %r' % (k, type(e).__name__, hits))
w('present=%d' % present)
out.close()
