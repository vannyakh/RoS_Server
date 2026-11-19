# READ-ONLY: upper-case string constants used by the supply UIs and iSupplement (the keys
# they read from the server's supplement info). Calls nothing.
import sys
import types
out = open(OUT, 'w')
keys = {}


def walk(code, where, depth=0):
    for c in code.co_consts:
        if isinstance(c, str) and c.isupper() and 3 < len(c) < 40 and '_' in c:
            keys.setdefault(c, set()).add(where)
        elif isinstance(c, types.CodeType) and depth < 4:
            walk(c, where, depth + 1)


for mname in ('ui.UIAdvanceSupplyPackage', 'ui.UISupplyPackage', 'iSupplement', 'ui.UISupplyController', 'ui.UIMonthlySupplyPackage', 'supplement_utils'):
    mod = sys.modules.get(mname)
    if mod is None:
        continue
    for name, obj in vars(mod).items():
        if isinstance(obj, types.FunctionType):
            walk(obj.func_code, mname + '.' + name)
        elif isinstance(obj, (type, types.ClassType)):
            for an, av in vars(obj).items():
                f = getattr(av, 'func_code', None) or getattr(getattr(av, '__func__', None), 'func_code', None)
                if f is not None:
                    walk(f, '%s.%s' % (mname, an))
for k in sorted(keys):
    out.write('%s  %s\n' % (k, sorted(keys[k])[:4]))
out.close()
