# READ-ONLY: names/constants of the portrait functions, the FilePicker download path,
# and which built-in portrait images exist in the package.
import sys
import types

out = open(OUT, 'w')


def info(label, func):
    code = getattr(func, 'func_code', None) or getattr(getattr(func, '__func__', None), 'func_code', None)
    if code is None:
        out.write('%s: none\n' % label)
        return
    out.write('%s\n  args=%r\n  names=%r\n  consts=%r\n' % (label, code.co_varnames[:code.co_argcount], code.co_names, [c for c in code.co_consts if not isinstance(c, types.CodeType)]))
    for c in code.co_consts:
        if isinstance(c, types.CodeType):
            out.write('  nested %s names=%r consts=%r\n' % (c.co_name, c.co_names, [x for x in c.co_consts if not isinstance(x, types.CodeType)]))


cu = sys.modules.get('client_utils')
for name in ('getAvatarProtrait', 'getAvatarPortraitByFPID', 'getAvatarPortraitByGID', 'getAvatarProtratiAndFrame', 'downloadPortrait'):
    info('client_utils.' + name, getattr(cu, name, None))
out.write('client_utils.AVATAR_PORTRAIT_RES_PATH_PREFIX=%r\n' % getattr(cu, 'AVATAR_PORTRAIT_RES_PATH_PREFIX', None))

# where downloadPortrait lives
for mname, mod in sys.modules.items():
    if mod is None:
        continue
    f = getattr(mod, 'downloadPortrait', None)
    if f is not None:
        info('%s.downloadPortrait' % mname, f)
    for k in ('AVATAR_PORTRAIT_RES_PATH_PREFIX', 'FILEPICKER_URL', 'FILE_PICKER_URL', 'FP_URL', 'MEET_URL'):
        if k in getattr(mod, '__dict__', {}):
            out.write('CONST %s.%s=%r\n' % (mname, k, mod.__dict__[k]))

pa = getattr(sys.modules.get('Athlete'), 'PlayerAthlete', None)
for name in ('updateBaseCharacter', 'onSetPortrait', 'setPortrait'):
    info('PlayerAthlete.' + name, getattr(pa, name, None) if pa else None)
um = getattr(sys.modules.get('ui.UIMain'), 'UIMain', None)
for name in ('_set_profile_avatar', '_set_profile_avatar_and_frame', 'updateProfileAvatar', '_init_profile', 'on_enter'):
    info('UIMain.' + name, getattr(um, name, None) if um else None)

# built-in portrait files: probe with the engine file check if one exists
checker = None
for mname in ('C_file', 'render', 'world', 'game3d'):
    mod = sys.modules.get(mname)
    for fn in ('find_file', 'file_exist', 'file_exists', 'exists'):
        if mod is not None and hasattr(mod, fn):
            checker = (mname, fn, getattr(mod, fn))
            break
    if checker:
        break
out.write('checker=%r\n' % (checker[:2] if checker else None,))
if checker:
    found = []
    for i in range(0, 400):
        try:
            if checker[2]('ui/images/avatar/portrait/%d_on.png' % i):
                found.append(i)
        except Exception as e:
            out.write('check error %r\n' % e)
            break
    out.write('builtin portrait ids=%r\n' % found)
out.close()
