# READ-ONLY: the checks that open UIDtsSign and UICosmicSupply at hall entry.
import sys, types
out = open(OUT, 'w')
def w(s): out.write(s[:1600] + '\n')
def show(label, o):
    if isinstance(o, (staticmethod, classmethod)): o = o.__func__
    co = getattr(o, 'func_code', None)
    if not isinstance(co, types.CodeType):
        w('== %s: none' % label); return
    stack = [co]
    while stack:
        c = stack.pop()
        w('== %s/%s (%s:%d) vars=%r' % (label, c.co_name, c.co_filename, c.co_firstlineno, list(c.co_varnames)))
        w('   names=%r' % (list(c.co_names),))
        w('   consts=%r' % ([x if not isinstance(x, types.CodeType) else '<code>' for x in c.co_consts],))
        stack.extend(x for x in c.co_consts if isinstance(x, types.CodeType))
try:
    import BigWorld
    cls = type(BigWorld.player())
    show('onCheckEnterSignInUI', getattr(cls, 'onCheckEnterSignInUI', None))
    for modname, mod in sorted(sys.modules.items()):
        if mod is None or not modname.startswith(('ui', 'entities', 'common', 'helpers')): continue
        try: items = list(vars(mod).items())
        except Exception: continue
        for k, v in items:
            objs = [(k, v)]
            if isinstance(v, (type, types.ClassType)):
                objs = [(k + '.' + n, o) for n, o in vars(v).items()]
            for label, o in objs:
                if isinstance(o, (staticmethod, classmethod)): o = o.__func__
                co = getattr(o, 'func_code', None)
                if isinstance(co, types.CodeType) and 'UICosmicSupplyController' in co.co_consts and modname not in ('ui.UIMgr',) and 'Cosmic' not in modname:
                    show('%s:%s' % (modname, label), o)
except Exception:
    import traceback; w(traceback.format_exc())
out.close()
