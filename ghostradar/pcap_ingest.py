from __future__ import annotations

from pathlib import Path
from typing import Iterable


def parse_pcap(path: str | Path) -> Iterable[dict]:
    """Placeholder PCAP parser.

    This validates that a capture exists, then returns no RF samples for now.
    TODO: integrate Wi-BFI / beamforming feedback extraction here once a real
    parser and adapter/driver workflow are selected. scapy or pyshark may help
    with frame metadata, but BFI extraction often requires chipset/driver-aware
    tooling beyond generic PCAP parsing.
    """

    capture = Path(path)
    if not capture.exists():
        raise FileNotFoundError(f"PCAP file does not exist: {capture}")
    if not capture.is_file():
        raise ValueError(f"PCAP path is not a file: {capture}")
    return []
