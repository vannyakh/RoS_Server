@echo off
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -match 'ros_server.py|dns_server.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
echo Stopped.
