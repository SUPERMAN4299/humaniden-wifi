"""
WiFi Human Detection - Complete Integrated Example
Real-world implementation with logging, alerts, and web interface
"""

import json
import time
from datetime import datetime
from collections import deque
from wifi_human_detector import WiFiHumanDetector
from wifi_detection_utils import EnvironmentCalibration, SignalProcessor, ReportGenerator


class SmartOccupancySystem:
    """
    Complete occupancy detection system for smart home/buildings
    Includes:
    - Multi-room monitoring
    - Event logging
    - Alert system
    - Historical data
    - Web API (optional)
    """
    
    def __init__(self, config_file="occupancy_config.json"):
        self.rooms = {}
        self.events = deque(maxlen=1000)  # Keep last 1000 events
        self.report_generator = ReportGenerator()
        self.running = False
        self.config_file = config_file
        self.load_config()
        
    def add_room(self, room_name, ssid=None, threshold=5):
        """Add a room to monitor"""
        detector = WiFiHumanDetector(ssid=ssid, threshold=threshold)
        self.rooms[room_name] = {
            'detector': detector,
            'occupied': False,
            'last_detection': None,
            'detection_count': 0,
            'ssid': ssid
        }
        print(f"✓ Added room: {room_name}")
    
    def calibrate_room(self, room_name, samples=30):
        """Calibrate a specific room"""
        if room_name not in self.rooms:
            print(f"❌ Room not found: {room_name}")
            return
        
        print(f"\n📊 Calibrating {room_name}...")
        detector = self.rooms[room_name]['detector']
        calibrator = EnvironmentCalibration(detector, num_samples=samples)
        baseline = calibrator.run_calibration()
        
        if baseline:
            self.rooms[room_name]['baseline'] = baseline
            return baseline
        return None
    
    def update_room(self, room_name):
        """Update detection status for a room"""
        if room_name not in self.rooms:
            return False
        
        room = self.rooms[room_name]
        room['detector'].detect()
        
        was_occupied = room['occupied']
        is_now_occupied = room['detector'].human_detected
        
        if is_now_occupied:
            room['detection_count'] += 1
        
        # Occupancy state changed
        if is_now_occupied and not was_occupied:
            room['occupied'] = True
            room['last_detection'] = datetime.now()
            self._log_event(f"OCCUPIED", room_name)
            self._alert(room_name, "now occupied")
            return True
            
        elif not is_now_occupied and was_occupied:
            room['occupied'] = False
            self._log_event(f"UNOCCUPIED", room_name)
            self._alert(room_name, "is now empty")
            return False
        
        return is_now_occupied
    
    def _log_event(self, event_type, room_name):
        """Log an event"""
        event = {
            'timestamp': datetime.now().isoformat(),
            'event': event_type,
            'room': room_name
        }
        self.events.append(event)
        self.report_generator.log_detection(
            event['timestamp'],
            room_name,
            1.0,  # confidence
            -70   # sample signal strength
        )
    
    def _alert(self, room_name, status):
        """Generate alerts"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] 🔔 ALERT: {room_name.upper()} - {status}")
    
    def monitor_all(self, interval=2):
        """Monitor all rooms"""
        print(f"\n{'='*70}")
        print(f"Smart Occupancy System Started")
        print(f"Monitoring {len(self.rooms)} rooms every {interval} seconds")
        print(f"{'='*70}\n")
        
        self.running = True
        iteration = 0
        
        try:
            while self.running:
                iteration += 1
                timestamp = datetime.now().strftime("%H:%M:%S")
                print(f"\n[{timestamp}] Iteration {iteration}:")
                print("-" * 70)
                
                for room_name in self.rooms:
                    self.update_room(room_name)
                
                self.print_status()
                time.sleep(interval)
                
        except KeyboardInterrupt:
            print("\n\n✓ Monitoring stopped")
            self.save_report()
    
    def print_status(self):
        """Print current status of all rooms"""
        print("\nCurrent Status:")
        for room_name, room_data in self.rooms.items():
            status = "🟢 OCCUPIED" if room_data['occupied'] else "⚪ EMPTY"
            detections = room_data['detection_count']
            print(f"  {room_name:20} {status:15} (Detections: {detections})")
    
    def get_status(self):
        """Get system status as dict"""
        status = {}
        for room_name, room_data in self.rooms.items():
            status[room_name] = {
                'occupied': room_data['occupied'],
                'detections': room_data['detection_count'],
                'last_detection': room_data['last_detection'].isoformat() if room_data['last_detection'] else None
            }
        return status
    
    def save_report(self):
        """Save detailed report"""
        filename = f"occupancy_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        report_data = {
            'timestamp': datetime.now().isoformat(),
            'rooms': self.get_status(),
            'events': list(self.events),
            'summary': {
                'total_events': len(self.events),
                'rooms_monitored': len(self.rooms)
            }
        }
        
        with open(filename, 'w') as f:
            json.dump(report_data, f, indent=2)
        
        print(f"\n📄 Report saved: {filename}")
    
    def save_config(self):
        """Save configuration"""
        config = {
            'rooms': {}
        }
        
        for room_name, room_data in self.rooms.items():
            config['rooms'][room_name] = {
                'ssid': room_data['ssid'],
                'threshold': room_data['detector'].threshold
            }
        
        with open(self.config_file, 'w') as f:
            json.dump(config, f, indent=2)
    
    def load_config(self):
        """Load configuration from file"""
        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
                for room_name, room_config in config.get('rooms', {}).items():
                    self.add_room(
                        room_name,
                        ssid=room_config.get('ssid'),
                        threshold=room_config.get('threshold', 5)
                    )
        except FileNotFoundError:
            print(f"⚠ Config file not found: {self.config_file}")


class AdvancedAnalytics:
    """Advanced analytics for occupancy patterns"""
    
    @staticmethod
    def analyze_occupancy_pattern(events):
        """Analyze occupancy patterns from events"""
        if not events:
            return None
        
        occupied_times = []
        current_start = None
        
        for event in events:
            if event['event'] == 'OCCUPIED':
                current_start = datetime.fromisoformat(event['timestamp'])
            elif event['event'] == 'UNOCCUPIED' and current_start:
                duration = datetime.fromisoformat(event['timestamp']) - current_start
                occupied_times.append(duration.total_seconds())
        
        if not occupied_times:
            return None
        
        return {
            'avg_occupancy_duration': sum(occupied_times) / len(occupied_times),
            'max_occupancy_duration': max(occupied_times),
            'min_occupancy_duration': min(occupied_times),
            'total_occupied_sessions': len(occupied_times)
        }
    
    @staticmethod
    def predict_next_occupancy(events, room_name):
        """Predict when room will next be occupied"""
        # Simple heuristic: if occupied at this time yesterday, likely to be occupied tomorrow
        # In real system, use ML
        
        today_events = [e for e in events if room_name in e.get('room', '')]
        
        if today_events:
            return f"Based on pattern, room likely occupied around {today_events[0]['timestamp']}"
        
        return "Insufficient data for prediction"


# ============================================================================
# EXAMPLE 1: Simple Home Automation System
# ============================================================================

def example_home_automation():
    """
    Home automation system that controls lights based on occupancy
    """
    print("\n" + "="*70)
    print("EXAMPLE 1: Home Automation System")
    print("="*70 + "\n")
    
    system = SmartOccupancySystem()
    
    # Add rooms
    system.add_room("Living Room", threshold=5)
    system.add_room("Bedroom", threshold=4)
    system.add_room("Kitchen", threshold=6)
    
    # Quick simulation
    print("Running quick simulation...\n")
    
    # Simulate occupancy changes
    scenarios = [
        ("Living Room", True, "Person enters"),
        ("Bedroom", False, "No one in bedroom"),
        ("Kitchen", True, "Someone cooking"),
    ]
    
    for room, occupied, description in scenarios:
        print(f"{description}")
        system.rooms[room]['detector'].human_detected = occupied
        system.update_room(room)
        time.sleep(0.5)
    
    system.print_status()
    system.save_report()


# ============================================================================
# EXAMPLE 2: Security Monitoring System
# ============================================================================

def example_security_system():
    """
    Security system that alerts on unauthorized occupancy
    """
    print("\n" + "="*70)
    print("EXAMPLE 2: Security Monitoring System")
    print("="*70 + "\n")
    
    system = SmartOccupancySystem()
    
    # Add secure areas
    system.add_room("Front Door", threshold=3)
    system.add_room("Bedroom", threshold=4)
    system.add_room("Garage", threshold=5)
    
    print("Security system armed for night mode")
    print("Alert threshold: Any occupancy detected\n")
    
    # Simulate intrusion detection
    print("Simulating night monitoring...")
    
    # Normal - no activity
    print("\n[22:00] System armed. All rooms clear.")
    for room in system.rooms:
        system.rooms[room]['detector'].human_detected = False
    
    # Alert - movement detected
    time.sleep(1)
    print("[22:15] Movement detected in bedroom!")
    system.rooms["Bedroom"]['detector'].human_detected = True
    system.update_room("Bedroom")
    
    time.sleep(1)
    print("[22:20] Movement detected at front door!")
    system.rooms["Front Door"]['detector'].human_detected = True
    system.update_room("Front Door")
    
    system.print_status()


# ============================================================================
# EXAMPLE 3: Office Space Management
# ============================================================================

def example_office_management():
    """
    Office system tracking employee presence for hot-desking
    """
    print("\n" + "="*70)
    print("EXAMPLE 3: Office Space Management System")
    print("="*70 + "\n")
    
    system = SmartOccupancySystem()
    
    # Add office spaces
    offices = ["Desk Area 1", "Desk Area 2", "Conference Room", "Server Room"]
    for office in offices:
        system.add_room(office, threshold=5)
    
    print("Office occupancy system active\n")
    print("Tracking workspace usage for hot-desking allocation...\n")
    
    # Simulate office hours
    scenarios = [
        ("Desk Area 1", True),
        ("Desk Area 2", True),
        ("Conference Room", True),
        ("Server Room", False),
    ]
    
    for room, occupied in scenarios:
        system.rooms[room]['detector'].human_detected = occupied
        system.update_room(room)
        time.sleep(0.3)
    
    system.print_status()
    
    # Analytics
    print("\n📊 Office Analytics:")
    print(f"Occupied spaces: {sum(1 for r in system.rooms.values() if r['occupied'])}/{len(system.rooms)}")
    print(f"Utilization rate: {sum(1 for r in system.rooms.values() if r['occupied'])/len(system.rooms)*100:.1f}%")


# ============================================================================
# MAIN: Run Examples
# ============================================================================

if __name__ == "__main__":
    import sys
    
    print("\n" + "="*70)
    print("WiFi Human Detection - Complete Integrated Examples")
    print("="*70)
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "1":
            example_home_automation()
        elif sys.argv[1] == "2":
            example_security_system()
        elif sys.argv[1] == "3":
            example_office_management()
    else:
        # Run all examples
        example_home_automation()
        example_security_system()
        example_office_management()
    
    print("\n" + "="*70)
    print("Examples completed!")
    print("="*70 + "\n")
