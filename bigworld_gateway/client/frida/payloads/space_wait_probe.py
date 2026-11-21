# READ-ONLY: how the client's BattleGroundSpace handles game status / wait-born (warm-up island, countdown),
# and what its map table (maps_utils) holds. Output: names and small constants only.
import sys, types

f = open(OUT, 'w')
def w(s): f.write(s + '\n')

def unwrap(fn):
    for cell in (getattr(fn, 'func_closure', None) or ()):
        try: v = cell.cell_contents
        except ValueError: continue
        if isinstance(v, types.FunctionType): return unwrap(v)
    return fn

def consts(co):
    return [c for c in co.co_consts if isinstance(c, (str, int, long, float)) and not isinstance(c, bool)][:40]

def dump_fn(tag, fn):
    fn = getattr(fn, '__func__', fn)
    if not isinstance(fn, types.FunctionType): return
    co = unwrap(fn).func_code
    w('FN %s line=%d vars=%s names=%s consts=%r' % (tag, co.co_firstlineno, list(co.co_varnames)[:12], list(co.co_names)[:70], consts(co)))

def short(v):
    r = repr(v)
    return r if len(r) < 400 else r[:400] + '...'

KEYS = ('gamestatus', 'waitborn', 'countdown', 'starttime', 'plane', 'initui', 'enterworld', 'gameend', 'circle', 'onenter', 'leftTime'.lower())

for mname, mod in sorted(sys.modules.items()):
    if mod is None: continue
    low = mname.lower()
    if low.endswith('battlegroundspace'):
        w('MODULE %s' % mname)
        cls = getattr(mod, 'BattleGroundSpace', None)
        for k, v in sorted(vars(mod).items()):
            if isinstance(v, (dict, list, tuple)) and not k.startswith('__'):
                w('MODVAR %s = %s' % (k, short(v)))
        if cls is not None:
            for k, v in sorted(cls.__dict__.items()):
                if isinstance(v, (dict, list, tuple)) and not k.startswith('__'):
                    w('CLSVAR %s = %s' % (k, short(v)))
                elif any(n in k.lower() for n in KEYS):
                    dump_fn('BattleGroundSpace.' + k, v)
    if low.endswith('maps_utils') or low.endswith('map_utils') or low.endswith('mapsutils'):
        w('MAPS MODULE %s' % mname)
        w('  attrs=%s' % [k for k in dir(mod) if not k.startswith('__')][:80])
        for k, v in sorted(vars(mod).items()):
            if k.startswith('__'): continue
            if isinstance(v, dict):
                keys = sorted(v.keys())[:60]
                w('  DICT %s n=%d keys=%s' % (k, len(v), keys))
            elif isinstance(v, (int, long, str)):
                w('  CONST %s = %r' % (k, v))
f.close()
