# READ-ONLY: names of entered/visible UIs (any uiMgr dict/list attribute holding UI names).
out = open(OUT, 'w')
try:
    import Globals
    m = Globals.uiMgr
    for a in sorted(dir(m)):
        if a.startswith('__'): continue
        try: v = getattr(m, a)
        except Exception: continue
        if isinstance(v, dict) and v and all(isinstance(k, str) for k in list(v)[:5]) and any(k.startswith('UI') for k in list(v)[:50]):
            out.write('%s: %r\n' % (a, sorted(v)[:80]))
        elif isinstance(v, (list, tuple)) and v and isinstance(v[0], str) and v[0].startswith('UI'):
            out.write('%s: %r\n' % (a, list(v)[:80]))
    for n in ('UIMask', 'UIDialog', 'UIDtsSign', 'UIMain', 'UICosmicSupply', 'UIJumpTip', 'UIWaiting', 'UILoading'):
        try: out.write('is_enter %s = %r\n' % (n, m.is_enter(n)))
        except Exception as e: out.write('is_enter %s err %r\n' % (n, e))
except Exception:
    import traceback; out.write(traceback.format_exc())
out.close()
