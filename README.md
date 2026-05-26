# wifi-ghost-radar

A local-first Wi-Fi RF disturbance dashboard prototype. It uses a Python/FastAPI backend, SQLite storage, WebSockets, and a vanilla HTML/CSS/JS dashboard to visualize simulated Wi-Fi capture-derived signal metrics.

## What this is

This is a local Wi-Fi RF disturbance dashboard prototype. It watches a stream of RF-derived samples and learns a "quiet house" baseline. When rolling disturbance exceeds configurable thresholds, it records possible motion or occupancy events.

## What this is not

This is not a production security system, not a guaranteed intruder detector, and not a finished BFI extraction system. The first version deliberately does not pretend real beamforming feedback extraction is solved.

## Why simulator-first

The simulator lets the UI, database, detector, ingestion pipeline, event handling, and export paths be developed before RF capture is reliable. Real RF/BFI parsing can be plugged in later without rewriting the dashboard or detector flow.

## Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Run

```bash
uv sync
uv run python main.py --simulate
```

Open:

```text
http://127.0.0.1:8000
```

The app binds to `127.0.0.1` by default and starts the simulator unless `--no-simulate` is passed.

Useful runtime options:

```bash
uv run python main.py --host 127.0.0.1 --port 8000
uv run python main.py --no-simulate
uv run python main.py --db-path data/ghostradar.sqlite --debug
```

## Smoke test

```bash
uv run python -m compileall .
uv run python scripts/smoke_test.py
```

## Hardware assumptions

The future live-capture target is a Linux machine plus a TP-Link Archer T4U AC1300 or similar 5 GHz monitor-mode-capable USB Wi-Fi adapter.

## T4U / monitor-mode notes

Inspection commands:

```bash
lsusb
ip link
iw dev
iw list | grep -A 10 "Supported interface modes"
```

Monitor-mode test commands:

```bash
sudo ip link set wlan1 down
sudo iw dev wlan1 set type monitor
sudo ip link set wlan1 up
sudo tcpdump -i wlan1 -I -s 0 -w test.pcap
```

Warnings:

- Interface names may differ.
- Chipset revisions matter.
- Driver support may be annoying.
- This project does not magically make a dongle support monitor mode.
- Real BFI extraction may require additional tools or driver work.

The helper script prints these notes without changing network interfaces:

```bash
uv run bash scripts/monitor_mode_notes.sh
```

## Future Wi-BFI integration

Connect a real parser in:

- `ghostradar/pcap_ingest.py`
- `ghostradar/ingest.py`

The intended flow is:

```text
sample source -> ingest pipeline -> detector -> SQLite -> event handling -> WebSocket broadcast
```

`ghostradar/pcap_ingest.py` currently validates uploaded PCAP files and returns no samples. That is intentional. Real BFI extraction is the hard future work and may need chipset-specific tools, custom drivers, or a Wi-BFI parser beyond generic PCAP libraries.

## API overview

- `GET /` serves the dashboard.
- `GET /ws/live` streams live sample, event, and heartbeat messages.
- `GET /api/status`
- `GET /api/samples?limit=500`
- `GET /api/events`
- `GET /api/baselines`
- `GET /api/settings`
- `POST /api/settings`
- `POST /api/baseline/create-from-recent`
- `POST /api/events/{id}/label`
- `POST /api/simulate/start`
- `POST /api/simulate/stop`
- `POST /api/ingest/sample`
- `POST /api/ingest/pcap`
- `GET /api/export/samples.csv`
- `GET /api/export/events.csv`
- `GET /api/export/recent.json`

## Privacy/legal note

Only capture traffic in your own environment. This project is for local experimentation and has no cloud dependencies.
