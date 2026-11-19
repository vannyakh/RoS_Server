OUT = '/storage/emulated/0/Android/data/com.netease.chiji/files/py_out.log'
f = open(OUT, 'w')
try:
    import sys
    m = sys.modules.get('ui.UILimitWelfareController')
    f.write('file: %r\n' % getattr(m, '__file__', None))
    cls = getattr(m, 'UILimitWelfareController')
    f.write('bases: %r\n' % cls.__bases__)
    for k, v in cls.__dict__.items():
        if not k.startswith('__'):
            f.write('%s: %r\n' % (k, v))
except Exception:
    import traceback
    f.write(traceback.format_exc())
f.close()
