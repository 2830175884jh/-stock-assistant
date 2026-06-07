from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    project_root: Path
    data_dir: Path
    a_share_dir: Path
    reports_dir: Path
    tushare_token: str
    ollama_base_url: str
    ollama_model: str
    request_timeout: float = 30.0


def _load_env_file(project_root: Path) -> None:
    env_path = project_root / ".env"
    try:
        from dotenv import load_dotenv

        load_dotenv(env_path)
        return
    except ImportError:
        pass

    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def find_project_root() -> Path:
    current = Path.cwd().resolve()
    for path in [current, *current.parents]:
        if (path / "pyproject.toml").exists() and (path / "src" / "stock_assistant").exists():
            return path
    return current


def load_settings(project_root: Path | None = None) -> Settings:
    root = (project_root or find_project_root()).resolve()
    _load_env_file(root)

    data_dir = root / "data"
    a_share_dir = data_dir / "a_share_out"
    reports_dir = data_dir / "reports"

    return Settings(
        project_root=root,
        data_dir=data_dir,
        a_share_dir=a_share_dir,
        reports_dir=reports_dir,
        tushare_token=os.getenv("TUSHARE_TOKEN", "").strip(),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/"),
        ollama_model=os.getenv("OLLAMA_MODEL", "qwen3:4b").strip() or "qwen3:4b",
        request_timeout=_float_env("OLLAMA_TIMEOUT", 60.0),
    )


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def ensure_output_dirs(settings: Settings) -> None:
    settings.a_share_dir.mkdir(parents=True, exist_ok=True)
    settings.reports_dir.mkdir(parents=True, exist_ok=True)
