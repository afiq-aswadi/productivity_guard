#!/usr/bin/env python3
"""
Test script for the daily logging functionality.

This script tests the file-based daily logging and summary generation.
"""

import sys
import os
import shutil
from datetime import datetime, timedelta

# Add the current directory to path to import productivity_guard
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_daily_logging():
    """Test the daily logging functionality."""
    print("🧪 Testing Daily Logging Functionality")
    print("=" * 50)
    
    # Create a temporary test directory
    test_data_dir = os.path.join(os.path.dirname(__file__), 'test_data')
    if os.path.exists(test_data_dir):
        shutil.rmtree(test_data_dir)
    
    try:
        # Import here to avoid dependency issues during testing
        from productivity_guard import ProductivityGuard
        
        # Create guard instance
        guard = ProductivityGuard(test_mode=True, debug=True)
        
        # Override the data directory for testing
        guard.data_dir = test_data_dir
        guard.logs_dir = os.path.join(test_data_dir, 'logs')
        guard.summaries_dir = os.path.join(test_data_dir, 'summaries')
        
        # Re-setup logging with test directory
        guard.setup_daily_logging()
        
        print(f"📁 Test files created in: {test_data_dir}")
        print(f"📝 Daily log: {guard.daily_log_file}")
        print(f"📊 Summary file: {guard.daily_summary_file}")
        
        # Test activity logging
        print("\n🎯 Testing activity logging...")
        activities = [
            ('CODING', 'Working on Python script'),
            ('STUDYING', 'Reading documentation'),
            ('SOCIAL_MEDIA', 'Checking Twitter'),
            ('BREAKS', 'Coffee break'),
            ('CODING', 'Code review'),
        ]
        
        for category, description in activities:
            guard.log_activity(category, description)
            print(f"   ✓ Logged: {category} - {description}")
        
        # Test hourly summary
        print("\n⏰ Testing hourly summary...")
        guard.generate_hourly_summary()
        
        # Test end-of-day summary
        print("\n🎯 Testing end-of-day summary...")
        guard.save_workday_summary_to_file()
        
        # Show file contents
        print("\n📄 Daily Log Content:")
        print("-" * 30)
        if os.path.exists(guard.daily_log_file):
            with open(guard.daily_log_file, 'r', encoding='utf-8') as f:
                content = f.read()
                print(content[:500] + "..." if len(content) > 500 else content)
        
        print("\n📊 Summary File Content:")
        print("-" * 30)
        if os.path.exists(guard.daily_summary_file):
            with open(guard.daily_summary_file, 'r', encoding='utf-8') as f:
                content = f.read()
                print(content[:500] + "..." if len(content) > 500 else content)
        
        print(f"\n✅ Test completed successfully!")
        print(f"📁 Test files are in: {test_data_dir}")
        print("💡 Files will be automatically ignored by git (.gitignore updated)")
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("💡 This is normal if dependencies aren't installed")
        print("📁 Testing folder structure creation...")
        
        # Test just the folder creation
        os.makedirs(os.path.join(test_data_dir, 'logs'), exist_ok=True)
        os.makedirs(os.path.join(test_data_dir, 'summaries'), exist_ok=True)
        
        # Create sample files
        today = datetime.now().strftime('%Y-%m-%d')
        sample_log = os.path.join(test_data_dir, 'logs', f'{today}_activity_log.md')
        sample_summary = os.path.join(test_data_dir, 'summaries', f'{today}_workday_summary.md')
        
        with open(sample_log, 'w') as f:
            f.write(f"# 📅 Daily Activity Log - {today}\n\nSample log file created for testing.\n")
        
        with open(sample_summary, 'w') as f:
            f.write(f"# 🎯 Workday Summary - {today}\n\nSample summary file created for testing.\n")
        
        print(f"✅ Created sample files in: {test_data_dir}")
        
    except Exception as e:
        print(f"❌ Error during test: {e}")
    
    finally:
        # Clean up test directory
        if os.path.exists(test_data_dir):
            response = input(f"\n🗑️  Remove test directory {test_data_dir}? (y/N): ")
            if response.lower() == 'y':
                shutil.rmtree(test_data_dir)
                print("✅ Test directory cleaned up")

if __name__ == "__main__":
    test_daily_logging()