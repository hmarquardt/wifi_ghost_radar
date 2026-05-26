from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = ROOT / "data" / "ghostradar.sqlite"

DEFAULT_SETTINGS: dict[str, str] = {
    "threshold_disturbed": "0.25",
    "threshold_motion": "0.55",
    "threshold_occupied": "0.80",
    "occupied_hold_seconds": "5",
    "sample_retention_days": "7",
    "active_source": "simulator",
    "simulator_interval_seconds": "0.5",
    "host": "127.0.0.1",
    "port": "8000",
}


@dataclass(slots=True)
class AppConfig:
    db_path: Path = DEFAULT_DB_PATH
    host: str = "127.0.0.1"
    port: int = 8000
    simulate: bool = True
    debug: bool = False
