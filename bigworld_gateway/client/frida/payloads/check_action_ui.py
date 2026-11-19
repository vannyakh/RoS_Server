import traceback, sys
f = open('/storage/emulated/0/Android/data/com.netease.chiji/files/py_out.log', 'w')
try:
    import Globals
    all_ui = getattr(Globals.uiMgr, '____all_ui__', getattr(Globals.uiMgr, '_UIMgr____all_ui__', {}))
    a = all_ui.get('UIMainActionAndEmoji')
    f.write('UIMainActionAndEmoji: %r\n' % a)
    if a:
        for attr in dir(a):
            if any(x in attr.lower() for x in ['tab', 'emoji', 'btn', 'item', 'select', 'click', 'touch']):
                val = getattr(a, attr, None)
                f.write('  %s: %r\n' % (attr, val))
                if hasattr(val, 'getWorldPosition'):
                    try:
                        f.write('    wp: %r, size: %r\n' % (val.getWorldPosition(), val.getContentSize()))
                    except: pass
except Exception:
    f.write(traceback.format_exc())
f.close()
