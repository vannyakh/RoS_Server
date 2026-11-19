# READ-ONLY: find client code that reads or sets the player portrait and the string
# constants around it (icon paths, URL prefixes). Writes to OUT; changes nothing.
import sys
import types

out = open(OUT, 'w')


def consts_of(code, depth=0):
    found = []
    for c in code.co_consts:
        if isinstance(c, types.CodeType) and depth < 3:
            found.extend(consts_of(c, depth + 1))
        elif isinstance(c, basestring) and 0 < len(c) < 160:
            found.append(c)
    return found


def walk(code, path, depth=0):
    names = set(code.co_names) | set(code.co_varnames)
    text = ' '.join(n.lower() for n in names)
    if 'portrait' in text or 'setportrait' in text:
        strs = [s for s in consts_of(code) if any(k in s.lower() for k in ('portrait', 'head', 'icon', 'http', '.png', 'png', 'url', 'res', 'gui', 'ui/'))]
        out.write('%s  names=%s\n    strs=%r\n' % (path, sorted(n for n in names if any(k in n.lower() for k in ('portrait', 'head', 'icon', 'url', 'pic', 'image', 'tex')))[:30], strs[:40]))
    if depth < 4:
        for c in code.co_consts:
            if isinstance(c, types.CodeType):
                walk(c, path + '.' + c.co_name, depth + 1)


count = 0
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
    count += 1
out.write('modules scanned: %d\n' % count)
out.close()
