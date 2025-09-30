#!/usr/bin/env python3
"""
Debug script for timezone inference.
"""

import re
from typing import Optional

# Same mapping as in server.py
TIMEZONE_OFFSET_MAP = {
    "+0800": "Asia/Taipei",      # Taiwan, China, Singapore
    "+0900": "Asia/Tokyo",       # Japan, Korea  
    "+0000": "UTC",              # UTC
    "-0500": "America/New_York", # US Eastern (EST)
    "-0400": "America/New_York", # US Eastern (EDT)
    "-0800": "America/Los_Angeles", # US Pacific (PST)
    "-0700": "America/Los_Angeles", # US Pacific (PDT)
    "+0100": "Europe/London",    # UK (BST)
}

def infer_timezone_from_date(date_string: str) -> Optional[str]:
    """
    Extract timezone from ISO date string and map to timezone name.
    """
    if not date_string:
        return None
    
    print(f"Processing date string: {date_string}")
    
    # Extract timezone offset using regex
    timezone_pattern = r'([+-]\d{4})$'
    match = re.search(timezone_pattern, date_string)
    
    if match:
        offset = match.group(1)
        print(f"Found offset: {offset}")
        result = TIMEZONE_OFFSET_MAP.get(offset)
        print(f"Mapped to timezone: {result}")
        return result
    else:
        print("No timezone offset found")
    
    return None

def get_smart_timezone(time_zone: str, start_date: str, due_date: str) -> Optional[str]:
    """
    Get the best timezone for the task using smart inference.
    """
    print(f"\nget_smart_timezone called with:")
    print(f"  time_zone: {time_zone}")
    print(f"  start_date: {start_date}")
    print(f"  due_date: {due_date}")
    
    # If explicitly provided, use that
    if time_zone:
        print(f"Using explicit timezone: {time_zone}")
        return time_zone
    
    # Try to infer from start_date
    if start_date:
        print("Trying to infer from start_date...")
        inferred = infer_timezone_from_date(start_date)
        if inferred:
            print(f"Inferred from start_date: {inferred}")
            return inferred
    
    # Try to infer from due_date
    if due_date:
        print("Trying to infer from due_date...")
        inferred = infer_timezone_from_date(due_date)
        if inferred:
            print(f"Inferred from due_date: {inferred}")
            return inferred
    
    print("No timezone inferred, returning None")
    return None

# Test the problematic case
if __name__ == "__main__":
    print("=== Testing Timezone Inference ===\n")
    
    test_cases = [
        {
            "name": "Taiwan time",
            "due_date": "2025-09-04T14:00:00+0800",
            "time_zone": None
        },
        {
            "name": "US Eastern time", 
            "due_date": "2025-09-04T09:00:00-0500",
            "time_zone": None
        },
        {
            "name": "Japan time with explicit timezone",
            "due_date": "2025-09-04T15:00:00+0900",
            "time_zone": "Asia/Tokyo"
        }
    ]
    
    for test_case in test_cases:
        print(f"\n--- Test Case: {test_case['name']} ---")
        result = get_smart_timezone(
            test_case['time_zone'], 
            None, 
            test_case['due_date']
        )
        print(f"Final result: {result}")
        print("-" * 50)