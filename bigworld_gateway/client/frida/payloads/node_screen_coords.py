OUT = '/storage/emulated/0/Android/data/com.netease.chiji/files/py_out.log'
f = open(OUT, 'w')
try:
    import Globals
    all_ui = getattr(Globals.uiMgr, '____all_ui__', getattr(Globals.uiMgr, '_UIMgr____all_ui__', {}))
    w = all_ui.get('UILimitWelfareController')
    node = w.panel.FindWidget('Image_1')
    import cc
    # convert (0,0) of node to world space
    wp0 = node.convertToWorldSpace(cc.Vec2(0, 0))
    # convert (width, height) to world space
    sz = node.getContentSize()
    wp1 = node.convertToWorldSpace(cc.Vec2(sz.width, sz.height))
    f.write('wp0: (%f, %f)\n' % (wp0.x, wp0.y))
    f.write('wp1: (%f, %f)\n' % (wp1.x, wp1.y))
except Exception:
    import traceback
    f.write(traceback.format_exc())
f.close()
