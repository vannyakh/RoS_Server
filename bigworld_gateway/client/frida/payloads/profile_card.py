# READ-ONLY: the lobby profile card (top-left: portrait, name, level badge). Dumps UIMain profile
# methods and client_utils.getAvatarProtrait, and the PlayerAthlete values they read. Calls no game method.
import sys

out = open(OUT, 'w')


def code_of(func):
    return getattr(func, 'func_code', None) or getattr(getattr(func, '__func__', None), 'func_code', None)


def dump(label, func):
    co = code_of(func)
    out.write('==== %s\n' % label)
    if co is None:
        out.write('  (no code)\n')
        return
    out.write('  file %s line %s vars=%r\n' % (co.co_filename, co.co_firstlineno, list(co.co_varnames)))
    out.write('  names=%r\n' % (list(co.co_names),))
    out.write('  consts=%r\n' % ([c if not hasattr(c, 'co_code') else '<code %s>' % c.co_name for c in co.co_consts],))
    for c in co.co_consts:
        if hasattr(c, 'co_code'):
            out.write('  --- nested %s names=%r consts=%r\n' % (c.co_name, list(c.co_names), [k for k in c.co_consts if not hasattr(k, 'co_code')]))


for modname, mod in sorted(sys.modules.items()):
    if mod is None or not modname.startswith('ui.UIMain'):
        continue
    for k, v in list(vars(mod).items()):
        if (isinstance(v, type) or type(v).__name__ == 'classobj') and getattr(v, '__module__', '') == modname:
            for n, f in sorted(vars(v).items()):
                low = n.lower()
                if code_of(f) is not None and ('profile' in low or 'portrait' in low or 'level' in low
                                               or 'headframe' in low or 'exp' in low or 'vip' in low):
                    dump('%s.%s.%s' % (modname, k, n), f)
cu = sys.modules.get('client_utils')
for n in ('getAvatarProtrait', 'getAvatarPortrait'):
    if cu is not None and hasattr(cu, n):
        dump('client_utils.' + n, getattr(cu, n))
try:
    import BigWorld
    p = BigWorld.player()
    out.write('player %s\n' % type(p).__name__)
    for a in ('baseLevel', 'level', 'baseExp', 'exp', 'baseCharacterType', 'portrait', 'headFrameTag',
              'nationalFlag', 'vipInfo', 'baseNickname', 'playerName', 'gid', 'childBaseClientProperty'):
        try:
            v = getattr(p, a, '<none>')
            out.write('  %s = %r\n' % (a, v if not isinstance(v, (list, dict)) else str(v)[:300]))
        except Exception as e:
            out.write('  %s: %r\n' % (a, e))
except Exception as e:
    out.write('player: %r\n' % (e,))
out.close()
