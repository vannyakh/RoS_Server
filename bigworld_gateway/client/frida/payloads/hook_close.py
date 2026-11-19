OUT = '/storage/emulated/0/Android/data/com.netease.chiji/files/py_out.log'
f = open(OUT, 'w')
try:
    import Globals
    all_ui = getattr(Globals.uiMgr, '____all_ui__', getattr(Globals.uiMgr, '_UIMgr____all_ui__', {}))
    w = all_ui.get('UILimitWelfareController')
    old_fn = w.onCloseTouch
    def dbg_close(*a, **kw):
        with open('/storage/emulated/0/Android/data/com.netease.chiji/files/close_touch.log', 'a') as f2:
            f2.write('CALLED! a=%r kw=%r\n' % (a, kw))
            if len(a) > 0 and hasattr(a[0], 'touch'):
                f2.write('phase: %r\n' % getattr(a[0].touch, 'phase', None))
        return old_fn(*a, **kw)
    w.onCloseTouch = dbg_close
    f.write('Installed dbg_close on w\n')
except Exception:
    import traceback
    f.write(traceback.format_exc())
f.close()
