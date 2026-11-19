OUT = '/storage/emulated/0/Android/data/com.netease.chiji/files/py_out.log'
f = open(OUT, 'w')
try:
    import Globals, cc
    all_ui = getattr(Globals.uiMgr, '____all_ui__', getattr(Globals.uiMgr, '_UIMgr____all_ui__', {}))
    w = all_ui.get('UILimitWelfareController')
    node = w.panel.FindWidget('Image_1')
    f.write('node.hitTest(cc.Vec2(640, 360)): %r\n' % getattr(node, 'hitTest', lambda pt: None)(cc.Vec2(640, 360)))
    f.write('node.hitTest(cc.Vec2(800, 450)): %r\n' % getattr(node, 'hitTest', lambda pt: None)(cc.Vec2(800, 450)))
    f.write('node.isSwallowTouches: %r\n' % getattr(node, 'isSwallowTouches', lambda: None)())
except Exception:
    import traceback
    f.write(traceback.format_exc())
f.close()
