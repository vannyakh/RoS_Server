@echo off
rem Starts DNS + game server. Logs go to logs\. Usage: start.cmd   (stop with stop.cmd)
setlocal
cd /d %~dp0
call "%~dp0config.cmd"
if not exist logs mkdir logs
set PY=%~dp0..\.venv\Scripts\python.exe
if not exist "%PY%" set PY=%~dp0.venv\Scripts\python.exe
if not exist "%PY%" set PY=python
cd server
start "ros_dns" /b cmd /c ""%PY%" -u dns_server.py > ..\logs\dns.log 2> ..\logs\dns_err.log"
start "ros_server" /b cmd /c ""%PY%" -u ros_server.py > ..\logs\server.log 2> ..\logs\server_err.log"
echo Server starting on %ROS_PC_IP% (UDP/TCP 25000, DNS 53, HTTP 80, HTTPS 443). Logs: logs\
