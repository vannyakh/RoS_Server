# READ-ONLY: what the player's base mailbox object exposes (type, attributes, docs),
# to find the client's own exposed base-method order. Calls nothing on the server.
import BigWorld

out = open(OUT, 'w')
p = BigWorld.player()
out.write('player=%r type=%r\n' % (p, type(p)))
b = getattr(p, 'base', None)
out.write('base=%r type=%r\n' % (b, type(b)))
try:
    names = dir(b)
except Exception as e:
    names = ['dir failed %r' % e]
out.write('dir(base) n=%d\n%r\n' % (len(names), names[:2000]))
for k in ('__members__', '__methods__', '__doc__'):
    try:
        out.write('base.%s=%r\n' % (k, getattr(b, k)))
    except Exception as e:
        out.write('base.%s !! %r\n' % (k, e))
tp = type(b)
out.write('type dir=%r\n' % dir(tp))
for a in dir(BigWorld):
    if any(w in a.lower() for w in ('def', 'method', 'desc', 'expos')):
        out.write('BigWorld.%s=%r\n' % (a, getattr(BigWorld, a)))
out.close()
