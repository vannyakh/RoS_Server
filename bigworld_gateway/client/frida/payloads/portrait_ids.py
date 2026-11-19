# READ-ONLY: how C_file.find_file answers, which portrait images exist, and the
# FilePicker object meethttp uses for downloads.
import sys

out = open(OUT, 'w')
C_file = sys.modules['C_file']
for path in ('ui/in_game/ui_friendship/vx_effect.csb', 'ui/images/avatar/portrait/1_on.png',
             'ui/images/avatar/portrait/20001_on.png', 'ui/images/avatar/portrait/10001_on.png'):
    for second in ('', 'res', 'ui'):
        try:
            out.write('find_file(%r, %r) -> %r\n' % (path, second, C_file.find_file(path, second)))
        except Exception as e:
            out.write('find_file(%r, %r) !! %r\n' % (path, second, e))
out.write('C_file attrs=%r\n' % [k for k in dir(C_file) if not k.startswith('_')])

mh = sys.modules.get('meethttp')
fp = getattr(mh, 'filePicker', None)
out.write('meethttp.filePicker=%r type=%r\n' % (fp, type(fp)))
if fp is not None:
    for k in dir(fp):
        if k.startswith('__'):
            continue
        try:
            v = getattr(fp, k)
        except Exception as e:
            v = e
        if isinstance(v, (basestring, int, long, dict, list, tuple)):
            out.write('  fp.%s=%r\n' % (k, v))
        else:
            code = getattr(v, 'func_code', None) or getattr(getattr(v, '__func__', None), 'func_code', None)
            if code:
                out.write('  fp.%s args=%r names=%r consts=%r\n' % (k, code.co_varnames[:code.co_argcount], code.co_names[:40], [c for c in code.co_consts if not hasattr(c, 'co_code')][:25]))
for k in sorted(vars(mh)):
    v = getattr(mh, k)
    if isinstance(v, basestring):
        out.write('meethttp.%s=%r\n' % (k, v))
mc = sys.modules.get('meetconfigs')
if mc:
    for k in sorted(vars(mc)):
        v = getattr(mc, k)
        if isinstance(v, (basestring, int)) and not k.startswith('_'):
            out.write('meetconfigs.%s=%r\n' % (k, v))
out.close()
