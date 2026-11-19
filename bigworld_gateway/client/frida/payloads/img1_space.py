OUT = '/storage/emulated/0/Android/data/com.netease.chiji/files/py_out.log'
f = open(OUT, 'w')
try:
    import Globals
    all_ui = getattr(Globals.uiMgr, '____all_ui__', getattr(Globals.uiMgr, '_UIMgr____all_ui__', {}))
    w = all_ui.get('UILimitWelfareController')
    node = w.panel.FindWidget('Image_1')
    p = node.getParent()
    f.write('parent: %r pos=%r\n' % (p, getattr(p, 'getPosition', lambda: None)()))
    f.write('node.convertToWorldSpace(0,0): %r\n' % getattr(node, 'convertToWorldSpace', lambda x, y: None)(0, 0))
    f.write('node.convertToWorldSpace(100,100): %r\n' % getattr(node, 'convertToWorldSpace', lambda x, y: None)(100, 100))
except Exception:
    import traceback
    f.write(traceback.format_exc())
f.close()
