# READ-ONLY: every Workshop vehicle cultivate chain (dts_appearance_cultivate_utils.VehicleCultivateDict)
# with each rule's target item, consumptions and unlock conditions, written as JSON to OUT.
# Reads data attributes only. The server copy is bigworld_gateway/server/extract/appearance_cultivate.json.
import sys
import json
cu = sys.modules['dts_appearance_cultivate_utils']
lp = vars(cu)['legacyProperties']


def entry(o):
    name = o.__class__.__name__
    if name == 'ConSumptionProp':
        return {'prop_id': o.PROP_ID, 'num': o.NUM}
    if name == 'ConSumptionCurrency':
        return {'currency_id': o.CURRENCY_ID, 'num': o.NUM}
    if name == 'UnlockConditionAppearance':
        return {'appearance_id': o.APPEARANCE_ID, 'num': o.NUM}
    return {'type': name}


chains = {}
for cid, rules in sorted(cu.VehicleCultivateDict.items()):
    d = lp.getDtsAppearanceCultivateData(cid)
    rows = []
    for rid in d.RULE_LIST:
        r = lp.getDtsAppearanceCultivateRuleData(rid)
        sec = r.SECOND_CONSUMPTION
        rows.append({'rule_id': rid, 'name': r.NAME, 'target': r.TARGET_APPEARANCE_ID,
                     'consume': [entry(x) for x in r.CONSUMPTION_LIST],
                     'second_consume': entry(sec) if sec is not None and sec.NUM else None,
                     'unlock': [entry(x) for x in r.UNLOCK_CONDITION_LIST]})
    chains[str(cid)] = {'name': d.NAME, 'rules': rows}
out = open(OUT, 'w')
json.dump({'kind': 'vehicle', 'chains': chains}, out, indent=1, sort_keys=True)
out.close()
