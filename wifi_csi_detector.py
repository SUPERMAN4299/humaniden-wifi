"""
Advanced WiFi CSI (Channel State Information) Based Human Detection
More sensitive than RSSI - can detect subtle environmental changes
Requires special hardware: Intel 5300 NIC or compatible router
"""

import numpy as np
from collections import deque
from datetime import datetime
import json

class WiFiCSIDetector:
    """
    CSI-based human detector
    CSI provides finer-grained signal information than RSSI
    Can detect movement through walls with higher accuracy
    """
    
    def __init__(self, window_size=50, threshold=0.15):
        """
        Initialize CSI detector
        
        Args:
            window_size: Number of CSI samples to analyze
            threshold: Variance threshold for movement detection
        """
        self.window_size = window_size
        self.threshold = threshold
        self.csi_history = deque(maxlen=window_size)
        self.variance_history = deque(maxlen=10)
        
    def generate_mock_csi(self, has_movement=False):
        """
        Generate mock CSI data for demonstration
        In real implementation, this would come from WiFi hardware
        """
        # CSI is typically a 30x30 matrix of complex numbers
        base_csi = np.random.randn(30, 30) + 1j * np.random.randn(30, 30)
        
        if has_movement:
            # Add movement signature - increased variance
            noise = np.random.randn(30, 30) * 2 + 1j * np.random.randn(30, 30) * 2
            base_csi += noise
        
        return base_csi
    
    def compute_csi_amplitude(self, csi):
        """Compute amplitude from complex CSI matrix"""
        return np.abs(csi)
    
    def compute_csi_phase(self, csi):
        """Compute phase from complex CSI matrix"""
        return np.angle(csi)
    
    def detect_movement_from_csi(self, csi1, csi2):
        """
        Detect movement by comparing two CSI samples
        Returns correlation coefficient
        """
        amp1 = self.compute_csi_amplitude(csi1)
        amp2 = self.compute_csi_amplitude(csi2)
        
        # Compute correlation
        correlation = np.corrcoef(amp1.flatten(), amp2.flatten())[0, 1]
        
        return correlation
    
    def analyze_csi_variance(self):
        """Analyze variance in CSI history to detect movement"""
        if len(self.csi_history) < 2:
            return False, 0
        
        csi_list = list(self.csi_history)
        
        # Compute amplitude for all CSI samples
        amplitudes = [self.compute_csi_amplitude(csi) for csi in csi_list]
        
        # Calculate variance in amplitudes
        amplitude_values = np.array([amp.flatten() for amp in amplitudes])
        variance = np.var(amplitude_values)
        
        self.variance_history.append(variance)
        
        # If variance exceeds threshold, movement detected
        is_detected = variance > self.threshold
        
        return is_detected, variance
    
    def detect(self, csi_sample=None):
        """
        Single detection cycle
        
        Args:
            csi_sample: CSI matrix (30x30 complex array), or None for mock data
        """
        # Use provided CSI or generate mock data
        if csi_sample is None:
            # Simulate with 30% chance of movement
            has_movement = np.random.random() < 0.3
            csi_sample = self.generate_mock_csi(has_movement)
        
        self.csi_history.append(csi_sample)
        
        is_detected, variance = self.analyze_csi_variance()
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] CSI Variance: {variance:.6f} | ", end="")
        
        if is_detected:
            print(f"🟢 HUMAN DETECTED (Movement signature found)")
            return True
        else:
            print(f"No movement detected")
            return False


class WifiSensingML:
    """
    Machine learning approach for WiFi-based sensing
    Uses historical data to train and predict human presence
    """
    
    def __init__(self):
        self.training_data = []
        self.labels = []  # 0: no human, 1: human present
        
    def extract_features(self, rssi_values):
        """Extract features from RSSI measurements"""
        features = {
            'mean': np.mean(rssi_values),
            'std': np.std(rssi_values),
            'min': np.min(rssi_values),
            'max': np.max(rssi_values),
            'range': np.max(rssi_values) - np.min(rssi_values),
            'variance': np.var(rssi_values),
        }
        return features
    
    def simple_classifier(self, rssi_values):
        """
        Simple classifier based on signal characteristics
        More sophisticated approaches would use ML models
        """
        if len(rssi_values) < 3:
            return None
        
        features = self.extract_features(rssi_values)
        
        # Simple heuristics
        score = 0
        
        # High variance suggests movement
        if features['variance'] > 10:
            score += 1
        
        # Large range indicates signal fluctuations from movement
        if features['range'] > 15:
            score += 1
        
        # Sudden changes in mean
        if len(self.training_data) > 0:
            prev_mean = self.training_data[-1]['mean']
            if abs(features['mean'] - prev_mean) > 5:
                score += 1
        
        self.training_data.append(features)
        
        # If 2+ signals detected, human likely present
        return score >= 2


# Example demonstration
if __name__ == "__main__":
    print("\n" + "="*70)
    print("Advanced WiFi CSI Human Detection Demo")
    print("="*70 + "\n")
    
    # CSI Detector Demo
    print("CSI-Based Detection Test (Mock Data):")
    print("-" * 70)
    csi_detector = WiFiCSIDetector(window_size=20, threshold=0.15)
    
    for i in range(15):
        csi_detector.detect()
        if (i + 1) % 5 == 0:
            print()
    
    # ML Classifier Demo
    print("\nML-Based Classification Test:")
    print("-" * 70)
    ml_detector = WifiSensingML()
    
    # Simulate RSSI readings
    rssi_readings = [
        [-70, -71, -72, -71, -70],  # Stable - no human
        [-70, -65, -75, -68, -72],  # Fluctuating - human present
        [-68, -69, -70, -69, -68],  # Stable - no human
    ]
    
    for idx, readings in enumerate(rssi_readings):
        result = ml_detector.simple_classifier(readings)
        status = "HUMAN DETECTED" if result else "No human detected"
        print(f"Reading set {idx+1}: {readings} -> {status}")
