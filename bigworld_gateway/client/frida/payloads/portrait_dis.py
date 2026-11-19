# READ-ONLY: disassemble the client's portrait functions and read related constants.
import sys
import dis
import StringIO

out = open(OUT, 'w')


def dump(label, func):
    out.write('==== %s\n' % label)
    code = getattr(func, 'func_code', None) or getattr(getattr(func, '__func__', None), 'func_code', None)
    if code is None:
        out.write('  (no code)\n')
        return
    buf = StringIO.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        dis.dis(code)
        for c in code.co_consts:
            if hasattr(c, 'co_code'):
                print('--- nested %s' % c.co_name)
                dis.dis(c)
    finally:
        sys.stdout = old
    out.write(buf.getvalue())


cu = sys.modules.get('client_utils')
for name in ('getAvatarProtrait', 'getAvatarPortraitByFPID', 'getAvatarPortraitByGID', 'getAvatarProtratiAndFrame'):
    dump('client_utils.' + name, getattr(cu, name, None))

ath = sys.modules.get('Athlete')
pa = getattr(ath, 'PlayerAthlete', None)
for name in ('updateBaseCharacter', 'onSetPortrait'):
    dump('PlayerAthlete.' + name, getattr(pa, name, None) if pa else None)

ui = sys.modules.get('ui.UIMain')
um = getattr(ui, 'UIMain', None)
for name in ('_set_profile_avatar', '_set_profile_avatar_and_frame', 'updateProfileAvatar', '_init_profile'):
    dump('UIMain.' + name, getattr(um, name, None) if um else None)

# constants that the functions above refer to
for modname in ('client_utils', 'meethttp', 'const', 'client_const', 'common.const', 'gameconst'):
    mod = sys.modules.get(modname)
    if mod is None:
        continue
    for k in sorted(vars(mod)):
        if any(w in k.upper() for w in ('PORTRAIT', 'FILEPICKER', 'FILE_PICKER', 'FP_', 'MEET_URL', 'TANTAN')):
            out.write('CONST %s.%s = %r\n' % (modname, k, getattr(mod, k)))
out.close()
