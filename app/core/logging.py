"""Process logging setup. The server log file is the source for the operations panel."""

import logging
from pathlib import Path


def server_log_path() -> Path:
    path = Path(__file__).resolve().parents[2] / "logs" / "server.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def configure_logging() -> None:
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    if not root.handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
        )
    path = server_log_path()
    if not any(isinstance(handler, logging.FileHandler) and Path(handler.baseFilename) == path for handler in root.handlers):
        file_handler = logging.FileHandler(path, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        root.addHandler(file_handler)


def tail_server_log(limit: int) -> list[str]:
    path = server_log_path()
    if not path.is_file():
        return []
    text = path.read_bytes()[-65_536:].decode("utf-8", errors="replace")
    return text.splitlines()[-limit:]
