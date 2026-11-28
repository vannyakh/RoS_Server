# READ-ONLY: dump the BattleGroundPropAppearanceType (wardrobe ITEMS tab) slot data:
# getBattleGroundPropAppearanceAllPropIDs (DtsAppearance.isForSameBattleGroundProp = the two
# sets overlap), gender, category, part/style. Calls only static data lookups.
import sys

out = open(OUT, 'w')
utils = None
for name, mod in list(sys.modules.items()):
    if mod is not None and name.endswith('dts_appearance_utils') and hasattr(mod, 'getBattleGroundPropAppearanceAllPropIDs'):
        utils = mod
        out.write('# module %s\n' % name)
        break
dtsa = None
for name, mod in list(sys.modules.items()):
    if mod is not None and name.endswith('DtsAppearance') and hasattr(mod, 'BattleGroundPropAppearanceType'):
        dtsa = mod
        break
ids = IDS
res = {}
for pid in ids:
    row = {}
    for fn in ('getBattleGroundPropAppearanceAllPropIDs', 'getBattleGroundPropAppearancePropGender',
               'getBattleGroundPropAppearanceCategory', 'getBattleGroundPropAppearancePropPartAndStyle'):
        f = getattr(utils, fn, None)
        try:
            v = f(pid) if f else None
            if isinstance(v, (set, frozenset, tuple)):
                v = list(v)
            row[fn[len('getBattleGroundPropAppearance'):]] = v
        except Exception as e:
            row[fn[len('getBattleGroundPropAppearance'):]] = 'ERR %r' % (e,)
    res[pid] = row
out.write(repr(res))
out.write('\n# has isSameTypeFlyDecorate: %r\n' % (hasattr(getattr(dtsa, 'BattleGroundPropAppearanceType', None), 'isSameTypeFlyDecorate'),))
out.close()
