OUT = '/storage/emulated/0/Android/data/com.netease.chiji/files/py_out.log'
f = open(OUT, 'w')
try:
    import Globals
    all_ui = getattr(Globals.uiMgr, '____all_ui__', getattr(Globals.uiMgr, '_UIMgr____all_ui__', {}))
    w = all_ui.get('UILimitWelfareController')
    node = w.panel.FindWidget('Image_1')
    f.write('node: %r\n' % node)
    f.write('isTouchEnabled: %r\n' % getattr(node, 'isTouchEnabled', lambda: None)())
    f.write('isVisible: %r\n' % getattr(node, 'isVisible', lambda: None)())
except Exception:
    import traceback
    f.write(traceback.format_exc())
f.close()
