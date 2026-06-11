# WiFi Human Detection

A small Python project for detecting human presence and movement using WiFi signals.

## What is in this project

- wifi_human_detector.py
  - RSSI-based detector for Linux, Windows, and macOS
  - Uses WiFi signal strength changes to detect movement
- wifi_csi_detector.py
  - CSI demo and a simple ML-style classifier
  - Useful for experimenting with more advanced WiFi sensing
- wifi_detection_utils.py
  - Calibration, config, and signal-processing helpers
- example_applications.py
  - Example occupancy/monitoring workflow

## Quick start

```bash
pip install -r requirements.txt
python wifi_human_detector.py
```

For the CSI demo:

```bash
python wifi_csi_detector.py
```

## Notes

- The RSSI detector relies on the OS WiFi tools available on your machine:
  - Linux: nmcli / NetworkManager
  - Windows: netsh
  - macOS: airport
- The CSI script in this repository is a demo and uses simulated data; real CSI hardware is required for live CSI sensing.

## Basic usage

You can also instantiate the detector directly in Python:

```python
from wifi_human_detector import WiFiHumanDetector

detector = WiFiHumanDetector(ssid=None, threshold=5)
detector.monitor(interval=2, duration=120)
```
