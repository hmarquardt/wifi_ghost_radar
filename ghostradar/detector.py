from __future__ import annotations

from dataclasses import dataclass

from .models import IncomingSample, ProcessedSample, Status, utc_now_iso


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


@dataclass(slots=True)
class EventState:
    event_id: int
    peak: float
    total: float
    count: int
    quiet_ticks: int = 0


class Detector:
    def __init__(self) -> None:
        self._occupied_seconds = 0.0
        self._event: EventState | None = None

    def score_sample(
        self,
        sample: IncomingSample,
        settings: dict[str, str],
        baseline: dict | None,
    ) -> ProcessedSample:
        baseline_delta: float | None = None
        if baseline:
            mean = float(baseline["mean_bfi_variance"])
            std = max(float(baseline["std_bfi_variance"]), 0.000001)
            z = (sample.bfi_variance - mean) / std
            score = clamp(z / 6.0, 0.0, 1.0)
            baseline_delta = z
        elif sample.motion_score is not None:
            score = clamp(sample.motion_score, 0.0, 1.0)
        else:
            # Safe fallback normalization for manual samples before calibration exists.
            score = clamp((sample.bfi_variance - 0.05) / 0.35, 0.0, 1.0)

        interval = float(settings.get("simulator_interval_seconds", "0.5"))
        status = self._status_from_score(score, settings, interval)
        return ProcessedSample(
            **sample.model_dump(exclude={"timestamp", "motion_score"}),
            timestamp=sample.timestamp or utc_now_iso(),
            motion_score=score,
            status=status,
            baseline_delta=baseline_delta,
        )

    def _status_from_score(self, score: float, settings: dict[str, str], interval: float) -> Status:
        disturbed = float(settings.get("threshold_disturbed", "0.25"))
        motion = float(settings.get("threshold_motion", "0.55"))
        occupied = float(settings.get("threshold_occupied", "0.80"))
        hold = float(settings.get("occupied_hold_seconds", "5"))

        if score >= occupied:
            self._occupied_seconds += interval
        else:
            self._occupied_seconds = 0.0

        if score >= occupied and self._occupied_seconds >= hold:
            return "occupied"
        if score >= motion:
            return "motion"
        if score >= disturbed:
            return "disturbed"
        return "quiet"

    @property
    def active_event(self) -> EventState | None:
        return self._event

    def attach_event(self, event_id: int, sample: ProcessedSample) -> EventState:
        self._event = EventState(event_id=event_id, peak=sample.motion_score, total=sample.motion_score, count=1)
        return self._event

    def observe_for_event(self, sample: ProcessedSample, settings: dict[str, str]) -> tuple[str, EventState | None]:
        disturbed = float(settings.get("threshold_disturbed", "0.25"))
        if self._event is None:
            return ("needs_open", None) if sample.status in {"motion", "occupied"} else ("none", None)

        state = self._event
        state.peak = max(state.peak, sample.motion_score)
        state.total += sample.motion_score
        state.count += 1
        if sample.motion_score < disturbed:
            state.quiet_ticks += 1
        else:
            state.quiet_ticks = 0
        if state.quiet_ticks >= 3:
            self._event = None
            return "needs_close", state
        return "needs_update", state
