# READ-ONLY: SysMailTypeEnum values and the mail-detail prop parsing used by ui.UISystemMail.
import sys
import types
out = open(OUT, 'w')
m = sys.modules.get('ui.UISystemMail') or __import__('ui.UISystemMail', fromlist=['x'])
e = vars(m).get('SysMailTypeEnum')
out.write('SysMailTypeEnum=%r\n' % dict((k, v) for k, v in vars(e).items() if not k.startswith('_')) if e else 'no enum\n')
c = m.UISystemMail.onLoadMailDetail.func_code
out.write('onLoadMailDetail varnames=%r\n' % (c.co_varnames,))
out.write('consts=%r\n' % ([x for x in c.co_consts if not isinstance(x, types.CodeType)],))
import BigWorld
p = BigWorld.player()
out.write('mailsCache=%r\n' % (getattr(getattr(p, 'chatCache', None), 'mailsCache', None),))
out.close()
