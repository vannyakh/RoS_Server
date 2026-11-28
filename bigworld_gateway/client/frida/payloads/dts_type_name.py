# READ-ONLY: const.DTS_TYPE_NAME and teamSizeToModeName (the result screen's mode label: run 5 showed
# "Solo-Zombie" for the gateway's gameType). Module import only.
out = open(OUT, 'w')
import const
for k in ('DTS_TYPE_NAME', 'teamSizeToModeName'):
    out.write('%s = %r\n' % (k, getattr(const, k, '<missing>')))
out.close()
