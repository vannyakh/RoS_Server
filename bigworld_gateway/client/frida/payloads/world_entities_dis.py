# READ-ONLY (lane 5): disassembly of the client's vehicle / airdrop handlers (no calls, code objects only).
# Modules are found by suffix in sys.modules (package paths differ between builds).
import sys, types
f = open(OUT, 'w')
def w(s): f.write(s + '\n')
TARGETS = [
    ('iLandDrive', 'iLandDrive', 'refreshDriveState'),
    ('iLandDrive', 'iLandDrive', 'canGetOnLandVehicle'),
    ('iLandDrive', 'iLandDrive', 'onSwitchToDriver'),
    ('iVehicleEntity', 'iVehicleEntity', 'onAddAvatarSocket'),
    ('iVehicleEntity', 'iVehicleEntity', 'onControlledBy'),
    ('iVehicleEntity', 'iVehicleEntity', 'selectControl'),
    ('iVehicleEntity', 'iVehicleEntity', 'enterWorld'),
    ('iVehicleEntity', 'iVehicleEntity', 'usedSockets'),
    ('iLandVehicle', 'iLandVehicle', 'enterWorld'),
    ('iLandVehicle', 'iLandVehicle', 'showEnterHint'),
    ('iLandVehicle', 'iLandVehicle', 'onGetOn'),
    ('Plane', 'Plane', 'getPreloadModel'),
    ('DtsPlayerHeritage', 'DtsPlayerHeritage', 'getPreloadModel'),
    ('DtsPlayerHeritage', 'DtsPlayerHeritage', 'enterWorld'),
    ('DtsPlayerHeritage', 'DtsPlayerHeritage', 'set_dropping'),
    ('DtsPlayerHeritage', 'DtsPlayerHeritage', 'tryPickUp'),
    ('HeritageListControlComponent', 'HeritageListControlComponent', '__doRefreshHeritageItemList'),
    ('iDtsProp', 'iDtsProp', 'nearGroundChest'),
]
def find_mod(name):
    if name in sys.modules and sys.modules[name] is not None: return sys.modules[name]
    for k, m in sys.modules.items():
        if m is not None and (k == name or k.endswith('.' + name)): return m
    return None
def unwrap(fn):
    for cell in (getattr(fn, 'func_closure', None) or ()):
        try: v = cell.cell_contents
        except ValueError: continue
        if isinstance(v, types.FunctionType): return unwrap(v)
    return fn
def get_fn(obj, meth):
    for k in (meth, '_%s%s' % (getattr(obj, '__name__', ''), meth)):
        fn = obj.__dict__.get(k) if hasattr(obj, '__dict__') else None
        if fn is not None: return fn
    for base in getattr(obj, '__mro__', ())[1:]:
        fn = base.__dict__.get(meth) or base.__dict__.get('_%s%s' % (obj.__name__, meth))
        if fn is not None: return fn
    return None
def dis(modname, clsname, meth):
    mod = find_mod(modname)
    obj = getattr(mod, clsname, None) if mod else None
    fn = get_fn(obj, meth) if obj is not None else None
    if fn is None: w('## %s.%s.%s not found (mod %r)' % (modname, clsname, meth, mod)); return
    if isinstance(fn, property): fn = fn.fget
    if isinstance(fn, (staticmethod, classmethod)): fn = fn.__func__
    co = unwrap(fn).func_code
    w('## %s.%s.%s first=%d vars=%s consts=%r' % (modname, clsname, meth, co.co_firstlineno, list(co.co_varnames),
                                                [c for c in co.co_consts if not hasattr(c, 'co_code')][:40]))
    code = co.co_code; i = 0
    while i < len(code):
        op = ord(code[i]); s = ''
        if op >= 90:
            arg = ord(code[i+1]) | (ord(code[i+2]) << 8)
            n = co.co_names[arg] if arg < len(co.co_names) else '-'
            c = repr(co.co_consts[arg])[:30] if arg < len(co.co_consts) else '-'
            v = co.co_varnames[arg] if arg < len(co.co_varnames) else '-'
            s = '%5d n=%s c=%s v=%s' % (arg, n, c, v); step = 3
        else: step = 1
        w('%4d op%-3d %s' % (i, op, s))
        i += step
for spec in TARGETS:
    try: dis(*spec)
    except Exception as e: w('ERR %r %r' % (spec, e))
f.close()
