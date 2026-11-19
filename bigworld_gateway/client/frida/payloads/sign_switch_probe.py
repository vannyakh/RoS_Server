# READ-ONLY: switches about sign-in / returning players, and the code that enters UIDtsSign.
import sys, types
out = open(OUT, 'w')
def w(s): out.write(s[:1400] + '\n')
try:
    sw = sys.modules.get('shared.switches')
    for k in sorted(vars(sw)):
        if any(t in k.lower() for t in ('sign', 'huiliu', 'recall', 'popup')):
            w('SWITCH %s = %r' % (k, getattr(sw, k)))
    def walk(co):
        yield co
        for c in co.co_consts:
            if isinstance(c, types.CodeType):
                for x in walk(c): yield x
    hits = 0
    for modname, mod in sorted(sys.modules.items()):
        if mod is None or hits > 8 or not modname.startswith(('ui', 'entities', 'helpers', 'common', 'Athlete')):
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
                    if 'UIDtsSign' in c.co_consts and modname != 'ui.UIDtsSign':
                        hits += 1
                        w('== %s:%s (%s:%d)' % (modname, label, c.co_filename, c.co_firstlineno))
                        w('   names=%r' % (list(c.co_names),))
                        w('   consts=%r' % ([x if not isinstance(x, types.CodeType) else '<code>' for x in c.co_consts],))
except Exception:
    import traceback; w(traceback.format_exc())
out.close()
