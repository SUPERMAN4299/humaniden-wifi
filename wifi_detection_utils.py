"""
WiFi Human Detection - Utility Functions and Configuration
Includes setup helpers, signal processing, and calibration tools
"""

import json
import os
from pathlib import Path

class DetectionConfig:
    """Configuration management for detection systems"""
    
    # RSSI Detection Settings
    RSSI_WINDOW_SIZE = 20  # Number of readings for moving average
    RSSI_THRESHOLD = 5    # dBm change threshold for movement
    RSSI_INTERVAL = 2     # Seconds between readings
    
    # CSI Detection Settings
    CSI_WINDOW_SIZE = 50
    CSI_THRESHOLD = 0.15
    
    # Environment Calibration
    CALIBRATION_SAMPLES = 30
    CALIBRATION_INTERVAL = 1
    
    @staticmethod
    def load_config(filepath):
        """Load configuration from JSON file"""
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                config = json.load(f)
            return config
        return {}
    
    @staticmethod
    def save_config(config, filepath):
        """Save configuration to JSON file"""
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w') as f:
            json.dump(config, f, indent=4)


class EnvironmentCalibration:
    """
    Calibrate detection system for specific environment
    Helps establish baseline for movement detection
    """
    
    def __init__(self, detector, num_samples=30):
        self.detector = detector
        self.num_samples = num_samples
        self.baseline = None
        
    def run_calibration(self, interval=1):
        """
        Calibration routine - measure baseline RSSI without movement
        
        Args:
            interval: Seconds between readings
        """
        import time
        
        print("\n" + "="*70)
        print("CALIBRATION MODE - Do NOT move for 30 seconds")
        print("="*70)
        print("Measuring baseline signal strength...\n")
        
        readings = []
        for i in range(self.num_samples):
            rssi = self.detector.get_wifi_signal_strength()
            if rssi:
                readings.append(rssi)
                print(f"Sample {i+1}/{self.num_samples}: {rssi} dBm")
            time.sleep(interval)
        
        if readings:
            import statistics
            self.baseline = {
                'mean': statistics.mean(readings),
                'stdev': statistics.stdev(readings) if len(readings) > 1 else 0,
                'min': min(readings),
                'max': max(readings),
                'readings': readings
            }
            
            print(f"\n✓ Calibration Complete!")
            print(f"  Mean RSSI: {self.baseline['mean']:.1f} dBm")
            print(f"  Std Dev: {self.baseline['stdev']:.1f} dBm")
            print(f"  Range: {self.baseline['min']} to {self.baseline['max']} dBm\n")
            
            return self.baseline
        else:
            print("❌ Calibration failed - no signal detected")
            return None


class SignalProcessor:
    """Signal processing utilities for WiFi detection"""
    
    @staticmethod
    def apply_moving_average(values, window_size):
        """Apply moving average filter"""
        if len(values) < window_size:
            return values
        
        smoothed = []
        for i in range(len(values) - window_size + 1):
            window = values[i:i + window_size]
            smoothed.append(sum(window) / window_size)
        return smoothed
    
    @staticmethod
    def detect_spike(values, threshold):
        """Detect signal spikes above threshold"""
        if len(values) < 2:
            return False
        
        current = values[-1]
        previous = values[-2]
        change = abs(current - previous)
        
        return change > threshold
    
    @staticmethod
    def compute_autocorrelation(values, lag=1):
        """Compute autocorrelation for detecting periodic patterns"""
        if len(values) < lag + 1:
            return 0
        
        mean = sum(values) / len(values)
        c0 = sum((x - mean) ** 2 for x in values) / len(values)
        c_lag = sum((values[i] - mean) * (values[i + lag] - mean) 
                    for i in range(len(values) - lag)) / len(values)
        
        return c_lag / c0 if c0 != 0 else 0


class ReportGenerator:
    """Generate detection reports"""
    
    def __init__(self):
        self.detections = []
        
    def log_detection(self, timestamp, location, confidence, signal_strength):
        """Log a detection event"""
        self.detections.append({
            'timestamp': timestamp,
            'location': location,
            'confidence': confidence,
            'signal_strength': signal_strength
        })
    
    def generate_report(self):
        """Generate summary report"""
        if not self.detections:
            return "No detections recorded"
        
        report = "Detection Report\n"
        report += "=" * 50 + "\n"
        report += f"Total Detections: {len(self.detections)}\n\n"
        
        for detection in self.detections:
            report += f"Time: {detection['timestamp']}\n"
            report += f"  Confidence: {detection['confidence']:.2%}\n"
            report += f"  Signal: {detection['signal_strength']} dBm\n"
        
        return report


class HardwareInfo:
    """Check system and hardware capabilities"""
    
    @staticmethod
    def check_requirements():
        """Check if system has required tools"""
        import platform
        import shutil
        
        os_type = platform.system()
        issues = []
        
        if os_type == 'Linux':
            if not shutil.which('nmcli'):
                issues.append("❌ nmcli not found (install NetworkManager)")
        elif os_type == 'Windows':
            if not shutil.which('netsh'):
                issues.append("❌ netsh not found (Windows built-in, might need admin)")
        elif os_type == 'Darwin':  # macOS
            if not os.path.exists('/System/Library/PrivateFrameworks/Apple80211.framework'):
                issues.append("❌ airport utility not found")
        
        if issues:
            print("System Check - Issues found:")
            for issue in issues:
                print(f"  {issue}")
        else:
            print(f"✓ System check passed ({os_type})")
        
        return len(issues) == 0
    
    @staticmethod
    def check_csi_support():
        """Check if system supports CSI extraction"""
        issues = []
        
        try:
            # Check for Intel 5300 NIC
            import subprocess
            result = subprocess.run(['lspci'], capture_output=True, text=True)
            if 'Intel' not in result.stdout or '5300' not in result.stdout:
                issues.append("Intel 5300 NIC not detected")
        except:
            issues.append("Could not verify NIC (Linux only)")
        
        if issues:
            print("CSI Support - Limited:")
            for issue in issues:
                print(f"  ⚠ {issue}")
            return False
        
        print("✓ CSI support verified")
        return True


# Example usage and system check
if __name__ == "__main__":
    print("\nWiFi Human Detection - System Check\n")
    HardwareInfo.check_requirements()
    print()
    HardwareInfo.check_csi_support()
