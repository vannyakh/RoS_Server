# READ-ONLY: names/consts used by the client's package add-item code.
import sys
out = open(OUT, 'w')
def w(s): out.write(s + '\n')
def co(f):
    f = getattr(f, 'im_func', f)
    return getattr(f, 'func_code', None)
def dump(label, f):
    k = co(f) if f else None
    if k is None:
        w('%s: missing' % label); return
    w('== %s args=%r' % (label, list(k.co_varnames[:k.co_argcount])))
    w('names=%r' % list(k.co_names))
    w('consts=%r' % [x for x in k.co_consts if not hasattr(x, 'co_code')])
m = sys.modules.get('iPackage3')
c = getattr(m, 'iPackage3', None)
for n in ('onAddItem', 'onAddItemToTemporary', 'addItemToTemporaryUICall', '_onAddItemCommon'):
    dump('iPackage3.' + n, getattr(c, n, None) if c else None)
m2 = sys.modules.get('package_client.PackageClient3')
c2 = getattr(m2, 'DtsPackageClient3', None)
for n in ('onAddItem', 'canAddItem'):
    dump('DtsPackageClient3.' + n, getattr(c2, n, None) if c2 else None)
out.close()
