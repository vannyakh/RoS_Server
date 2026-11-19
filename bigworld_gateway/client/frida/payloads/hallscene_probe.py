# READ-ONLY: code that picks the hall scene path (scene\hall vs scene\hall2).
import sys, types
out = open(OUT, 'w')


def w(s):
    out.write(s[:1500] + '\n')


def walk(co):
    yield co
    for c in co.co_consts:
        if isinstance(c, types.CodeType):
            for x in walk(c):
                yield x


def is_hall(x):
    return isinstance(x, str) and ('hall2' in x or 'scene\\hall\\' in x or 'scene/hall/' in x or 'hall.scn' in x)


try:
    hits = 0
    for modname, mod in sorted(sys.modules.items()):
        if mod is None or hits > 14:
            continue
        try:
            items = list(vars(mod).items())
        except Exception:
            continue
        for k, v in items:
            if is_hall(v):
                w('CONST %s.%s = %r' % (modname, k, v))
            objs = [(k, v)]
            if isinstance(v, (type, types.ClassType)):
                objs = [(k + '.' + n, o) for n, o in vars(v).items()]
            for label, o in objs:
                if isinstance(o, (staticmethod, classmethod)):
                    o = o.__func__
                try:
                    co = getattr(o, 'func_code', None)
                except Exception:
                    continue
                if not isinstance(co, types.CodeType):
                    continue
                for c in walk(co):
                    if any(is_hall(x) for x in c.co_consts) or 'SCENE_PATH' in c.co_names:
                        hits += 1
                        w('== %s:%s/%s (%s:%d) vars=%r' % (modname, label, c.co_name, c.co_filename, c.co_firstlineno, list(c.co_varnames)))
                        w('   names=%r' % (list(c.co_names),))
                        w('   consts=%r' % ([x if not isinstance(x, types.CodeType) else '<code>' for x in c.co_consts],))
except Exception:
    import traceback
    w(traceback.format_exc())
out.close()
