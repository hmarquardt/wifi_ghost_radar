from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from ghostradar.db import Database
from ghostradar.detector import Detector
from ghostradar.event_bus import BroadcastManager
from ghostradar.ingest import IngestPipeline
from ghostradar.models import IncomingSample
from main import AppConfig, create_app


async def exercise_pipeline(db_path: Path) -> None:
    db = Database(db_path)
    await db.initialize()
    pipeline = IngestPipeline(db, Detector(), BroadcastManager())
    sample = await pipeline.ingest_sample(
        IncomingSample(
            source="smoke-test",
            bfi_variance=0.42,
            amplitude_delta=0.2,
            phase_delta=0.1,
            rssi=-52,
            motion_score=0.7,
            raw_json={"test": True},
        )
    )
    assert sample.status in {"quiet", "disturbed", "motion", "occupied"}
    latest = await db.latest_sample()
    assert latest is not None
    assert latest["source"] == "smoke-test"


def exercise_api(db_path: Path) -> None:
    app = create_app(AppConfig(db_path=db_path, simulate=False))
    with TestClient(app) as client:
        response = client.get("/api/status")
        assert response.status_code == 200
        payload = response.json()
        assert "settings" in payload


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "ghostradar-smoke.sqlite"
        asyncio.run(exercise_pipeline(db_path))
        exercise_api(db_path)
    print("smoke test passed")


if __name__ == "__main__":
    main()
