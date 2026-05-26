from __future__ import annotations

import asyncio
import math
import random
from dataclasses import dataclass

from .ingest import IngestPipeline
from .models import IncomingSample


@dataclass(slots=True)
class MotionWave:
    kind: str
    age: float
    duration: float
    amplitude: float


class Simulator:
    def __init__(self, pipeline: IngestPipeline, seed: int | None = None) -> None:
        self.pipeline = pipeline
        self.random = random.Random(seed)
        self._task: asyncio.Task | None = None
        self._running = False
        self._waves: list[MotionWave] = []
        self._tick = 0

    @property
    def running(self) -> bool:
        return self._running

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run(), name="ghostradar-simulator")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _run(self) -> None:
        while self._running:
            settings = await self.pipeline.db.get_settings()
            interval = max(0.25, min(1.0, float(settings.get("simulator_interval_seconds", "0.5"))))
            await self.pipeline.ingest_sample(self._make_sample(interval))
            await asyncio.sleep(interval)

    def _make_sample(self, interval: float) -> IncomingSample:
        self._tick += 1
        if self.random.random() < 0.018:
            self._waves.append(MotionWave("human", 0, self.random.uniform(7, 15), self.random.uniform(0.62, 0.95)))
        if self.random.random() < 0.025:
            self._waves.append(MotionWave("pet", 0, self.random.uniform(4, 9), self.random.uniform(0.32, 0.58)))
        if self.random.random() < 0.012:
            self._waves.append(MotionWave("disturbance", 0, self.random.uniform(2, 5), self.random.uniform(0.22, 0.38)))

        score = 0.05 + self.random.gauss(0, 0.018)
        active: list[dict] = []
        for wave in list(self._waves):
            wave.age += interval
            if wave.age >= wave.duration:
                self._waves.remove(wave)
                continue
            x = wave.age / wave.duration
            envelope = math.sin(math.pi * x) ** 1.4
            wobble = 0.08 * math.sin(14 * x + self.random.random())
            contribution = max(0.0, wave.amplitude * envelope + wobble)
            score += contribution
            active.append({"kind": wave.kind, "contribution": round(contribution, 3)})

        hvac = 0.08 * (math.sin(self._tick / 18) + 1) / 2
        if self._tick % 240 < 90:
            score += hvac
        score = max(0.0, min(1.0, score))

        bfi_variance = 0.08 + score * 0.55 + self.random.gauss(0, 0.012)
        return IncomingSample(
            source="simulator",
            channel=self.random.choice([36, 40, 44, 48, 149, 153, 157, 161]),
            frequency_mhz=self.random.choice([5180, 5200, 5220, 5240, 5745, 5765, 5785, 5805]),
            bssid="02:00:00:aa:bb:cc",
            client_mac=None,
            rssi=-47 + self.random.gauss(0, 2.5) - score * 6,
            bfi_variance=max(0.001, bfi_variance),
            amplitude_delta=score * self.random.uniform(0.8, 1.3),
            phase_delta=score * self.random.uniform(0.25, 0.9),
            motion_score=score,
            raw_json={"active_waves": active, "hvac_component": round(hvac, 3), "tick": self._tick},
        )
