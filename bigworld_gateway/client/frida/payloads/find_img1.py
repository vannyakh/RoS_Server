OUT = '/storage/emulated/0/Android/data/com.netease.chiji/files/py_out.log'
f = open(OUT, 'w')
try:
    import Globals
    all_ui = getattr(Globals.uiMgr, '____all_ui__', getattr(Globals.uiMgr, '_UIMgr____all_ui__', {}))
    w = all_ui.get('UILimitWelfareController')
    node = w.panel.FindWidget('Image_1')
    f.write('node: %r\n' % node)
    if node:
        f.write('pos: %r\n' % getattr(node, 'getPosition', lambda: None)())
        f.write('size: %r\n' % getattr(node, 'getContentSize', lambda: None)())
        f.write('wp: %r\n' % getattr(node, 'getWorldPosition', lambda: None)())
        f.write('bb: %r\n' % getattr(node, 'getBoundingBox', lambda: None)())
except Exception:
    import traceback
    f.write(traceback.format_exc())
f.close()
