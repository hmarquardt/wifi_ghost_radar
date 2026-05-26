from __future__ import annotations

from typing import Any

from .db import Database
from .detector import Detector
from .event_bus import BroadcastManager
from .models import IncomingSample, ProcessedSample, utc_now_iso


class IngestPipeline:
    def __init__(self, db: Database, detector: Detector, bus: BroadcastManager) -> None:
        self.db = db
        self.detector = detector
        self.bus = bus

    async def ingest_sample(self, incoming: IncomingSample) -> ProcessedSample:
        settings = await self.db.get_settings()
        baseline = await self.db.latest_baseline()
        sample = self.detector.score_sample(incoming, settings, baseline)
        await self.db.insert_sample(sample)
        await self._handle_events(sample, settings)
        await self.bus.broadcast(
            {
                "type": "sample",
                "timestamp": sample.timestamp,
                "status": sample.status,
                "motion_score": round(sample.motion_score, 4),
                "bfi_variance": round(sample.bfi_variance, 6),
                "baseline_delta": sample.baseline_delta,
                "source": sample.source,
            }
        )
        return sample

    async def _handle_events(self, sample: ProcessedSample, settings: dict[str, str]) -> None:
        action, state = self.detector.observe_for_event(sample, settings)
        if action == "needs_open":
            event_id = await self.db.open_event(sample)
            state = self.detector.attach_event(event_id, sample)
            await self._broadcast_event("opened", state.event_id, sample, state.peak)
        elif action == "needs_update" and state is not None:
            await self.db.update_event(state.event_id, state.peak, state.total / state.count)
        elif action == "needs_close" and state is not None:
            await self.db.close_event(state.event_id, sample.timestamp, state.peak, state.total / state.count)
            await self._broadcast_event("closed", state.event_id, sample, state.peak)

    async def _broadcast_event(self, event_status: str, event_id: int, sample: ProcessedSample, peak: float) -> None:
        await self.bus.broadcast(
            {
                "type": "event",
                "event_status": event_status,
                "event_id": event_id,
                "timestamp": sample.timestamp or utc_now_iso(),
                "status": sample.status,
                "peak_motion_score": round(peak, 4),
            }
        )
