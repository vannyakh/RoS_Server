# READ-ONLY: UIDtsSign methods (names/consts) and the player's iDtsSignin state.
import sys, types
out = open(OUT, 'w')
def w(s): out.write(s[:1400] + '\n')
try:
    mod = sys.modules.get('ui.UIDtsSign')
    cls = getattr(mod, 'UIDtsSign', None)
    for n in sorted(vars(cls)):
        f = vars(cls)[n]
        co = getattr(f, 'func_code', None)
        if isinstance(co, types.CodeType) and n in ('refresh_init_ui', '_get_ui', '_refresh_huiliu_event', 'btn_func_list'):
            w('== UIDtsSign.%s line %d vars=%r' % (n, co.co_firstlineno, list(co.co_varnames)))
            w('   names=%r' % (list(co.co_names),))
            w('   consts=%r' % ([c if not isinstance(c, types.CodeType) else '<code>' for c in co.co_consts],))
    w('methods=%r' % sorted(n for n in vars(cls) if not n.startswith('__')))
    import BigWorld
    p = BigWorld.player()
    for a in sorted(dir(p)):
        if ('sign' in a.lower() or 'huiliu' in a.lower()) and not callable(getattr(p, a, None)):
            w('ATTR %s = %r' % (a, getattr(p, a)))
    import Globals
    ui = Globals.uiMgr.get_ui_by_name('UIDtsSign')
    w('ui=%r visible=%r' % (ui, getattr(getattr(ui, 'widget', None), 'isVisible', lambda: '?')()))
except Exception:
    import traceback; w(traceback.format_exc())
out.close()
