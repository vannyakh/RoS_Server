# READ-ONLY: who reads/sets skipHallPopupUI and checkPopUpUINum.
import sys, types
out = open(OUT, 'w')
def w(s): out.write(s[:1300] + '\n')
def walk(co):
    yield co
    for c in co.co_consts:
        if isinstance(c, types.CodeType):
            for x in walk(c): yield x
try:
    hits = 0
    for modname, mod in sorted(sys.modules.items()):
        if mod is None or hits > 12 or not modname.startswith(('ui', 'entities', 'helpers', 'common', 'client_utils', 'Athlete')):
            continue
        try: items = list(vars(mod).items())
        except Exception: continue
        for k, v in items:
            objs = [(k, v)]
            if isinstance(v, (type, types.ClassType)):
                objs = [(k + '.' + n, o) for n, o in vars(v).items()]
            for label, o in objs:
                if isinstance(o, (staticmethod, classmethod)): o = o.__func__
                co = getattr(o, 'func_code', None)
                if not isinstance(co, types.CodeType): continue
                for c in walk(co):
                    if 'skipHallPopupUI' in c.co_names or 'checkPopUpUINum' == c.co_name:
                        hits += 1
                        w('== %s:%s/%s (%s:%d) vars=%r' % (modname, label, c.co_name, c.co_filename, c.co_firstlineno, list(c.co_varnames)))
                        w('   names=%r' % (list(c.co_names)[:60],))
                        w('   consts=%r' % ([x if not isinstance(x, types.CodeType) else '<code>' for x in c.co_consts][:40],))
except Exception:
    import traceback; w(traceback.format_exc())
out.close()
