# READ-ONLY: print rank_list_utils rank-type tables (which rank types use which list reply). Calls no game method.
import sys
out = open(OUT, 'w')
mod = sys.modules.get('rank_list_utils')
for k, v in sorted(vars(mod).items()):
    if k.isupper() or k in ('RankTypeStub', 'RankTypeName'):
        if isinstance(v, (int, long, str, list, tuple, dict, set, frozenset)):
            out.write('%s = %r\n' % (k, v))
out.close()
