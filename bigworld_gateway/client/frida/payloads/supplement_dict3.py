# READ-ONLY: evaluate the client's pure local helper getAvailableSupplementDictByTime()
# (reads local data tables only, no server call, no state change) and print its shape.
import sys
out = open(OUT, 'w')
su = sys.modules['supplement_utils']
lp = su.legacyProperties
it = list(lp.iterSupplementData())
out.write('iterSupplementData n=%d first=%r\n' % (len(it), it[:2] if len(repr(it[:2])) < 3000 else repr(it[:2])[:3000]))
d = su.getAvailableSupplementDictByTime()
out.write('avail type=%r n=%d\n' % (type(d), len(d)))
for k, v in sorted(d.items())[:5]:
    out.write('  %r -> %r (%r)\n' % (k, v if len(repr(v)) < 1500 else repr(v)[:1500], type(v)))
out.write('avail keys=%r\n' % sorted(d.keys()))
for k in sorted(d.keys()):
    out.write('  kind %r=%r freeMax=%r\n' % (k, su.getSupplementKind(k), su.getSupplementFreeLotteryMaxTimes(k)))
out.close()
