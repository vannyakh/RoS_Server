# READ-ONLY: look for client APIs that describe entity types / property order.
import BigWorld

out = open(OUT, 'w')
def w(s): out.write(s + '\n')

w('BigWorld: %r' % [n for n in dir(BigWorld) if any(k in n.lower() for k in ('type', 'desc', 'def', 'prop', 'entit', 'class'))])
p = BigWorld.player()
cls = type(p)
w('player class attrs: %r' % [n for n in dir(cls) if any(k in n.lower() for k in ('desc', 'propert', 'typeid', 'entitytype', '_type'))][:80])
for n in ('__entityType__', 'entityType', '_entityType', 'typeID', 'entityTypeID', 'className'):
    w('player.%s=%r' % (n, getattr(p, n, '<none>')))
for n in dir(BigWorld):
    if any(k in n.lower() for k in ('type', 'desc', 'def', 'prop')):
        o = getattr(BigWorld, n)
        w('BigWorld.%s = %r doc=%r' % (n, o, getattr(o, '__doc__', None)))
out.close()
