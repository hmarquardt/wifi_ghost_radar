from __future__ import annotations

import argparse
import asyncio
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles

from ghostradar.config import AppConfig, DEFAULT_DB_PATH
from ghostradar.db import Database
from ghostradar.detector import Detector
from ghostradar.event_bus import BroadcastManager
from ghostradar.ingest import IngestPipeline
from ghostradar.models import BaselineRequest, EventLabelRequest, IncomingSample, SettingsUpdate, utc_now_iso
from ghostradar.pcap_ingest import parse_pcap
from ghostradar.simulator import Simulator


ROOT = Path(__file__).resolve().parent


class Runtime:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.db = Database(config.db_path)
        self.bus = BroadcastManager()
        self.detector = Detector()
        self.pipeline = IngestPipeline(self.db, self.detector, self.bus)
        self.simulator = Simulator(self.pipeline)
        self.heartbeat_task: asyncio.Task | None = None

    async def start(self) -> None:
        await self.db.initialize()
        await self.db.update_settings({"host": self.config.host, "port": self.config.port})
        if self.config.simulate:
            await self.simulator.start()
        self.heartbeat_task = asyncio.create_task(self._heartbeats())

    async def stop(self) -> None:
        await self.simulator.stop()
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            try:
                await self.heartbeat_task
            except asyncio.CancelledError:
                pass

    async def _heartbeats(self) -> None:
        while True:
            await asyncio.sleep(10)
            await self.bus.broadcast({"type": "heartbeat", "timestamp": utc_now_iso()})


def create_app(config: AppConfig | None = None) -> FastAPI:
    runtime = Runtime(config or AppConfig())

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await runtime.start()
        yield
        await runtime.stop()

    app = FastAPI(title="Wi-Fi Ghost Radar", lifespan=lifespan)
    app.state.runtime = runtime
    app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")

    @app.get("/")
    async def dashboard() -> FileResponse:
        return FileResponse(ROOT / "static" / "index.html")

    @app.websocket("/ws/live")
    async def live(websocket: WebSocket) -> None:
        await runtime.bus.connect(websocket)
        try:
            await websocket.send_json({"type": "heartbeat", "timestamp": utc_now_iso()})
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            await runtime.bus.disconnect(websocket)
        except Exception:
            await runtime.bus.disconnect(websocket)

    @app.get("/api/status")
    async def status() -> dict[str, Any]:
        latest = await runtime.db.latest_sample()
        baselines = await runtime.db.get_baselines()
        events = await runtime.db.get_events()
        return {
            "timestamp": utc_now_iso(),
            "simulator_running": runtime.simulator.running,
            "latest_sample": latest,
            "latest_event": events[0] if events else None,
            "latest_baseline": baselines[0] if baselines else None,
            "settings": await runtime.db.get_settings(),
        }

    @app.get("/api/samples")
    async def samples(limit: int = 500) -> list[dict[str, Any]]:
        return await runtime.db.get_samples(limit)

    @app.get("/api/events")
    async def events() -> list[dict[str, Any]]:
        return await runtime.db.get_events()

    @app.get("/api/baselines")
    async def baselines() -> list[dict[str, Any]]:
        return await runtime.db.get_baselines()

    @app.get("/api/settings")
    async def settings() -> dict[str, str]:
        return await runtime.db.get_settings()

    @app.post("/api/settings")
    async def update_settings(update: SettingsUpdate) -> dict[str, str]:
        return await runtime.db.update_settings(update.settings)

    @app.post("/api/baseline/create-from-recent")
    async def create_baseline(request: BaselineRequest) -> dict[str, Any]:
        try:
            baseline = await runtime.db.create_baseline_from_recent(request.duration_seconds, request.notes)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        await runtime.bus.broadcast({"type": "baseline", "timestamp": utc_now_iso(), "baseline": baseline})
        return baseline

    @app.post("/api/events/{event_id}/label")
    async def label_event(event_id: int, request: EventLabelRequest) -> dict[str, Any]:
        try:
            event = await runtime.db.label_event(event_id, request.label, request.notes)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        await runtime.bus.broadcast({"type": "event_label", "timestamp": utc_now_iso(), "event": event})
        return event

    @app.post("/api/simulate/start")
    async def simulate_start() -> dict[str, Any]:
        await runtime.simulator.start()
        return {"simulator_running": runtime.simulator.running}

    @app.post("/api/simulate/stop")
    async def simulate_stop() -> dict[str, Any]:
        await runtime.simulator.stop()
        return {"simulator_running": runtime.simulator.running}

    @app.post("/api/ingest/sample")
    async def ingest_sample(sample: IncomingSample) -> dict[str, Any]:
        processed = await runtime.pipeline.ingest_sample(sample)
        return processed.model_dump()

    @app.post("/api/ingest/pcap")
    async def ingest_pcap(file: UploadFile = File(...)) -> dict[str, Any]:
        suffix = Path(file.filename or "capture.pcap").suffix or ".pcap"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            path = Path(tmp.name)
            tmp.write(await file.read())
        try:
            parsed = list(parse_pcap(path))
            for item in parsed:
                await runtime.pipeline.ingest_sample(IncomingSample(**item))
        finally:
            path.unlink(missing_ok=True)
        return {
            "accepted": True,
            "parsed_samples": len(parsed),
            "message": "PCAP accepted. Real Wi-BFI extraction is a future integration hook.",
        }

    @app.get("/api/export/samples.csv")
    async def export_samples() -> Response:
        csv_text = await runtime.db.export_csv("samples")
        return PlainTextResponse(csv_text, media_type="text/csv")

    @app.get("/api/export/events.csv")
    async def export_events() -> Response:
        csv_text = await runtime.db.export_csv("events")
        return PlainTextResponse(csv_text, media_type="text/csv")

    @app.get("/api/export/recent.json")
    async def export_recent() -> JSONResponse:
        return JSONResponse(await runtime.db.recent_export())

    return app


app = create_app()


def parse_args() -> AppConfig:
    parser = argparse.ArgumentParser(description="Run Wi-Fi Ghost Radar locally.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8000, type=int)
    parser.add_argument("--simulate", action="store_true", default=None)
    parser.add_argument("--no-simulate", action="store_true")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()
    simulate = True
    if args.simulate is True:
        simulate = True
    if args.no_simulate:
        simulate = False
    return AppConfig(
        db_path=Path(args.db_path),
        host=args.host,
        port=args.port,
        simulate=simulate,
        debug=args.debug,
    )


if __name__ == "__main__":
    cfg = parse_args()
    uvicorn.run(
        create_app(cfg),
        host=cfg.host,
        port=cfg.port,
        log_level="debug" if cfg.debug else "info",
    )
