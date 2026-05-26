#!/usr/bin/env bash
set -euo pipefail

cat <<'NOTES'
Wi-Fi Ghost Radar monitor-mode notes

Inspection commands:
  lsusb
  ip link
  iw dev
  iw list | grep -A 10 "Supported interface modes"

Manual monitor-mode test commands. Review interface names first.
These commands mutate the selected interface and may disrupt networking:
  sudo ip link set wlan1 down
  sudo iw dev wlan1 set type monitor
  sudo ip link set wlan1 up
  sudo tcpdump -i wlan1 -I -s 0 -w test.pcap

Warnings:
  - Interface names may differ.
  - TP-Link Archer T4U chipset revisions matter.
  - Driver support can be annoying.
  - This project does not make unsupported hardware support monitor mode.
  - Real BFI extraction may require extra tools or driver work.
NOTES
