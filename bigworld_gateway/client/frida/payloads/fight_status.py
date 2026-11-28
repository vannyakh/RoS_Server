# READ-ONLY: BattleGroundSpace.isInFightStatus getter and set_gameStatus (the result screen closes itself
# when the player is alive and the space is in fight status: UIBattlegroundsResult.delayShowResult).
# Module import only; no game method is called.
import sys
out = open(OUT, 'w')


def lines(co):
    m = {}; addr = 0; ln = co.co_firstlineno; t = co.co_lnotab
    for k in range(0, len(t), 2):
        m.setdefault(addr, ln); addr += ord(t[k]); ln += ord(t[k + 1])
    m.setdefault(addr, ln)
    return m


def dump(label, co):
    out.write('==== %s line %s\n  vars=%r\n  names=%r\n  consts=%r\n' % (
        label, co.co_firstlineno, list(co.co_varnames), list(co.co_names), list(co.co_consts)))
    lm = lines(co); code = co.co_code; i = 0; cur = co.co_firstlineno; row = {}
    while i < len(code):
        if i in lm: cur = lm[i]
        op = ord(code[i])
        if op >= 90:
            row.setdefault(cur, []).append('%d:%d' % (op, ord(code[i + 1]) | (ord(code[i + 2]) << 8))); i += 3
        else:
            row.setdefault(cur, []).append(str(op)); i += 1
    for ln in sorted(row):
        out.write('  L%d %s\n' % (ln, ' '.join(row[ln])))


import entities.BattleGroundSpace as m
cls = m.BattleGroundSpace
prop = cls.__dict__.get('isInFightStatus')
for klass in cls.__mro__:
    if 'isInFightStatus' in klass.__dict__:
        prop = klass.__dict__['isInFightStatus']; out.write('defined in %s\n' % klass.__name__); break
dump('isInFightStatus.fget', prop.fget.func_code)
dump('set_gameStatus', cls.set_gameStatus.im_func.func_code)
for k in sorted(dir(m)):
    if 'STATUS' in k.upper() or 'FIGHT' in k.upper():
        out.write('module %s = %r\n' % (k, getattr(m, k)))
try:
    import const
    for k in sorted(dir(const)):
        if 'GAME_STATUS' in k.upper() or 'GAMESTATUS' in k.upper():
            out.write('const.%s = %r\n' % (k, getattr(const, k)))
except Exception as e:
    out.write('const: %r\n' % (e,))
E = m.BattleGroundGameStatusEnum
out.write('enum %r\n' % dict((k, getattr(E, k)) for k in dir(E) if k.isupper()))
out.close()
