# READ-ONLY: tables.ExpLevelTable (level -> levelExp), for the lobby level badge / exp bar.
import sys

out = open(OUT, 'w')
tables = vars(sys.modules['iDtsLevelSystem'])['tables']   # the module iDtsLevelSystem.getNextTotalExp reads
t = tables.ExpLevelTable          # attribute access loads the data table (no game method)
try:
    keys = sorted(t.keys())
    out.write('levels %d..%d (%d)\n' % (keys[0], keys[-1], len(keys)))
    for k in keys:
        out.write('%d %r\n' % (k, dict(t[k])))
except Exception as e:
    out.write('ExpLevelTable: %r %r\n' % (type(t), e))
out.close()
