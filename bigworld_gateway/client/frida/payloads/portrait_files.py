# READ-ONLY: does the game's resource system have the built-in portrait images? C_file.find_file and
# C_file.file_exists-style lookups only, calibrated on a file known to exist.
import sys

out = open(OUT, 'w')
import C_file
out.write('C_file: %r\n' % ([n for n in dir(C_file) if not n.startswith('_')],))
names = ['entities/defs/Athlete.def', 'ui/images/avatar/portrait/20001_on.png', 'ui/images/avatar/portrait/20002_on.png',
         'ui/images/avatar/portrait/1_on.png', 'ui/images/avatar/portrait/30001_on.png', 'ui/images/avatar/portrait/no_such.png']
for n in names:
    for fn in ('get_file_info', 'find_res_file'):
        try:
            r = getattr(C_file, fn)(n, '')
            out.write('%s(%r) = %r\n' % (fn, n, r if not isinstance(r, str) else r[:80]))
        except Exception as e:
            out.write('%s(%r): %r\n' % (fn, n, e))
out.close()
