#!/usr/bin/env python3
"""
Test script for the workday tracking feature of ProductivityGuard.

This script demonstrates how to use the new workday tracking functionality
in test mode to simulate a full workday.
"""

import subprocess
import time
import os
import sys

def test_workday_tracking():
    """Test the workday tracking feature in simulation mode."""
    print("🧪 Testing ProductivityGuard Workday Tracking Feature")
    print("=" * 50)
    
    print("\n📋 This test will:")
    print("1. Start ProductivityGuard in test mode")
    print("2. Simulate various activities throughout a workday")
    print("3. Show hourly summaries")
    print("4. Generate an end-of-workday summary")
    
    print("\n💡 Available commands during test:")
    print("- Type 'summary' to get current progress")
    print("- Type 'end' to finish the workday")
    print("- Press Ctrl+C to stop")
    
    print("\n🚀 Starting test mode...")
    print("Note: Activities will be simulated every 10 seconds")
    
    try:
        # Run ProductivityGuard in test mode
        cmd = [sys.executable, "productivity_guard.py", "--test", "--interval", "10"]
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\n\n✅ Test completed successfully!")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Test failed with error: {e}")
    except FileNotFoundError:
        print("\n❌ ProductivityGuard script not found. Make sure you're in the correct directory.")

if __name__ == "__main__":
    test_workday_tracking()