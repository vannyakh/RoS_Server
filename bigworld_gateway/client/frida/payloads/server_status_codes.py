# READ-ONLY: the numberSt -> spot icon / text tables the server-select screen uses
# (ui.UIServerList / ui.UILogin number_st_icon, number_st_txt, number_st_color), so
# server_registry.SERVER_STATUS_CODES can map smooth / busy / full / maintenance to real codes.
# Run at the login menu: bash tools/probe.sh client/frida/payloads/server_status_codes.py
import sys
f = open(OUT, 'w')
def w(s): f.write(s + '\n')
for mod_name in ('ui.UIServerList', 'ui.UILogin'):
    mod = sys.modules.get(mod_name)
    if mod is None:
        w('%s: not loaded' % mod_name)
        continue
    for cls_name in ('UIServerList', 'UILogin'):
        cls = getattr(mod, cls_name, None)
        if cls is None:
            continue
        for attr in ('number_st_icon', 'number_st_txt', 'number_st_color'):
            value = getattr(cls, attr, '<missing>')
            w('%s.%s.%s = %r' % (mod_name, cls_name, attr, value))
f.close()
