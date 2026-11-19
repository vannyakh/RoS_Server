import os
import subprocess
import sys

_here = os.path.dirname(os.path.abspath(__file__))
cfg_cmd = os.path.join(os.path.dirname(_here), "config.cmd")
lines = subprocess.check_output(f'cmd.exe /c "call {cfg_cmd} && set"', text=True).splitlines()
for l in lines:
    if '=' in l:
        k, v = l.split('=', 1)
        os.environ[k] = v

print(f"[*] Starting ros_server with config: METHOD_BASE={os.environ.get('METHOD_BASE')} SWITCH_TO={os.environ.get('SWITCH_TO')}")
os.chdir(_here)
__file__ = os.path.join(_here, "ros_server.py")
with open("ros_server.py", "rb") as f:
    code = compile(f.read(), "ros_server.py", "exec")
    exec(code, {"__name__": "__main__", "__file__": "ros_server.py"})
