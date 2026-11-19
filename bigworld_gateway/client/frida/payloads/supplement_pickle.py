# READ-ONLY: pickle (protocol 2) the client's own available-supplement dict and one box,
# and check they unpickle again, to see what the server reply can carry. No server call.
import sys
import cPickle
out = open(OUT, 'w')
su = sys.modules['supplement_utils']
d = su.getAvailableSupplementDictByTime()
one = d[1]
try:
    s1 = cPickle.dumps(one, 2)
    out.write('one box pickle len=%d reduce=%r\n' % (len(s1), one.__reduce_ex__(2)[:2]))
    out.write('one box state=%r\n' % (repr(one.__reduce_ex__(2)[2])[:1500],))
    back = cPickle.loads(s1)
    out.write('roundtrip ok type=%r\n' % type(back))
except Exception as e:
    out.write('one box pickle failed %r\n' % e)
try:
    s = cPickle.dumps(d, 2)
    out.write('dict pickle len=%d\n' % len(s))
    open(OUT + '.bin', 'wb').write(s)
except Exception as e:
    out.write('dict pickle failed %r\n' % e)
ids = dict((k, None) for k in d)
out.write('ids-only pickle len=%d\n' % len(cPickle.dumps(ids, 2)))
out.close()
