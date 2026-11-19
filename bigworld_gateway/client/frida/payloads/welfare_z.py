OUT = '/storage/emulated/0/Android/data/com.netease.chiji/files/py_out.log'
f = open(OUT, 'w')
try:
    import Globals
    all_ui = getattr(Globals.uiMgr, '____all_ui__', getattr(Globals.uiMgr, '_UIMgr____all_ui__', {}))
    w = all_ui.get('UILimitWelfareController')
    f.write('w.ui_zorder: %r\n' % getattr(w, 'ui_zorder', None))
    f.write('w.ui_type: %r\n' % getattr(w, 'ui_type', None))
except Exception:
    import traceback
    f.write(traceback.format_exc())
f.close()
