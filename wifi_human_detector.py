"""
WiFi-based Human Detection System
Detects human presence/movement by monitoring WiFi signal strength (RSSI) changes
Works on Windows, macOS, and Linux
"""

import subprocess
import re
import time
import statistics
from collections import deque
from datetime import datetime
import platform

class WiFiHumanDetector:
    def __init__(self, ssid=None, window_size=20, threshold=5):
        """
        Initialize WiFi detector
        
        Args:
            ssid: Target WiFi network name (optional, will scan all if None)
            window_size: Number of readings to use for moving average
            threshold: RSSI change threshold to detect movement (dBm)
        """
        self.ssid = ssid
        self.window_size = window_size
        self.threshold = threshold
        self.rssi_history = deque(maxlen=window_size)
        self.os_type = platform.system()
        self.human_detected = False
        
    def get_wifi_networks_linux(self):
        """Scan WiFi networks on Linux"""
        try:
            result = subprocess.run(['nmcli', 'dev', 'wifi', 'list'], 
                                  capture_output=True, text=True)
            networks = {}
            for line in result.stdout.split('\n')[1:]:
                parts = re.split(r'\s{2,}', line.strip())
                if len(parts) >= 8:
                    ssid = parts[1]
                    signal = int(parts[6])
                    networks[ssid] = signal
            return networks
        except Exception as e:
            print(f"Error scanning networks on Linux: {e}")
            return {}
    
    def get_wifi_networks_windows(self):
        """Scan WiFi networks on Windows"""
        try:
            result = subprocess.run(['netsh', 'wlan', 'show', 'networks', 'mode=Bssid'],
                                  capture_output=True, text=True)
            networks = {}
            ssid = None
            for line in result.stdout.split('\n'):
                if 'SSID' in line and ':' in line:
                    ssid = line.split(':')[1].strip()
                    if ssid and ssid not in networks:
                        networks[ssid] = None
                if 'Signal' in line and '%' in line:
                    signal_percent = int(line.split(':')[1].strip().replace('%', ''))
                    # Convert percentage to dBm (approximate: 0% = -100dBm, 100% = -30dBm)
                    signal_dbm = -100 + (signal_percent * 0.7)
                    if ssid:
                        networks[ssid] = int(signal_dbm)
            return networks
        except Exception as e:
            print(f"Error scanning networks on Windows: {e}")
            return {}
    
    def get_wifi_networks_mac(self):
        """Scan WiFi networks on macOS"""
        try:
            result = subprocess.run(['/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport', '-s'],
                                  capture_output=True, text=True)
            networks = {}
            for line in result.stdout.split('\n')[1:]:
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 7:
                        ssid = parts[0]
                        try:
                            signal = int(parts[6])
                            networks[ssid] = signal
                        except ValueError:
                            continue
            return networks
        except Exception as e:
            print(f"Error scanning networks on macOS: {e}")
            return {}
    
    def get_wifi_signal_strength(self):
        """Get RSSI from available WiFi networks"""
        if self.os_type == 'Linux':
            networks = self.get_wifi_networks_linux()
        elif self.os_type == 'Windows':
            networks = self.get_wifi_networks_windows()
        elif self.os_type == 'Darwin':  # macOS
            networks = self.get_wifi_networks_mac()
        else:
            print(f"Unsupported OS: {self.os_type}")
            return None
        
        if not networks:
            return None
        
        # If specific SSID is set, use that; otherwise use strongest signal
        if self.ssid and self.ssid in networks:
            return networks[self.ssid]
        else:
            # Use the network with strongest signal
            return max(networks.values()) if networks.values() else None
    
    def analyze_signal_changes(self):
        """Analyze RSSI changes to detect human movement"""
        if len(self.rssi_history) < 2:
            return False
        
        # Calculate changes between consecutive readings
        changes = []
        history_list = list(self.rssi_history)
        for i in range(1, len(history_list)):
            change = abs(history_list[i] - history_list[i-1])
            changes.append(change)
        
        # Get average change
        avg_change = statistics.mean(changes)
        max_change = max(changes)
        
        # Detect human presence if changes exceed threshold
        if max_change > self.threshold:
            return True, avg_change, max_change
        return False, avg_change, max_change
    
    def detect(self):
        """Single detection cycle"""
        rssi = self.get_wifi_signal_strength()
        
        if rssi is None:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] No WiFi signal detected")
            return None
        
        self.rssi_history.append(rssi)
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] RSSI: {rssi} dBm | History: {list(self.rssi_history)}", end=" | ")
        
        if len(self.rssi_history) >= 3:
            result = self.analyze_signal_changes()
            if result[0]:
                print(f"🟢 HUMAN DETECTED (Avg Change: {result[1]:.2f}, Max Change: {result[2]:.2f} dBm)")
                self.human_detected = True
                return True
            else:
                print(f"No movement (Avg Change: {result[1]:.2f} dBm)")
                self.human_detected = False
        else:
            print("Calibrating...")
        
        return None
    
    def monitor(self, interval=2, duration=60):
        """
        Monitor WiFi signals for human detection
        
        Args:
            interval: Seconds between measurements
            duration: Total monitoring duration in seconds
        """
        print(f"\n{'='*70}")
        print(f"WiFi Human Detector Started")
        print(f"OS: {self.os_type}")
        print(f"Target SSID: {self.ssid if self.ssid else 'Any (strongest signal)'}")
        print(f"Detection Threshold: {self.threshold} dBm")
        print(f"Monitoring for {duration} seconds...\n")
        print(f"{'='*70}\n")
        
        start_time = time.time()
        try:
            while time.time() - start_time < duration:
                self.detect()
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\n\nMonitoring stopped by user")


# Example usage
if __name__ == "__main__":
    # Create detector instance
    # You can specify a WiFi network name, or leave None to use strongest signal
    detector = WiFiHumanDetector(ssid=None, window_size=20, threshold=5)
    
    # Start monitoring for 120 seconds, checking every 2 seconds
    detector.monitor(interval=2, duration=120)
