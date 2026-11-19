# READ-ONLY: every client function that reads availSupplementDict (names, consts, and a
# disassembly around each use) to learn the value shape the server must send.
import sys
import types
import dis
import StringIO

out = open(OUT, 'w')
hits = []


def walk(code, path, depth=0):
    if 'availSupplementDict' in code.co_names or 'availSupplementDict' in code.co_varnames:
        hits.append((path, code))
    if depth < 3:
        for c in code.co_consts:
            if isinstance(c, types.CodeType):
                walk(c, path + '.' + c.co_name, depth + 1)


for mname, mod in sorted(sys.modules.items()):
    if mod is None:
        continue
    try:
        items = list(vars(mod).items())
    except Exception:
        continue
    for name, obj in items:
        try:
            if isinstance(obj, types.FunctionType):
                walk(obj.func_code, '%s.%s' % (mname, name))
            elif isinstance(obj, (type, types.ClassType)) and getattr(obj, '__module__', None) == mname:
                for an, av in vars(obj).items():
                    f = getattr(av, 'func_code', None) or getattr(getattr(av, '__func__', None), 'func_code', None)
                    if f is not None:
                        walk(f, '%s.%s.%s' % (mname, name, an))
        except Exception:
            pass
for path, code in hits:
    out.write('== %s args=%r\n  names=%r\n  consts=%r\n' % (path, code.co_varnames[:code.co_argcount], code.co_names[:60], [c for c in code.co_consts if not isinstance(c, types.CodeType)][:30]))
out.close()
