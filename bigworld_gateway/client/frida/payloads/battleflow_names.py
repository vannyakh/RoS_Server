# READ-ONLY: for battle-flow code (battle state, plane, safe-zone circle) print each function's
# co_names / consts / vars, so we can see which entity props and server data the client reads.
import sys, types

out = open(OUT, 'w')
def w(s): out.write(s + '\n')

def code_of(f):
    if isinstance(f, (staticmethod, classmethod)): f = f.__func__
    f = getattr(f, 'im_func', f)
    for cell in (getattr(f, 'func_closure', None) or ()):
        try: v = cell.cell_contents
        except ValueError: continue
        if isinstance(v, types.FunctionType) and v.func_code.co_name == getattr(f, 'func_code', None) and False: pass
    return getattr(f, 'func_code', None)

def dump(label, co, depth=0):
    if co is None or depth > 2: return
    pad = '  ' * depth
    w('%s== %s (L%d) args=%r' % (pad, label, co.co_firstlineno, list(co.co_varnames[:co.co_argcount])))
    w('%s   names=%r' % (pad, list(co.co_names)))
    cs = [c for c in co.co_consts if not hasattr(c, 'co_code')]
    if cs: w('%s   consts=%r' % (pad, cs[:40]))
    for c in co.co_consts:
        if hasattr(c, 'co_code'): dump(label + '/' + c.co_name, c, depth + 1)

def dump_cls(modname, clsname, methods=None, filt=None):
    mod = sys.modules.get(modname)
    cls = getattr(mod, clsname, None) if mod else None
    if cls is None:
        w('## missing %s.%s' % (modname, clsname)); return
    for n, f in sorted(vars(cls).items()):
        co = code_of(f)
        if co is None: continue
        if methods and n not in methods: continue
        if filt and not (filt(n) or any(filt(x) for x in co.co_names)): continue
        dump('%s.%s.%s' % (modname, clsname, n), co)

KEYS = ('circle', 'poison', 'plane', 'battlestate', 'safe', 'airline', 'route')
hit = lambda s: any(k in s.lower() for k in KEYS)

dump_cls('Avatar', 'PlayerAvatar', ('set_battleState', 'set_planeID', 'getOnPlane', 'getOffPlane', 'isEnterOnPlane',
                                    'onWhiteCircleCenterChange', 'set_leftPlayerNumOnPlane', 'getPositionOfBattleState'))
dump_cls('Avatar', 'Avatar', ('set_planeID', 'isEnterOnPlane', 'getPositionOfBattleState', 'showPoisonEffect'))
dump_cls('iBattleGround', 'iBattleGround', ('getBattleState', 'onRequestCircleRestTime', 'set_isInPoisonArea'))
for mod in ('Plane', 'ui.ingame.DtsCircleTip', 'ui.ingame.RadarMap'):
    m = sys.modules.get(mod)
    if m is None:
        w('## missing module ' + mod); continue
    for cn, cls in sorted(vars(m).items()):
        if (isinstance(cls, type) or type(cls).__name__ == 'classobj') and getattr(cls, '__module__', '') == mod:
            dump_cls(mod, cn, None, hit if mod != 'Plane' else None)
# who stores circle data: any module-level function/class in loaded modules referencing these names
WANT = ('whiteCircleCenter', 'blueCircleCenter', 'blueCircleRadius', 'whiteCircleRadius', 'circleStage', 'circleScaleStartTime')
seen = set()
for modname, mod in sorted(sys.modules.items()):
    if mod is None: continue
    try: items = list(vars(mod).items())
    except Exception: continue
    for k, v in items:
        objs = [(k, v)]
        if isinstance(v, type) or type(v).__name__ == 'classobj':
            if getattr(v, '__module__', '') != modname: continue
            objs = [(k + '.' + a, b) for a, b in vars(v).items()]
        for nm, o in objs:
            co = code_of(o) if callable(o) or isinstance(o, (staticmethod, classmethod)) else None
            if co is not None and any(x in co.co_names for x in WANT) and (modname, nm) not in seen:
                seen.add((modname, nm))
                w('USES %s.%s %r' % (modname, nm, [x for x in co.co_names if 'ircle' in x or 'pace' in x or 'oison' in x]))
out.close()
