# Makes the client send its own door / pickup requests so the gateway can log the wire bytes
# (RO-057). Calls only exposed server methods that the UI itself would call; nothing is skipped
# or faked on the client. Distinct argument values make the messages easy to find in the log.
import BigWorld
import Globals

out = open(OUT, 'w')
def w(s): out.write(s + '\n')

se = getattr(Globals, 'spaceEntity', None)
w('spaceEntity=%r' % (se,))
if se is not None:
    for name, args in (('openElement', (832, 1)), ('closeElement', (832,)), ('openElement', (832, 1))):
        try:
            getattr(se.cell, name)(*args)
            w('called %s%r' % (name, args))
        except Exception as e:
            w('failed %s: %r' % (name, e))
    w('cell attrs: %r' % [n for n in dir(se.cell) if 'lement' in n or 'ick' in n])
out.close()
