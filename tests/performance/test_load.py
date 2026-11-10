import csv
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import psutil


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_locust_profile_measures_a_short_run(tmp_path):
    port = _free_port()
    database = tmp_path / "load.db"
    env = os.environ.copy()
    env["DATABASE_URL"] = "sqlite+aiosqlite:///" + database.as_posix()
    env["JWT_SECRET"] = "test-secret-key-for-pytest-is-long-enough-for-hs256"
    env["APP_ENV"] = "development"
    env["DEBUG"] = "false"
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    host = f"http://127.0.0.1:{port}"
    try:
        deadline = time.time() + 30
        while time.time() < deadline:
            if server.poll() is not None:
                raise AssertionError(server.stdout.read() if server.stdout else "server exited")
            try:
                with urllib.request.urlopen(host + "/health", timeout=1) as response:
                    if response.status == 200:
                        break
            except OSError:
                time.sleep(0.3)
        else:
            raise AssertionError("server did not become healthy")
        csv_prefix = tmp_path / "locust"
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "locust",
                "-f",
                "tools/load_generator/locustfile.py",
                "--headless",
                "-u",
                "2",
                "-r",
                "2",
                "-t",
                "10s",
                "--host",
                host,
                "--csv",
                str(csv_prefix),
                "--exit-code-on-error",
                "1",
            ],
            capture_output=True,
            text=True,
            timeout=40,
        )
        assert completed.returncode == 0, completed.stdout + completed.stderr
        stats_path = Path(str(csv_prefix) + "_stats.csv")
        rows = list(csv.DictReader(stats_path.open(encoding="utf-8")))
        aggregated = next(row for row in rows if row["Name"] == "Aggregated")
        process = psutil.Process(server.pid)
        rss = process.memory_info().rss + sum(child.memory_info().rss for child in process.children(recursive=True))
        measured = {
            "users": 2,
            "duration_s": 10,
            "requests": int(aggregated["Request Count"]),
            "failures": int(aggregated["Failure Count"]),
            "requests_per_s": float(aggregated["Requests/s"]),
            "average_ms": float(aggregated["Average Response Time"]),
            "p50_ms": float(aggregated["50%"]),
            "p95_ms": float(aggregated["95%"]),
            "p99_ms": float(aggregated["99%"]),
            "server_rss_mb": round(rss / (1024 * 1024), 1),
            "server_cpu_percent": process.cpu_percent(interval=0.2),
            "note": "Two simulated players for 10 seconds. This is not match capacity and MAX_PLAYERS_PER_MATCH was not used as a capacity claim.",
        }
        assert measured["requests"] > 0
        assert measured["failures"] == 0
        destination = Path("reports/performance")
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "measured.json").write_text(json.dumps(measured, indent=2), encoding="utf-8")
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
