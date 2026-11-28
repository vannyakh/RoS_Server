# READ-ONLY: meethttp portrait download (getTantanFileID, downloadPortrait) and its URL constants.
# Calls no game method.
import sys

out = open(OUT, 'w')
WANT = ('onBattleGroundDie', 'onBattleGroundResult', 'kickOutToHall', 'gameEnd', 'onGetFinalBattleData',
        'showKillerOverview', 'die')


def code_of(func):
    return getattr(func, 'func_code', None) or getattr(getattr(func, '__func__', None), 'func_code', None)


def lines(co):
    m = {}; addr = 0; ln = co.co_firstlineno; t = co.co_lnotab
    for k in range(0, len(t), 2):
        m.setdefault(addr, ln); addr += ord(t[k]); ln += ord(t[k + 1])
    m.setdefault(addr, ln)
    return m


def dump_code(co, indent=''):
    out.write('%s  file %s line %s vars=%r\n' % (indent, co.co_filename, co.co_firstlineno, list(co.co_varnames)))
    out.write('%s  names=%r\n' % (indent, list(co.co_names)))
    out.write('%s  consts=%r\n' % (indent, [c if not hasattr(c, 'co_code') else '<code %s>' % c.co_name for c in co.co_consts]))
    lm = lines(co); code = co.co_code; i = 0; cur = co.co_firstlineno; row = {}
    while i < len(code):
        if i in lm: cur = lm[i]
        op = ord(code[i])
        if op >= 90:
            arg = ord(code[i + 1]) | (ord(code[i + 2]) << 8)
            row.setdefault(cur, []).append('%d:%d' % (op, arg)); i += 3
        else:
            row.setdefault(cur, []).append(str(op)); i += 1
    for ln in sorted(row):
        out.write('%s  L%d %s\n' % (indent, ln, ' '.join(row[ln])))
    for c in co.co_consts:
        if hasattr(c, 'co_code'):
            out.write('%s  --- nested %s\n' % (indent, c.co_name))
            dump_code(c, indent + '    ')


def dump(label, func):
    out.write('==== %s\n' % label)
    code = code_of(func)
    if code is None:
        out.write('  (no code)\n')
        return
    dump_code(code)


mh = sys.modules.get('meethttp')
out.write('meethttp module %r\n' % (mh,))
if mh is not None:
    for k, v in sorted(vars(mh).items()):
        if isinstance(v, (str, unicode, int)) and not k.startswith('__'):
            out.write('  %s = %r\n' % (k, v))
    for n in ('getTantanFileID', 'downloadPortrait', 'getFilePickerURL', 'getDownloadURL'):
        if hasattr(mh, n):
            dump('meethttp.' + n, getattr(mh, n))
mc = sys.modules.get('meetconfigs')
if mc is not None:
    for k, v in sorted(vars(mc).items()):
        if isinstance(v, (str, unicode, int)) and not k.startswith('__'):
            out.write('meetconfigs.%s = %r\n' % (k, v))
out.close()
