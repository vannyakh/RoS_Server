OUT = '/storage/emulated/0/Android/data/com.netease.chiji/files/py_out.log'
f = open(OUT, 'w')
try:
    import Globals
    all_ui = getattr(Globals.uiMgr, '____all_ui__', getattr(Globals.uiMgr, '_UIMgr____all_ui__', {}))
    w = all_ui.get('UILimitWelfareController')
    img1 = getattr(w, 'Image_1', None)
    f.write('img1: %r\n' % img1)
    if img1:
        f.write('pos: %r\n' % getattr(img1, 'getPosition', lambda: None)())
        f.write('worldPos: %r\n' % getattr(img1, 'getWorldPosition', lambda: None)())
        f.write('size: %r\n' % getattr(img1, 'getContentSize', lambda: None)())
        bb = getattr(img1, 'getBoundingBox', lambda: None)()
        f.write('bb: %r\n' % bb)
except Exception:
    import traceback
    f.write(traceback.format_exc())
f.close()
