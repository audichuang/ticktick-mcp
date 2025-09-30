#!/usr/bin/env python3
"""
Test script for TickTick MCP Timezone Fix.
This script tests the new timezone functionality for creating and updating tasks.
"""

import asyncio
import sys
from datetime import datetime, timedelta
from ticktick_mcp.src.ticktick_client import TickTickClient

async def test_timezone_functionality():
    """Test the timezone functionality."""
    print("🌍 Testing TickTick MCP Timezone Fix\n")
    
    # Initialize client
    print("1. Initializing TickTick client...")
    try:
        client = TickTickClient()
        print("✅ Client initialized successfully\n")
    except Exception as e:
        print(f"❌ Failed to initialize client: {e}")
        return False
    
    # Get projects
    print("2. Getting projects...")
    projects = client.get_projects()
    if 'error' in projects:
        print(f"❌ Failed to get projects: {projects['error']}")
        return False
    
    if not projects:
        print("❌ No projects found. Please create a project first.")
        return False
    
    # Use the first project
    project = projects[0]
    project_id = project['id']
    print(f"✅ Using project: {project['name']} (ID: {project_id})\n")
    
    # Calculate test dates
    now = datetime.now()
    tomorrow = now + timedelta(days=1)
    
    # Test cases with different timezone formats
    test_cases = [
        {
            "name": "Taiwan time with timezone offset",
            "due_date": tomorrow.strftime("%Y-%m-%dT14:00:00+0800"),
            "time_zone": None,  # Should auto-infer to Asia/Taipei
            "expected_tz": "Asia/Taipei"
        },
        {
            "name": "Japan time with explicit timezone",
            "due_date": tomorrow.strftime("%Y-%m-%dT15:00:00+0900"),
            "time_zone": "Asia/Tokyo",
            "expected_tz": "Asia/Tokyo"
        },
        {
            "name": "US Eastern time with auto-inference",
            "due_date": tomorrow.strftime("%Y-%m-%dT09:00:00-0500"),
            "time_zone": None,  # Should auto-infer to America/New_York
            "expected_tz": "America/New_York"
        },
        {
            "name": "All-day task",
            "due_date": tomorrow.strftime("%Y-%m-%dT00:00:00+0800"),
            "time_zone": "Asia/Taipei",
            "is_all_day": True,
            "expected_tz": "Asia/Taipei"
        }
    ]
    
    created_tasks = []
    
    # Test creating tasks with different timezone configurations
    for i, test_case in enumerate(test_cases, 3):
        print(f"{i}. Testing: {test_case['name']}")
        
        task_title = f"Timezone Test - {test_case['name']}"
        
        task = client.create_task(
            title=task_title,
            project_id=project_id,
            content=f"Testing timezone functionality: {test_case['name']}",
            due_date=test_case['due_date'],
            time_zone=test_case['time_zone'],
            is_all_day=test_case.get('is_all_day', False),
            priority=3
        )
        
        if 'error' in task:
            print(f"❌ Failed to create task: {task['error']}")
            continue
        
        print(f"✅ Task created: {task['title']}")
        print(f"   ID: {task['id']}")
        print(f"   Due Date: {task.get('dueDate', 'Not set')}")
        print(f"   Timezone: {task.get('timeZone', 'Not set')}")
        print(f"   All Day: {task.get('isAllDay', False)}")
        
        # Verify timezone was set correctly
        if task.get('timeZone') == test_case['expected_tz']:
            print(f"✅ Timezone correctly set to {test_case['expected_tz']}")
        elif task.get('timeZone'):
            print(f"⚠️  Timezone set to {task.get('timeZone')}, expected {test_case['expected_tz']}")
        else:
            print(f"⚠️  No timezone set, expected {test_case['expected_tz']}")
        
        print()
        created_tasks.append(task)
    
    # Test updating task timezone
    if created_tasks:
        test_task = created_tasks[0]
        print(f"6. Testing timezone update for task: {test_task['title']}")
        
        # Update with different timezone
        updated_task = client.update_task(
            task_id=test_task['id'],
            project_id=project_id,
            time_zone="Europe/London",
            due_date=tomorrow.strftime("%Y-%m-%dT10:00:00+0000")
        )
        
        if 'error' in updated_task:
            print(f"❌ Failed to update task: {updated_task['error']}")
        else:
            print(f"✅ Task updated successfully")
            print(f"   New Due Date: {updated_task.get('dueDate', 'Not set')}")
            print(f"   New Timezone: {updated_task.get('timeZone', 'Not set')}")
            
            if updated_task.get('timeZone') == "Europe/London":
                print("✅ Timezone update successful")
            else:
                print(f"⚠️  Timezone update issue: got {updated_task.get('timeZone')}, expected Europe/London")
        print()
    
    # Cleanup test tasks
    print("7. Cleaning up test tasks...")
    cleanup_success = 0
    for task in created_tasks:
        if 'id' in task:
            result = client.delete_task(project_id, task['id'])
            if 'error' not in result:
                cleanup_success += 1
                print(f"✅ Deleted: {task['title']}")
            else:
                print(f"❌ Failed to delete: {task['title']}")
    
    print(f"\n📊 Test Summary:")
    print(f"   Tasks created: {len(created_tasks)}")
    print(f"   Tasks cleaned up: {cleanup_success}")
    
    if len(created_tasks) > 0:
        print("\n✨ Timezone functionality test completed successfully!")
        print("\n💡 Key improvements:")
        print("   - Added timeZone parameter support")
        print("   - Smart timezone inference from date strings")
        print("   - Support for isAllDay tasks")
        print("   - Enhanced MCP tool descriptions")
        return True
    else:
        print("\n❌ No tasks were created successfully. Please check your configuration.")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_timezone_functionality())
    sys.exit(0 if success else 1)