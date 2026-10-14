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
    scoring: dict
    llm_base_url: str
    llm_model: str
    llm_api_key: str


def load() -> Config:
    _load_dotenv(ROOT / ".env")
    return Config(
        db_file=ROOT / "fashion.db",
        out_dir=ROOT / "out",
        retailers=json.loads((ROOT / "retailers.json").read_text(encoding="utf-8")),
        scoring=json.loads((ROOT / "scoring.json").read_text(encoding="utf-8")),
        llm_base_url=os.environ.get("LLM_BASE_URL", "http://localhost:11434/v1"),
        llm_model=os.environ.get("LLM_MODEL", "qwen2.5:3b"),
        llm_api_key=os.environ.get("LLM_API_KEY", "ollama"),
    )
