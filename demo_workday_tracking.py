#!/usr/bin/env python3
"""
Quick demo of the new workday tracking features.

This script shows a simple demonstration of the workday tracking functionality
without requiring API keys or actual screenshots.
"""

from productivity_guard import ProductivityGuard
from datetime import datetime, timedelta
import time

def demo_workday_tracking():
    """Demonstrate the workday tracking features."""
    print("🎯 ProductivityGuard Workday Tracking Demo")
    print("=" * 50)
    
    # Create a ProductivityGuard instance in test mode
    guard = ProductivityGuard(test_mode=True, debug=True)
    
    print(f"📅 Workday started: {guard.workday_start_time.strftime('%Y-%m-%d %H:%M')}")
    print("\n🧪 Simulating activities throughout the workday...")
    
    # Simulate some activities
    activities = [
        ('CODING', 'Working on Python script'),
        ('CODING', 'Debugging application'),
        ('SOCIAL_MEDIA', 'Checking Twitter'),
        ('CODING', 'Writing unit tests'),
        ('BREAKS', 'Coffee break'),
        ('STUDYING', 'Reading documentation'),
        ('ENTERTAINMENT', 'Watching YouTube'),
        ('CODING', 'Code review'),
        ('MEETINGS', 'Team standup'),
    ]
    
    print("\n📊 Activity Log:")
    for i, (category, description) in enumerate(activities):
        # Simulate some time passing
        guard.current_activity_start = datetime.now() - timedelta(minutes=5)
        guard.log_activity(category, description)
        print(f"   {i+1}. {category.title()}: {description}")
        time.sleep(0.5)  # Small delay for demo effect
    
    print("\n⏰ Generating hourly summary...")
    guard.generate_hourly_summary()
    
    print("\n🎯 Generating end-of-workday summary...")
    guard.workday_active = True  # Ensure it's active for the summary
    guard._generate_basic_summary({
        'CODING': {'hours': 2, 'minutes': 30, 'total_minutes': 150, 'percentage': 45.5},
        'STUDYING': {'hours': 1, 'minutes': 0, 'total_minutes': 60, 'percentage': 18.2},
        'SOCIAL_MEDIA': {'hours': 0, 'minutes': 30, 'total_minutes': 30, 'percentage': 9.1},
        'ENTERTAINMENT': {'hours': 0, 'minutes': 20, 'total_minutes': 20, 'percentage': 6.1},
        'MEETINGS': {'hours': 0, 'minutes': 45, 'total_minutes': 45, 'percentage': 13.6},
        'BREAKS': {'hours': 0, 'minutes': 25, 'total_minutes': 25, 'percentage': 7.6}
    }, timedelta(hours=5, minutes=30))
    
    print("\n✅ Demo completed!")
    print("\n💡 To run the full workday tracking with real screenshots:")
    print("   python productivity_guard.py")
    print("\n🧪 To test with simulated activities:")
    print("   python productivity_guard.py --test")

if __name__ == "__main__":
    demo_workday_tracking()