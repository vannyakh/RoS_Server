# READ-ONLY: contents of the player's pickup package.
import BigWorld
out = open(OUT, 'w')
def w(s): out.write(s + '\n')
p = BigWorld.player()
pk = p.dtsItemPackage
w('type=%r' % type(pk))
names = [n for n in dir(pk) if not n.startswith('__')]
w('attrs=%r' % names[:80])
for n in ('itemList', 'items', 'itemDict', 'allItems', 'getAllItems', 'getItems', 'itemsDict', '_items', 'layoutInfo'):
    v = getattr(pk, n, '<none>')
    try:
        if callable(v): v = v()
    except Exception as e:
        v = 'call failed %r' % (e,)
    w('%s=%r' % (n, v))
for n in ('packageCapacity', 'PackageCapacity', '_packageCapacity', 'getDtsPackageLeftCapacity', 'getUsedGridNum', 'getItemCnt', 'isPackageEmpty'):
    v = getattr(pk, n, '<none>')
    try:
        if callable(v): v = v()
    except Exception as e:
        v = 'call failed %r' % (e,)
    w('%s=%r' % (n, v))
w('owner=%r ownerID=%r' % (getattr(pk, 'owner', None), getattr(pk, 'ownerID', None)))
out.close()
