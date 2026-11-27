# READ-ONLY (lane 5): vehicle and airdrop constants and data tables. Data getters and getattr only.
#   const.PlaneWorkMode / HeritageMode / DriveVehicleType / VEHICLE_DRIVER_SOCKET / DTS_FUEL_PROP_ID
#   legacyProperties.getVehicleData(id) / getLandVehicleData(id): which ids exist, model and seat fields
#   map 700 vehicle spawn points if the level config has them; airdrop timing constants
import sys
out = open(OUT, 'w')
def w(s):
    out.write(s + '\n')
def attrs(o, upper=True):
    d = {}
    for a in dir(o):
        if a.startswith('_') or (upper and not a.isupper()):
            continue
        try:
            v = getattr(o, a)
        except Exception as e:
            v = 'ERR %r' % e
        if callable(v):
            continue
        d[a] = v
    return d
try:
    import const
    for n in ('PlaneWorkMode', 'HeritageMode', 'DriveVehicleType', 'VehicleOpLevel', 'GameEnterType'):
        w('const.%s %r' % (n, attrs(getattr(const, n, None))))
    for n in ('VEHICLE_DRIVER_SOCKET', 'DTS_FUEL_PROP_ID', 'AIR_DROP', 'AirDrop', 'VEHICLE_POS_DIST_CORRECT_THRESHOLD',
              'DTS_PROP_TRAP_RADIUS', 'SearchAirDrop'):
        w('const.%s %r' % (n, getattr(const, n, None)))
except Exception as e:
    w('const ERR %r' % e)
try:
    import dts_const
    w('dts_const %r' % dict((k, v) for k, v in attrs(dts_const).items()
                             if any(s in k for s in ('VEHICLE', 'AIR', 'DROP', 'FUEL', 'CHARACTERTYPE', 'HERITAGE'))))
except Exception as e:
    w('dts_const ERR %r' % e)
try:
    import dts_utils
    w('dts_utils %r' % dict((k, v) for k, v in attrs(dts_utils).items() if 'AIR' in k or 'DROP' in k))
except Exception as e:
    w('dts_utils ERR %r' % e)
try:
    import legacyProperties as lp
    for getter in ('getVehicleData', 'getLandVehicleData'):
        fn = getattr(lp, getter, None)
        if fn is None:
            w('%s missing' % getter); continue
        found = 0
        for i in list(range(0, 400)) + list(range(1000, 1100)) + list(range(10000, 10100)) + list(range(20000, 20100)):
            try:
                d = fn(i)
            except Exception:
                continue
            if d is None:
                continue
            found += 1
            if found <= 80:
                a = attrs(d)
                keep = dict((k, a[k]) for k in a if any(s in k for s in (
                    'NAME', 'MODEL', 'MESH', 'CATEGORY', 'SEAT', 'SOCKET', 'HP', 'SPEED', 'FUEL', 'ID', 'TYPE', 'WATER')))
                w('%s(%d) %r' % (getter, i, keep))
        w('%s: %d ids' % (getter, found))
except Exception as e:
    w('legacyProperties ERR %r' % e)
try:
    import maps_utils
    bp = maps_utils.getBattleGroundParamData(700)
    a = attrs(bp)
    w('BattleGroundParam(700) keys %r' % sorted(a.keys()))
    w('BattleGroundParam(700) air/vehicle %r' % dict((k, a[k]) for k in a if any(s in k for s in ('AIR', 'DROP', 'VEHICLE', 'CAR', 'PLANE'))))
except Exception as e:
    w('maps_utils ERR %r' % e)
try:
    import levelConfig
    w('levelConfig %r' % [n for n in dir(levelConfig) if not n.startswith('__')])
except Exception as e:
    w('levelConfig ERR %r' % e)
out.close()
