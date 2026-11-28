# READ-ONLY: is the loose common/supplement_utils override loaded, and does the month lookup run?
# Calls only the getter getCurrentMonthSupplementID (it reads client tables and returns an id).
out = open(OUT, 'w')
try:
    import sys
    for name in ('supplement_utils', 'common.supplement_utils'):
        try:
            __import__(name)
            break
        except ImportError:
            pass
    m = sys.modules[name]
    out.write('module=%s file=%r\n' % (name, getattr(m, '__file__', None)))
    fn = m.getCurrentMonthSupplementID
    inner = fn.func_closure[0].cell_contents if fn.func_closure else fn     # decorator wrapper
    co = inner.func_code
    out.write('consts=%r' % (list(co.co_consts),) + chr(10))
    out.write('names=%r' % (list(co.co_names),) + chr(10))
    import time
    out.write('device_time=%r' % (time.time(),) + chr(10))
    try:
        out.write('inner()=%r' % (inner(),) + chr(10))
    except Exception as e:
        import traceback
        out.write(traceback.format_exc())
except Exception as e:
    out.write('error=%r\n' % (e,))
out.close()
