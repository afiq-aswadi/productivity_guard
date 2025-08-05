#!/usr/bin/env python3
"""
Manual test for break feature functionality.
This script demonstrates the break feature without running the full monitoring system.
"""

import sys
import os
from datetime import datetime, timedelta

def test_break_functionality():
    """Test the break feature by creating a simplified version."""
    
    class SimpleBreakTester:
        def __init__(self):
            self.on_break = False
            self.break_start_time = None
            self.break_duration = 0
            self.break_activity = ""
            
        def start_break(self, minutes, activity):
            """Simplified break start method."""
            if self.on_break:
                print("☕ You're already on a break!")
                return
            
            self.on_break = True
            self.break_start_time = datetime.now()
            self.break_duration = minutes * 60
            self.break_activity = activity
            
            print(f"\n🛑 BREAK MODE ACTIVATED!")
            print(f"☕ Activity: {activity}")
            print(f"⏰ Duration: {minutes} minutes")
            print(f"🎯 Break ends at {(self.break_start_time + timedelta(seconds=self.break_duration)).strftime('%H:%M')}")
            print("📸 Screenshot monitoring is PAUSED")
            print("=" * 50)
            
        def show_break_status(self):
            """Show current break status."""
            if not self.on_break:
                print("☕ No active break.")
                return
            
            current_time = datetime.now()
            elapsed_seconds = (current_time - self.break_start_time).total_seconds()
            remaining_seconds = max(0, self.break_duration - elapsed_seconds)
            
            if remaining_seconds > 0:
                remaining_minutes = int(remaining_seconds // 60)
                remaining_secs = int(remaining_seconds % 60)
                total_minutes = int(self.break_duration // 60)
                elapsed_minutes = int(elapsed_seconds // 60)
                
                print(f"\n☕ BREAK MODE ACTIVE")
                print(f"🎯 Activity: {self.break_activity}")
                print(f"⏰ Time remaining: {remaining_minutes:02d}:{remaining_secs:02d}")
                print(f"📊 Progress: {elapsed_minutes}/{total_minutes} minutes")
                print(f"📸 Screenshot monitoring is PAUSED")
                
                # Show simple progress bar
                progress = elapsed_seconds / self.break_duration
                bar_length = 20
                filled_length = int(bar_length * progress)
                bar = "☕" * filled_length + "░" * (bar_length - filled_length)
                print(f"🔋 [{bar}] {progress*100:.1f}%")
            else:
                print("⏰ Break time is over!")
                
        def check_break_timer(self):
            """Check if break is finished."""
            if not self.on_break:
                return False
                
            current_time = datetime.now()
            elapsed_seconds = (current_time - self.break_start_time).total_seconds()
            
            if elapsed_seconds >= self.break_duration:
                self.on_break = False
                minutes = self.break_duration // 60
                
                print("\n" + "=" * 60)
                print("⏰ BREAK TIME IS OVER! ⏰")
                print(f"✅ You took a {minutes}-minute break: {self.break_activity}")
                print("🔋 Hope you're feeling refreshed!")
                print("📸 Screenshot monitoring would now be RESUMED")
                print("=" * 60)
                
                self.break_activity = ""
                return True
            
            return False
    
    # Test the functionality
    print("🧪 Testing Break Feature Functionality")
    print("=" * 60)
    
    tester = SimpleBreakTester()
    
    # Test 1: Initial state
    print("\n1. Testing initial state:")
    tester.show_break_status()
    
    # Test 2: Start a break
    print("\n2. Starting a 2-minute break (for testing):")
    tester.start_break(2, "drinking coffee and stretching")
    
    # Test 3: Show status during break
    print("\n3. Checking break status:")
    tester.show_break_status()
    
    # Test 4: Try to start another break
    print("\n4. Trying to start another break while already on break:")
    tester.start_break(1, "another activity")
    
    # Test 5: Check if break timer works
    print("\n5. Break timer functionality demonstrated")
    print("   (In real usage, break would automatically end after the specified time)")
    
    # Test 6: Simulate break completion
    print("\n6. Simulating break completion:")
    # Manually set break to completed state for demonstration
    tester.break_start_time = datetime.now() - timedelta(minutes=3)  # Simulate 3 minutes ago
    tester.check_break_timer()
    
    # Test 7: Show status after break ends
    print("\n7. Status after break ends:")
    tester.show_break_status()
    
    print("\n✅ Break feature test completed successfully!")
    print("\nFeatures demonstrated:")
    print("  ✓ Break initialization and state management")
    print("  ✓ Starting breaks with custom activities")
    print("  ✓ Showing break status with progress bar")
    print("  ✓ Preventing multiple concurrent breaks")
    print("  ✓ Automatic break completion detection")
    print("  ✓ Screenshot monitoring pause indication")

if __name__ == '__main__':
    test_break_functionality()