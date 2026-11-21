# READ-ONLY: enums and handlers behind the plane / jump / skydive flow of the player
# (battleState, planeID, flightStage, fallPhase, glidePhase) and the space's game status.
import sys, types

f = open(OUT, 'w')
def w(s): f.write(s + '\n')
def short(v, n=300):
    r = repr(v)
    return r if len(r) <= n else r[:n] + '...'

try:
    import const
    for name in sorted(dir(const)):
        low = name.lower()
        if any(k in low for k in ('playerstate', 'flight', 'fall', 'glide', 'skydiv', 'parachute', 'jump', 'plane', 'gamestage', 'battlestate')):
            e = getattr(const, name, None)
            vals = {}
            for k in dir(e):
                if k.startswith('_'): continue
                v = getattr(e, k, None)
                if isinstance(v, (int, long)) and not callable(v): vals[k] = v
            w('ENUM const.%s %s' % (name, sorted(vals.items(), key=lambda kv: kv[1])[:40] if vals else short(e, 120)))
except Exception as ex:
    w('const err %r' % (ex,))

def unwrap(fn):
    for cell in (getattr(fn, 'func_closure', None) or ()):
        try: v = cell.cell_contents
        except ValueError: continue
        if isinstance(v, types.FunctionType): return unwrap(v)
    return fn

def consts(co):
    return [c for c in co.co_consts if isinstance(c, (str, int, long, float)) and not isinstance(c, bool)][:30]

WANT = ('set_battlestate', 'set_flightstage', 'set_planeid', 'set_fallphase', 'set_glidephase', 'onjump', 'requestgetoffplane',
        'ongetoffplane', 'onenterplane', 'onleaveplane', 'chooseparachute', 'onparachute', 'startfall', 'onfall', 'set_isinplane')
seen = set()
for mname, mod in sorted(sys.modules.items()):
    if mod is None: continue
    try: items = list(vars(mod).items())
    except Exception: continue
    for cname, cls in items:
        if not isinstance(cls, (type, types.ClassType)) or getattr(cls, '__module__', None) != mname: continue
        for k, v in list(cls.__dict__.items()):
            if k.lower() in WANT:
                fn = getattr(v, '__func__', v)
                if not isinstance(fn, types.FunctionType): continue
                co = unwrap(fn).func_code
                key = (mname, cname, k)
                if key in seen: continue
                seen.add(key)
                w('FN %s.%s.%s line=%d names=%s consts=%r' % (mname, cname, k, co.co_firstlineno, list(co.co_names)[:45], consts(co)))
f.close()
