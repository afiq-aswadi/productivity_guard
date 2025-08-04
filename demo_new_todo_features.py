#!/usr/bin/env python3
"""
Demonstration of the new todo management features in ProductivityGuard.

This script shows how the new features work:
1. Next session todo collection when ending workday
2. Previous day todo import when starting new day
"""

import os
import json
from datetime import datetime, timedelta
from productivity_guard import ProductivityGuard

def demo_new_todo_features():
    """Demonstrate the new todo management functionality."""
    print("🚀 ProductivityGuard - New Todo Management Features Demo")
    print("=" * 70)
    
    print("\n🎯 NEW TODO MANAGEMENT FEATURES:")
    
    print("\n1. 📝 NEXT SESSION TODO COLLECTION")
    print("   • When ending workday with 'end' command")
    print("   • Ask user for todos for next session")
    print("   • Store in next_session_todos.json")
    print("   • Load automatically when starting again")
    print("   • Works for same day or future sessions")
    
    print("\n2. 📅 PREVIOUS DAY TODO IMPORT")
    print("   • When starting a new day (no existing todos)")
    print("   • Check for undone todos from yesterday")
    print("   • Offer to import them for today")
    print("   • Mark imported todos with metadata")
    
    print("\n" + "=" * 70)
    print("🔧 HOW THE NEW FEATURES WORK:")
    
    print("\n📤 ENDING WORKDAY:")
    print("   1. Run 'end' command to end workday")
    print("   2. System generates workday summary")
    print("   3. Prompts: 'Add todos for next session?'")
    print("   4. Enter todos one by one (or skip)")
    print("   5. Saves to data/next_session_todos.json")
    print("   6. File removed after loading in next session")
    
    print("\n📥 STARTING NEW SESSION:")
    print("   Same Day:")
    print("   • Loads existing daily todos")
    print("   • Loads next_session_todos.json if exists")
    print("   • Integrates both seamlessly")
    
    print("\n   New Day:")
    print("   • Checks for undone todos from yesterday") 
    print("   • Asks: 'Import yesterday's undone todos?'")
    print("   • Loads next_session_todos.json if exists")
    print("   • Prompts for additional todos")
    print("   • All todos saved to today's file")
    
    print("\n" + "=" * 70)
    print("📁 FILE STRUCTURE:")
    
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
    today = datetime.now().strftime('%Y-%m-%d')
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    print(f"\n   data/")
    print(f"   ├── {today}_daily_todos.json       # Today's todos")
    print(f"   ├── {yesterday}_daily_todos.json   # Yesterday's todos")
    print(f"   ├── next_session_todos.json        # Pending next session todos")
    print(f"   ├── logs/")
    print(f"   └── summaries/")
    
    print("\n" + "=" * 70)
    print("💡 USAGE SCENARIOS:")
    
    print("\n🔄 Scenario 1: Multiple sessions same day")
    print("   • Morning: Start ProductivityGuard, add todos")
    print("   • Lunch: End with 'end', add afternoon todos")
    print("   • Afternoon: Restart, gets morning + afternoon todos")
    
    print("\n📅 Scenario 2: New day workflow")
    print("   • Previous day had: 'Code feature', 'Review PR', 'Write docs'")
    print("   • Only completed: 'Code feature'")
    print("   • New day: Offers to import 'Review PR', 'Write docs'")
    print("   • Add new todos on top of imported ones")
    
    print("\n🎯 Scenario 3: End-of-day planning")
    print("   • End workday: 'Think of tomorrow's tasks?'")
    print("   • Add: 'Fix bug #123', 'Prepare presentation'")
    print("   • Next day: Auto-loads those tasks")
    
    print("\n" + "=" * 70)
    print("📋 EXAMPLE TODO METADATA:")
    
    example_todos = {
        "regular_todo": {
            "id": 1,
            "text": "Implement new feature",
            "completed": False,
            "created_at": "2025-01-08T09:00:00.000000"
        },
        "next_session_todo": {
            "id": 2,
            "text": "Review code changes", 
            "completed": False,
            "created_at": "2025-01-08T14:30:00.000000",
            "from_previous_session": True
        },
        "imported_todo": {
            "id": 3,
            "text": "Update documentation",
            "completed": False,
            "created_at": "2025-01-08T09:00:00.000000",
            "imported_from_previous_day": True,
            "original_date": "2025-01-07T10:15:00.000000"
        }
    }
    
    print("\n   Regular Todo:")
    print(f"   {json.dumps(example_todos['regular_todo'], indent=4)}")
    
    print("\n   Next Session Todo:")
    print(f"   {json.dumps(example_todos['next_session_todo'], indent=4)}")
    
    print("\n   Imported from Previous Day:")
    print(f"   {json.dumps(example_todos['imported_todo'], indent=4)}")
    
    print("\n" + "=" * 70)
    print("🚦 COMMANDS:")
    print("   • 'end' / 'end workday' - Trigger next session todo collection")
    print("   • 'todos' / 'list' - Show current todos (with metadata)")
    print("   • 'done [id]' - Complete todo")
    print("   • 'add [text]' - Add new todo")
    
    print("\n" + "=" * 70)
    print("✅ Features implemented and ready for testing!")
    print("\nTo test:")
    print("1. Run ProductivityGuard normally")
    print("2. Add some todos, complete some")
    print("3. Use 'end' command and add next session todos")
    print("4. Restart and see todos loaded automatically")
    print("5. Try on a new day to see previous day import")

if __name__ == "__main__":
    demo_new_todo_features()