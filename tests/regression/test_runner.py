import os
import subprocess
import sys


def test_runner_refuses_the_development_database():
    env = os.environ.copy()
    env["DATABASE_URL"] = "sqlite+aiosqlite:///./ros_server.db"
    completed = subprocess.run(
        [sys.executable, "-m", "tools.test_runner", "--feature", "authentication"],
        env=env,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 2
    assert "ros_server.db" in completed.stderr


def test_runner_writes_a_feature_report():
    env = os.environ.copy()
    env["DATABASE_URL"] = "sqlite+aiosqlite:///./tmp_runner.db"
    env.setdefault("JWT_SECRET", "test-secret-key-for-pytest-is-long-enough-for-hs256")
    completed = subprocess.run(
        [sys.executable, "-m", "tools.test_runner", "--feature", "player"],
        env=env,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    report = __import__("pathlib").Path("reports/player/latest.json").read_text(encoding="utf-8")
    assert '"passed":' in report
    assert "password" not in report.lower()
