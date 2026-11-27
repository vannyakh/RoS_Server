# READ-ONLY: in-match player's curr_equip_parts / characterInfo dress, and the hall prop data
# (PART, STYLE) of the worn appearance items. Calls only data getters.
import sys
import BigWorld
out = open(OUT, 'w')
p = BigWorld.player()
for k in ('curr_equip_parts', 'dtsWearableAppearanceList', 'dtsBodyAppearanceList'):
    out.write('%s = %r\n' % (k, getattr(p, k, 'MISSING')))
ci = getattr(p, 'characterInfo', None)
out.write('characterInfo.dtsDressInfo = %r\n' % (getattr(ci, 'dtsDressInfo', None),))
lp = sys.modules.get('legacyProperties') or sys.modules.get('shared.lib.gametoolslib.legacyProperties')
for m in list(sys.modules):
    if m.endswith('legacyProperties') and sys.modules[m] is not None:
        lp = sys.modules[m]
        break
for aid in list(getattr(p, 'dtsWearableAppearanceList', []) or []) + [111900]:
    try:
        d = lp.getDtsHallPropData(aid)
        pt = d.PROP_TYPE
        out.write('hallprop %d PART=%r STYLE=%r GENDER=%r\n' % (aid, getattr(pt, 'PART', None), getattr(pt, 'STYLE', None), getattr(pt, 'GENDER', None)))
    except Exception as e:
        out.write('hallprop %d error %r\n' % (aid, e))
out.close()
