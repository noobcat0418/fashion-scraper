"""Paths, settings from .env, and the retailer list."""
import json
import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    # Minimal .env reader so we don't need python-dotenv. Real env vars win.
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass(frozen=True)
class Config:
    db_file: Path
    out_dir: Path
    retailers: list


def load() -> Config:
    _load_dotenv(ROOT / ".env")
    return Config(
        db_file=ROOT / "fashion.db",
        out_dir=ROOT / "out",
        retailers=json.loads((ROOT / "retailers.json").read_text(encoding="utf-8")),
    )
