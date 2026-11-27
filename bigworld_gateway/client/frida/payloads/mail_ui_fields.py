# READ-ONLY: field names the mail UI reads from a mail record, the detail extraInfo and the
# award list (ui.UISystemMail / ui.UIR2SystemMail and the iChat mail helpers). Imports the UI
# modules (defines classes, opens nothing) and lists string constants of their functions.
import sys
import types
out = open(OUT, 'w')


def strs(c, seen):
    if id(c) in seen:
        return []
    seen.add(id(c))
    r = [x for x in c.co_consts if isinstance(x, str)]
    for x in c.co_consts:
        if isinstance(x, types.CodeType):
            r += strs(x, seen)
    return r


for name in ('ui.UISystemMail', 'ui.UIR2SystemMail', 'iChat'):
    try:
        m = __import__(name, fromlist=['x'])
    except Exception as e:
        out.write('%s import err %r\n' % (name, e))
        continue
    for k, v in sorted(vars(m).items()):
        if isinstance(v, (type, types.ClassType)) and getattr(v, '__module__', '') == m.__name__:
            for mk, mv in sorted(vars(v).items()):
                if isinstance(mv, types.FunctionType) and any(w in mk.lower() for w in ('mail', 'award', 'refresh', 'item', 'attach', 'cell', 'detail', 'show', 'content', 'get')):
                    c = mv.func_code
                    out.write('%s.%s.%s args=%r names=%r strs=%r\n' % (name, k, mk, c.co_varnames[:c.co_argcount],
                              c.co_names, sorted(set(strs(c, set())))[:60]))
out.close()
