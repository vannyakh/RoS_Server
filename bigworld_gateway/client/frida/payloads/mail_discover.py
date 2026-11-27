# READ-ONLY: the client's mail system. Names/consts of the Athlete mail handlers
# (onMailUpdate, onLoadMailDetail, onGetAwardFromMail, requestMails) and of the mail modules,
# so the server can build the PYTHON arguments these methods unpickle. Reads code objects only.
import sys
import types
out = open(OUT, 'w')


def code(f):
    c = getattr(f, 'func_code', None)
    if c is None:
        return 'not a function'
    return 'args=%r names=%r consts=%r' % (c.co_varnames[:c.co_argcount], c.co_names,
                                          [x for x in c.co_consts if not isinstance(x, types.CodeType)])


import BigWorld
p = BigWorld.player()
for n in ('onMailUpdate', 'onLoadMailDetail', 'onLoadMailDetailFailed', 'onGetAwardFromMail',
          'requestMails', 'requestMailDetail', 'getAwardFromMail', 'deleteMail', 'onUpdateHeadFrameTag',
          'setHeadFrameTag', 'equipHeadFrame'):
    for k in type(p).__mro__:
        if n in vars(k):
            out.write('player.%s (%s) %s\n' % (n, k.__name__, code(vars(k)[n])))
            break
for k in sorted(dir(p)):
    if 'mail' in k.lower() and not callable(getattr(p, k, None)):
        out.write('player attr %s=%r\n' % (k, getattr(p, k))[:400])
mods = sorted(n for n, m in sys.modules.items() if m is not None and 'mail' in n.lower())
out.write('modules=%r\n' % mods)
for n in mods:
    m = sys.modules[n]
    for k, v in sorted(vars(m).items()):
        if isinstance(v, types.FunctionType):
            out.write('%s.%s %s\n' % (n, k, code(v)))
        elif isinstance(v, (type, types.ClassType)):
            for mk, mv in sorted(vars(v).items()):
                if isinstance(mv, types.FunctionType) and any(w in mk.lower() for w in ('mail', 'award', 'refresh', 'init', 'show', 'update', 'item', 'attach')):
                    out.write('%s.%s.%s %s\n' % (n, k, mk, code(mv)))
        elif isinstance(v, (int, str, dict)) and not k.startswith('__'):
            out.write('%s.%s=%r\n' % (n, k, v if not isinstance(v, dict) else dict(list(v.items())[:15])))
out.close()
