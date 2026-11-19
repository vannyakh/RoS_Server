OUT = '/storage/emulated/0/Android/data/com.netease.chiji/files/py_out.log'
f = open(OUT, 'w')
try:
    import Globals
    all_ui = getattr(Globals.uiMgr, '____all_ui__', getattr(Globals.uiMgr, '_UIMgr____all_ui__', {}))
    w = all_ui.get('UILimitWelfareController')
    fn = w.onCloseTouch
    co = fn.func_code
    f.write('co_names: %r\n' % list(co.co_names))
    f.write('co_consts: %r\n' % list(co.co_consts))
    f.write('co_varnames: %r\n' % list(co.co_varnames))
except Exception:
    import traceback
    f.write(traceback.format_exc())
f.close()
