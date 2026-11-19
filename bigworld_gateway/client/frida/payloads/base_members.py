# READ-ONLY: the player's base mailbox member names in the client's own order
# (one per line, "index name"). Calls nothing on the server.
import BigWorld
out = open(OUT, 'w')
for i, n in enumerate(BigWorld.player().base.__members__):
    out.write('%d %s\n' % (i, n))
out.close()
