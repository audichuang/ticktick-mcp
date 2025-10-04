import asyncio
import os
import json
import logging
import time
import secrets
import urllib.parse
import base64
import re
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv

from mcp.server.fastmcp import FastMCP
from .ticktick_client import TickTickClient
from .ics_sync import ICSSyncEngine, FilterManager, ConflictResolver, start_scheduler, get_scheduler
from .ics_sync.models import ICSSource, FilterRule, SyncConflict, OAuthToken, get_db_session, init_db

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# OAuth configuration
OAUTH_USERNAME = os.getenv("OAUTH_USERNAME", "admin")
OAUTH_PASSWORD = os.getenv("OAUTH_PASSWORD", "ticktick-mcp-password")

# OAuth Client Credentials for direct authentication (no user login redirect)
OAUTH_CLIENT_ID = os.getenv("OAUTH_CLIENT_ID", "ticktick-mcp-client")
OAUTH_CLIENT_SECRET = os.getenv("OAUTH_CLIENT_SECRET", "default-client-secret")

# Log warning if using default password
if OAUTH_PASSWORD == "ticktick-mcp-password":
    logger.warning("⚠️  Using default password! Please set OAUTH_PASSWORD environment variable for security.")

# Log warning if using default client secret
if OAUTH_CLIENT_SECRET == "default-client-secret":
    logger.warning("⚠️  Using default Client Secret! Please set OAUTH_CLIENT_SECRET environment variable for security.")

# In-memory storage for OAuth authorization codes (short-lived, 10 min)
auth_codes = {}  # code -> {client_id, redirect_uri, expires_at, username}

# Token management helper functions
def save_token_to_db(token: str, token_type: str, client_id: str, username: str,
                     scope: str, grant_type: str, expires_at: float, parent_token: str = None) -> None:
    """Save token to database"""
    db_session = get_db_session()
    try:
        oauth_token = OAuthToken(
            token=token,
            token_type=token_type,
            client_id=client_id,
            username=username,
            scope=scope,
            grant_type=grant_type,
            expires_at=datetime.utcfromtimestamp(expires_at),  # Use UTC to match comparisons
            parent_token=parent_token
        )
        db_session.add(oauth_token)
        db_session.commit()
        logger.info(f"Saved {token_type} token to database (expires: {oauth_token.expires_at} UTC)")
    except Exception as e:
        db_session.rollback()
        logger.error(f"Failed to save token to database: {e}")
    finally:
        db_session.close()

def get_token_from_db(token: str) -> Optional[Dict]:
    """Get token from database and check if expired"""
    db_session = get_db_session()
    try:
        oauth_token = db_session.query(OAuthToken).filter_by(token=token).first()
        if not oauth_token:
            return None

        # Check if expired
        if oauth_token.expires_at < datetime.utcnow():
            logger.info(f"Token expired: {token[:10]}...")
            return None

        return {
            'token': oauth_token.token,
            'token_type': oauth_token.token_type,
            'client_id': oauth_token.client_id,
            'username': oauth_token.username,
            'scope': oauth_token.scope,
            'grant_type': oauth_token.grant_type,
            'expires_at': oauth_token.expires_at.timestamp(),
            'parent_token': oauth_token.parent_token
        }
    finally:
        db_session.close()

def delete_token_from_db(token: str) -> None:
    """Delete token from database"""
    db_session = get_db_session()
    try:
        db_session.query(OAuthToken).filter_by(token=token).delete()
        db_session.commit()
        logger.info(f"Deleted token from database: {token[:10]}...")
    except Exception as e:
        db_session.rollback()
        logger.error(f"Failed to delete token: {e}")
    finally:
        db_session.close()

def cleanup_expired_tokens_db() -> None:
    """Remove expired tokens from database"""
    db_session = get_db_session()
    try:
        expired_count = db_session.query(OAuthToken).filter(
            OAuthToken.expires_at < datetime.utcnow()
        ).delete()
        db_session.commit()
        if expired_count > 0:
            logger.info(f"Cleaned up {expired_count} expired tokens")
    except Exception as e:
        db_session.rollback()
        logger.error(f"Failed to cleanup expired tokens: {e}")
    finally:
        db_session.close()

# Create FastMCP server
mcp = FastMCP("ticktick-remote")

# Create TickTick client
ticktick = None

# Timezone offset mapping for smart timezone detection (same as server.py)
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
    
    Args:
        date_string: ISO 8601 date string (e.g., "2025-06-09T08:00:00+0800")
    
    Returns:
        Timezone name (e.g., "Asia/Taipei") or None if not found
    """
    if not date_string:
        return None
    
    # Extract timezone offset using regex
    timezone_pattern = r'([+-]\d{4})$'
    match = re.search(timezone_pattern, date_string)
    
    if match:
        offset = match.group(1)
        return TIMEZONE_OFFSET_MAP.get(offset)
    
    return None

def normalize_timezone_format(date_string: str) -> str:
    """
    Normalize timezone format in ISO date string to TickTick API compatible format.
    
    Converts:
    - "2025-09-20T12:00:00+08:00" -> "2025-09-20T12:00:00+0800"
    - "2025-09-20T12:00:00+8:00" -> "2025-09-20T12:00:00+0800" 
    - "2025-09-20T12:00:00+8" -> "2025-09-20T12:00:00+0800"
    
    Args:
        date_string: ISO 8601 date string
    
    Returns:
        Date string with normalized timezone format
    """
    if not date_string:
        return date_string
    
    # Pattern to match timezone with colon: +08:00, -05:00, +8:00, etc.
    import re
    
    # Match timezone patterns at the end of the string
    timezone_pattern = r'([+-])(\d{1,2}):?(\d{2})?$'
    match = re.search(timezone_pattern, date_string)
    
    if match:
        sign = match.group(1)  # + or -
        hours = match.group(2).zfill(2)  # Ensure 2 digits
        minutes = match.group(3) or "00"  # Default to 00 if not present
        
        # Remove the original timezone part
        base_date = date_string[:match.start()]
        
        # Add normalized timezone format
        normalized_date = f"{base_date}{sign}{hours}{minutes}"
        return normalized_date
    
    # If no colon format found, try to fix single digit timezones like +8
    single_digit_pattern = r'([+-])(\d)$'
    match = re.search(single_digit_pattern, date_string)
    
    if match:
        sign = match.group(1)
        hours = match.group(2).zfill(2)  # Convert 8 to 08
        
        # Remove the original timezone part
        base_date = date_string[:match.start()]
        
        # Add normalized timezone format
        normalized_date = f"{base_date}{sign}{hours}00"
        return normalized_date
    
    return date_string

def get_smart_timezone(time_zone: str, start_date: str, due_date: str) -> Optional[str]:
    """
    Get the best timezone for the task using smart inference.
    
    Args:
        time_zone: Explicitly provided timezone
        start_date: Start date string
        due_date: Due date string
    
    Returns:
        Best timezone name to use
    """
    # If explicitly provided, use that
    if time_zone:
        return time_zone
    
    # Try to infer from start_date
    if start_date:
        inferred = infer_timezone_from_date(start_date)
        if inferred:
            return inferred
    
    # Try to infer from due_date
    if due_date:
        inferred = infer_timezone_from_date(due_date)
        if inferred:
            return inferred
    
    return None

def initialize_client():
    """Initialize the TickTick client with credentials."""
    global ticktick
    try:
        # Check if we have valid credentials
        if os.getenv("TICKTICK_ACCESS_TOKEN") is None:
            logger.error("No access token found in .env file.")
            return False
        
        # Initialize the client
        ticktick = TickTickClient()
        logger.info("TickTick client initialized successfully")
        
        # Test API connectivity
        projects = ticktick.get_projects()
        if 'error' in projects:
            logger.error(f"Failed to access TickTick API: {projects['error']}")
            return False
            
        logger.info(f"Successfully connected to TickTick API with {len(projects)} projects")
        
        # Initialize ICS sync database
        try:
            init_db()
            logger.info("ICS sync database initialized")
            
            # Start ICS sync scheduler
            scheduler = start_scheduler(ticktick)
            if scheduler:
                logger.info("ICS sync scheduler started")
        except Exception as e:
            logger.error(f"Failed to initialize ICS sync: {e}")
        
        return True
    except Exception as e:
        logger.error(f"Failed to initialize TickTick client: {e}")
        return False

# Format functions (reuse from original server)
def format_task(task: Dict) -> str:
    """Format a task into a human-readable string."""
    formatted = f"ID: {task.get('id', 'No ID')}\n"
    formatted += f"Title: {task.get('title', 'No title')}\n"
    formatted += f"Project ID: {task.get('projectId', 'None')}\n"
    
    if task.get('startDate'):
        formatted += f"Start Date: {task.get('startDate')}\n"
    if task.get('dueDate'):
        formatted += f"Due Date: {task.get('dueDate')}\n"
    
    priority_map = {0: "None", 1: "Low", 3: "Medium", 5: "High"}
    priority = task.get('priority', 0)
    formatted += f"Priority: {priority_map.get(priority, str(priority))}\n"
    
    status = "Completed" if task.get('status') == 2 else "Active"
    formatted += f"Status: {status}\n"
    
    # Add reminders if available
    reminders = task.get('reminders', [])
    if reminders:
        formatted += f"\nReminders:\n"
        for reminder in reminders:
            # Parse TRIGGER format
            if reminder.startswith("TRIGGER:"):
                trigger_value = reminder[8:]  # Remove "TRIGGER:"
                if trigger_value == "PT0S":
                    formatted += "- At time of event\n"
                elif trigger_value.startswith("PT"):
                    # Parse minutes/hours
                    if "M" in trigger_value:
                        minutes = trigger_value.replace("PT", "").replace("M", "")
                        formatted += f"- {minutes} minutes before\n"
                    elif "H" in trigger_value:
                        hours = trigger_value.replace("PT", "").replace("H", "")
                        formatted += f"- {hours} hours before\n"
                elif trigger_value.startswith("P"):
                    # Parse days/hours format like P0DT1H0M0S or P1DT0H0M0S
                    if "DT" in trigger_value:
                        parts = trigger_value.replace("P", "").split("DT")
                        days = parts[0].replace("D", "") if parts[0] else "0"
                        time_part = parts[1] if len(parts) > 1 else ""
                        
                        hours = "0"
                        if "H" in time_part:
                            hours = time_part.split("H")[0]
                        
                        if days != "0":
                            formatted += f"- {days} day(s) before\n"
                        elif hours != "0":
                            formatted += f"- {hours} hour(s) before\n"
                else:
                    formatted += f"- {reminder}\n"
            else:
                formatted += f"- {reminder}\n"
    
    if task.get('content'):
        formatted += f"\nContent:\n{task.get('content')}\n"
    
    items = task.get('items', [])
    if items:
        formatted += f"\nSubtasks ({len(items)}):\n"
        for i, item in enumerate(items, 1):
            status = "✓" if item.get('status') == 1 else "□"
            formatted += f"{i}. [{status}] {item.get('title', 'No title')}\n"
    
    return formatted

def format_project(project: Dict) -> str:
    """Format a project into a human-readable string."""
    formatted = f"Name: {project.get('name', 'No name')}\n"
    formatted += f"ID: {project.get('id', 'No ID')}\n"
    
    if project.get('color'):
        formatted += f"Color: {project.get('color')}\n"
    if project.get('viewMode'):
        formatted += f"View Mode: {project.get('viewMode')}\n"
    if 'closed' in project:
        formatted += f"Closed: {'Yes' if project.get('closed') else 'No'}\n"
    if project.get('kind'):
        formatted += f"Kind: {project.get('kind')}\n"
    
    return formatted

# Copy all MCP tools from original server
@mcp.tool()
async def get_projects() -> str:
    """Get all projects from TickTick."""
    if not ticktick:
        if not initialize_client():
            return "Failed to initialize TickTick client. Please check your API credentials."
    
    try:
        projects = ticktick.get_projects()
        if 'error' in projects:
            return f"Error fetching projects: {projects['error']}"
        
        if not projects:
            return "No projects found."
        
        result = f"Found {len(projects)} projects:\n\n"
        for i, project in enumerate(projects, 1):
            result += f"Project {i}:\n" + format_project(project) + "\n"
        
        return result
    except Exception as e:
        logger.error(f"Error in get_projects: {e}")
        return f"Error retrieving projects: {str(e)}"

@mcp.tool()
async def get_project(project_id: str) -> str:
    """
    Get details about a specific project.
    
    Args:
        project_id: ID of the project
    """
    if not ticktick:
        if not initialize_client():
            return "Failed to initialize TickTick client. Please check your API credentials."
    
    try:
        project = ticktick.get_project(project_id)
        if 'error' in project:
            return f"Error fetching project: {project['error']}"
        
        return format_project(project)
    except Exception as e:
        logger.error(f"Error in get_project: {e}")
        return f"Error retrieving project: {str(e)}"

@mcp.tool()
async def get_project_tasks(project_id: str) -> str:
    """
    Get all tasks in a specific project.
    
    Args:
        project_id: ID of the project
    """
    if not ticktick:
        if not initialize_client():
            return "Failed to initialize TickTick client. Please check your API credentials."
    
    try:
        project_data = ticktick.get_project_with_data(project_id)
        if 'error' in project_data:
            return f"Error fetching project data: {project_data['error']}"
        
        tasks = project_data.get('tasks', [])
        if not tasks:
            return f"No tasks found in project '{project_data.get('project', {}).get('name', project_id)}'."
        
        result = f"Found {len(tasks)} tasks in project '{project_data.get('project', {}).get('name', project_id)}':\n\n"
        for i, task in enumerate(tasks, 1):
            result += f"Task {i}:\n" + format_task(task) + "\n"
        
        return result
    except Exception as e:
        logger.error(f"Error in get_project_tasks: {e}")
        return f"Error retrieving project tasks: {str(e)}"

@mcp.tool()
async def get_task(project_id: str, task_id: str) -> str:
    """
    Get details about a specific task.
    
    Args:
        project_id: ID of the project
        task_id: ID of the task
    """
    if not ticktick:
        if not initialize_client():
            return "Failed to initialize TickTick client. Please check your API credentials."
    
    try:
        task = ticktick.get_task(project_id, task_id)
        if 'error' in task:
            return f"Error fetching task: {task['error']}"
        
        return format_task(task)
    except Exception as e:
        logger.error(f"Error in get_task: {e}")
        return f"Error retrieving task: {str(e)}"

@mcp.tool()
async def create_task(
    title: str, 
    project_id: str, 
    content: str = None, 
    start_date: str = None, 
    due_date: str = None, 
    priority: int = 0,
    is_all_day: bool = False,
    time_zone: str = None,
    reminders: List[str] = None
) -> str:
    """
    Create a new task in TickTick with optional reminders and timezone support.
    
    Args:
        title: Task title
        project_id: ID of the project to add the task to
        content: Task description/content (optional)
        start_date: Start date in ISO format with timezone (optional)
                   Examples:
                   - "2025-06-09T08:00:00+0800" (8AM Taiwan time)
                   - "2025-06-09T14:00:00+08:00" (also supported, will be normalized)
                   - "2025-06-09T09:00:00-0500" (9AM US Eastern)
                   Note: Both +0800 and +08:00 formats are accepted
        due_date: Due date in ISO format with timezone (optional)
                 Examples:
                 - "2025-06-09T18:00:00+0800" (6PM Taiwan time)
                 - "2025-06-09T18:00:00+08:00" (also supported, will be normalized)
                 - "2025-06-09T17:00:00-0500" (5PM US Eastern)
                 Note: Both +0800 and +08:00 formats are accepted
        priority: Priority level (0: None, 1: Low, 3: Medium, 5: High) (optional)
        is_all_day: Whether this is an all-day task (default: False) (optional)
        time_zone: Timezone for the task (optional)
                  Common timezones:
                  - "Asia/Taipei" (Taiwan, UTC+8)
                  - "Asia/Tokyo" (Japan, UTC+9) 
                  - "Asia/Shanghai" (China, UTC+8)
                  - "America/New_York" (US Eastern)
                  - "America/Los_Angeles" (US Pacific)
                  - "Europe/London" (UK)
                  If not provided, timezone will be inferred from the date format
        reminders: List of reminder triggers in TRIGGER format (optional)
                  Examples:
                  - ["TRIGGER:PT0S"] - At time of event
                  - ["TRIGGER:PT15M"] - 15 minutes before
                  - ["TRIGGER:P0DT1H0M0S"] - 1 hour before
                  - ["TRIGGER:P1DT0H0M0S"] - 1 day before
                  - ["TRIGGER:P0DT9H0M0S", "TRIGGER:PT0S"] - 9 hours before AND at time
    """
    if not ticktick:
        if not initialize_client():
            return "Failed to initialize TickTick client. Please check your API credentials."
    
    if priority not in [0, 1, 3, 5]:
        return "Invalid priority. Must be 0 (None), 1 (Low), 3 (Medium), or 5 (High)."
    
    try:
        for date_str, date_name in [(start_date, "start_date"), (due_date, "due_date")]:
            if date_str:
                try:
                    datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                except ValueError:
                    return f"Invalid {date_name} format. Use ISO format: YYYY-MM-DDThh:mm:ss+0000"
        
        if reminders:
            for reminder in reminders:
                if not reminder.startswith("TRIGGER:"):
                    return f"Invalid reminder format: {reminder}. Must start with 'TRIGGER:'"
        
        # Normalize timezone format in dates before sending to API
        normalized_start_date = normalize_timezone_format(start_date) if start_date else None
        normalized_due_date = normalize_timezone_format(due_date) if due_date else None
        
        # Get smart timezone
        smart_timezone = get_smart_timezone(time_zone, normalized_start_date, normalized_due_date)
        
        task = ticktick.create_task(
            title=title,
            project_id=project_id,
            content=content,
            start_date=normalized_start_date,
            due_date=normalized_due_date,
            priority=priority,
            is_all_day=is_all_day,
            time_zone=smart_timezone,
            reminders=reminders
        )
        
        if 'error' in task:
            return f"Error creating task: {task['error']}"
        
        return f"Task created successfully:\n\n" + format_task(task)
    except Exception as e:
        logger.error(f"Error in create_task: {e}")
        return f"Error creating task: {str(e)}"

@mcp.tool()
async def update_task(
    task_id: str,
    project_id: str,
    title: str = None,
    content: str = None,
    start_date: str = None,
    due_date: str = None,
    priority: int = None,
    is_all_day: bool = None,
    time_zone: str = None,
    reminders: List[str] = None
) -> str:
    """
    Update an existing task in TickTick with optional reminders and timezone support.
    
    Args:
        task_id: ID of the task to update
        project_id: ID of the project the task belongs to
        title: New task title (optional)
        content: New task description/content (optional)
        start_date: New start date in ISO format with timezone (optional)
                   Examples:
                   - "2025-06-09T08:00:00+0800" (8AM Taiwan time)
                   - "2025-06-09T14:00:00+08:00" (also supported, will be normalized)
                   - "2025-06-09T09:00:00-0500" (9AM US Eastern)
                   Note: Both +0800 and +08:00 formats are accepted
        due_date: New due date in ISO format with timezone (optional)
                 Examples:
                 - "2025-06-09T18:00:00+0800" (6PM Taiwan time)
                 - "2025-06-09T18:00:00+08:00" (also supported, will be normalized)
                 - "2025-06-09T17:00:00-0500" (5PM US Eastern)
                 Note: Both +0800 and +08:00 formats are accepted
        priority: New priority level (0: None, 1: Low, 3: Medium, 5: High) (optional)
        is_all_day: Whether this is an all-day task (optional)
        time_zone: Timezone for the task (optional)
                  Common timezones:
                  - "Asia/Taipei" (Taiwan, UTC+8)
                  - "Asia/Tokyo" (Japan, UTC+9) 
                  - "Asia/Shanghai" (China, UTC+8)
                  - "America/New_York" (US Eastern)
                  - "America/Los_Angeles" (US Pacific)
                  - "Europe/London" (UK)
                  If not provided, timezone will be inferred from the date format
        reminders: List of reminder triggers in TRIGGER format (optional)
                  Examples:
                  - ["TRIGGER:PT0S"] - At time of event
                  - ["TRIGGER:PT15M"] - 15 minutes before
                  - ["TRIGGER:P0DT1H0M0S"] - 1 hour before
                  - ["TRIGGER:P1DT0H0M0S"] - 1 day before
                  - [] - Remove all reminders
    """
    if not ticktick:
        if not initialize_client():
            return "Failed to initialize TickTick client. Please check your API credentials."
    
    if priority is not None and priority not in [0, 1, 3, 5]:
        return "Invalid priority. Must be 0 (None), 1 (Low), 3 (Medium), or 5 (High)."
    
    try:
        for date_str, date_name in [(start_date, "start_date"), (due_date, "due_date")]:
            if date_str:
                try:
                    datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                except ValueError:
                    return f"Invalid {date_name} format. Use ISO format: YYYY-MM-DDThh:mm:ss+0000"
        
        if reminders is not None and reminders:
            for reminder in reminders:
                if not reminder.startswith("TRIGGER:"):
                    return f"Invalid reminder format: {reminder}. Must start with 'TRIGGER:'"
        
        # Normalize timezone format in dates before sending to API
        normalized_start_date = normalize_timezone_format(start_date) if start_date else None
        normalized_due_date = normalize_timezone_format(due_date) if due_date else None
        
        # Get smart timezone
        smart_timezone = get_smart_timezone(time_zone, normalized_start_date, normalized_due_date)
        
        task = ticktick.update_task(
            task_id=task_id,
            project_id=project_id,
            title=title,
            content=content,
            start_date=normalized_start_date,
            due_date=normalized_due_date,
            priority=priority,
            is_all_day=is_all_day,
            time_zone=smart_timezone,
            reminders=reminders
        )
        
        if 'error' in task:
            return f"Error updating task: {task['error']}"
        
        return f"Task updated successfully:\n\n" + format_task(task)
    except Exception as e:
        logger.error(f"Error in update_task: {e}")
        return f"Error updating task: {str(e)}"

@mcp.tool()
async def complete_task(project_id: str, task_id: str) -> str:
    """
    Mark a task as complete.
    
    Args:
        project_id: ID of the project
        task_id: ID of the task
    """
    if not ticktick:
        if not initialize_client():
            return "Failed to initialize TickTick client. Please check your API credentials."
    
    try:
        result = ticktick.complete_task(project_id, task_id)
        if 'error' in result:
            return f"Error completing task: {result['error']}"
        
        return f"Task {task_id} marked as complete."
    except Exception as e:
        logger.error(f"Error in complete_task: {e}")
        return f"Error completing task: {str(e)}"

@mcp.tool()
async def delete_task(project_id: str, task_id: str) -> str:
    """
    Delete a task.
    
    Args:
        project_id: ID of the project
        task_id: ID of the task
    """
    if not ticktick:
        if not initialize_client():
            return "Failed to initialize TickTick client. Please check your API credentials."
    
    try:
        result = ticktick.delete_task(project_id, task_id)
        if 'error' in result:
            return f"Error deleting task: {result['error']}"
        
        return f"Task {task_id} deleted successfully."
    except Exception as e:
        logger.error(f"Error in delete_task: {e}")
        return f"Error deleting task: {str(e)}"

@mcp.tool()
async def create_project(
    name: str,
    color: str = "#F18181",
    view_mode: str = "list"
) -> str:
    """
    Create a new project in TickTick.
    
    Args:
        name: Project name
        color: Color code (hex format) (optional)
        view_mode: View mode - one of list, kanban, or timeline (optional)
    """
    if not ticktick:
        if not initialize_client():
            return "Failed to initialize TickTick client. Please check your API credentials."
    
    if view_mode not in ["list", "kanban", "timeline"]:
        return "Invalid view_mode. Must be one of: list, kanban, timeline."
    
    try:
        project = ticktick.create_project(
            name=name,
            color=color,
            view_mode=view_mode
        )
        
        if 'error' in project:
            return f"Error creating project: {project['error']}"
        
        return f"Project created successfully:\n\n" + format_project(project)
    except Exception as e:
        logger.error(f"Error in create_project: {e}")
        return f"Error creating project: {str(e)}"

@mcp.tool()
async def delete_project(project_id: str) -> str:
    """
    Delete a project.
    
    Args:
        project_id: ID of the project
    """
    if not ticktick:
        if not initialize_client():
            return "Failed to initialize TickTick client. Please check your API credentials."
    
    try:
        result = ticktick.delete_project(project_id)
        if 'error' in result:
            return f"Error deleting project: {result['error']}"
        
        return f"Project {project_id} deleted successfully."
    except Exception as e:
        logger.error(f"Error in delete_project: {e}")
        return f"Error deleting project: {str(e)}"

# ICS Sync MCP Tools
@mcp.tool()
async def add_ics_source(
    name: str,
    url: str,
    project_id: str,
    sync_interval: int = 3600
) -> str:
    """
    Add a new ICS calendar source for synchronization.
    
    Args:
        name: Display name for the ICS source
        url: ICS calendar URL (e.g., Outlook calendar URL)
        project_id: TickTick project ID to sync events to
        sync_interval: Sync interval in seconds (default: 3600 = 1 hour)
    """
    if not ticktick:
        if not initialize_client():
            return "Failed to initialize TickTick client. Please check your API credentials."
    
    try:
        db_session = get_db_session()
        
        # Check if project exists
        projects = ticktick.get_projects()
        project_exists = any(p.get('id') == project_id for p in projects)
        if not project_exists:
            return f"Project {project_id} not found. Please create the project first."
        
        # Create ICS source
        source = ICSSource(
            name=name,
            url=url,
            project_id=project_id,
            sync_interval=sync_interval,
            enabled=True
        )
        
        db_session.add(source)
        db_session.commit()
        
        # Add to scheduler
        scheduler = get_scheduler()
        if scheduler:
            scheduler.add_source(source.id)
        
        return f"✅ ICS source '{name}' added successfully!\n\n" \
               f"📋 **Details**:\n" \
               f"• Name: {name}\n" \
               f"• URL: {url}\n" \
               f"• Project: {project_id}\n" \
               f"• Sync Interval: {sync_interval} seconds\n" \
               f"• Status: Enabled\n\n" \
               f"🔄 Next sync will happen automatically within {sync_interval} seconds."
        
    except Exception as e:
        logger.error(f"Error in add_ics_source: {e}")
        return f"Error adding ICS source: {str(e)}"

@mcp.tool()
async def sync_ics_now(source_id: int = None) -> str:
    """
    Trigger immediate synchronization for an ICS source or all sources.
    
    Args:
        source_id: ID of specific source to sync, or None for all sources
    """
    if not ticktick:
        if not initialize_client():
            return "Failed to initialize TickTick client. Please check your API credentials."
    
    try:
        scheduler = get_scheduler()
        if not scheduler:
            return "❌ ICS sync scheduler not available."
        
        if source_id:
            result = scheduler.sync_now(source_id)
            if 'error' in result:
                return f"❌ **Sync failed**: {result['error']}"
            
            stats = result.get('stats', {})
            return f"✅ **Sync completed for source {source_id}**\n\n" \
                   f"📊 **Statistics**:\n" \
                   f"• Events created: {stats.get('created', 0)}\n" \
                   f"• Events updated: {stats.get('updated', 0)}\n" \
                   f"• Events deleted: {stats.get('deleted', 0)}\n" \
                   f"• Conflicts detected: {stats.get('conflicts', 0)}\n\n" \
                   f"🕐 Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        else:
            result = scheduler.sync_now()
            total_stats = result.get('total_stats', {})
            
            return f"✅ **Sync completed for all sources**\n\n" \
                   f"📊 **Total Statistics**:\n" \
                   f"• Sources synced: {result.get('total_sources', 0)}\n" \
                   f"• Events created: {total_stats.get('created', 0)}\n" \
                   f"• Events updated: {total_stats.get('updated', 0)}\n" \
                   f"• Events deleted: {total_stats.get('deleted', 0)}\n" \
                   f"• Conflicts detected: {total_stats.get('conflicts', 0)}\n\n" \
                   f"🕐 Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
    except Exception as e:
        logger.error(f"Error in sync_ics_now: {e}")
        return f"Error triggering sync: {str(e)}"

@mcp.tool()
async def get_ics_sync_status(source_id: int = None) -> str:
    """
    Get synchronization status for ICS sources.
    
    Args:
        source_id: ID of specific source, or None for all sources
    """
    if not ticktick:
        if not initialize_client():
            return "Failed to initialize TickTick client. Please check your API credentials."
    
    try:
        sync_engine = ICSSyncEngine(ticktick)
        status = sync_engine.get_sync_status(source_id)
        
        if 'error' in status:
            return f"❌ Error getting status: {status['error']}"
        
        result = f"📊 **ICS Sync Status**\n\n"
        
        for source_status in status['sources']:
            result += f"📋 **{source_status['name']}** (ID: {source_status['id']})\n"
            result += f"• URL: {source_status['url']}\n"
            result += f"• Status: {'🟢 Enabled' if source_status['enabled'] else '🔴 Disabled'}\n"
            result += f"• Sync Interval: {source_status['sync_interval']} seconds\n"
            result += f"• Last Sync: {source_status['last_sync'] or 'Never'}\n"
            result += f"• Synced Tasks: {source_status['mapping_count']}\n"
            result += f"• Pending Conflicts: {source_status['pending_conflicts']}\n"
            
            if source_status.get('latest_sync'):
                sync_info = source_status['latest_sync']
                result += f"• Latest Sync Status: {sync_info['status']}\n"
                result += f"• Events Processed: {sync_info['events_processed']}\n"
                result += f"• Events Created: {sync_info['events_created']}\n"
                result += f"• Events Updated: {sync_info['events_updated']}\n"
                
                if sync_info.get('error_message'):
                    result += f"• Last Error: {sync_info['error_message']}\n"
            
            result += "\n"
        
        # Add scheduler status
        scheduler = get_scheduler()
        if scheduler:
            scheduler_status = scheduler.get_scheduler_status()
            result += f"🔄 **Scheduler Status**: {'🟢 Running' if scheduler_status['running'] else '🔴 Stopped'}\n"
            result += f"📅 **Active Jobs**: {scheduler_status['job_count']}\n"
        
        return result
        
    except Exception as e:
        logger.error(f"Error in get_ics_sync_status: {e}")
        return f"Error getting sync status: {str(e)}"

@mcp.tool()
async def manage_ics_filter_rules(
    source_id: int,
    action: str,
    rule_type: str = None,
    rule_value: str = None
) -> str:
    """
    Manage filter rules for an ICS source.
    
    Args:
        source_id: ID of the ICS source
        action: Action to perform ('add', 'list', 'remove', 'clear')
        rule_type: Type of filter rule ('exclude_keyword', 'include_attendee', 'time_range')
        rule_value: Value for the filter rule (JSON string for complex rules)
    """
    if not ticktick:
        if not initialize_client():
            return "Failed to initialize TickTick client. Please check your API credentials."
    
    try:
        db_session = get_db_session()
        source = db_session.query(ICSSource).filter_by(id=source_id).first()
        
        if not source:
            return f"❌ ICS source {source_id} not found."
        
        if action == 'list':
            rules = db_session.query(FilterRule).filter_by(source_id=source_id).all()
            
            if not rules:
                return f"📋 **Filter Rules for '{source.name}'**\n\nNo filter rules configured."
            
            result = f"📋 **Filter Rules for '{source.name}'**\n\n"
            for i, rule in enumerate(rules, 1):
                status = "🟢 Enabled" if rule.enabled else "🔴 Disabled"
                result += f"{i}. **{rule.rule_type}** {status}\n"
                result += f"   Value: {rule.rule_value}\n"
                result += f"   Created: {rule.created_at.strftime('%Y-%m-%d %H:%M')}\n\n"
            
            return result
        
        elif action == 'add':
            if not rule_type or not rule_value:
                return "❌ rule_type and rule_value are required for 'add' action."
            
            # Create new filter rule
            filter_rule = FilterRule(
                source_id=source_id,
                rule_type=rule_type,
                rule_value=rule_value,
                enabled=True
            )
            
            db_session.add(filter_rule)
            db_session.commit()
            
            return f"✅ **Filter rule added to '{source.name}'**\n\n" \
                   f"• Type: {rule_type}\n" \
                   f"• Value: {rule_value}\n" \
                   f"• Status: Enabled\n\n" \
                   f"💡 The rule will be applied in the next sync cycle."
        
        elif action == 'clear':
            rules = db_session.query(FilterRule).filter_by(source_id=source_id).all()
            count = len(rules)
            
            for rule in rules:
                db_session.delete(rule)
            
            db_session.commit()
            
            return f"✅ **Cleared all filter rules for '{source.name}'**\n\n" \
                   f"Removed {count} filter rules."
        
        else:
            return f"❌ Invalid action '{action}'. Use: add, list, clear"
        
    except Exception as e:
        logger.error(f"Error in manage_ics_filter_rules: {e}")
        return f"Error managing filter rules: {str(e)}"

@mcp.tool()
async def get_ics_conflicts(source_id: int = None) -> str:
    """
    Get pending synchronization conflicts.
    
    Args:
        source_id: ID of specific source, or None for all sources
    """
    if not ticktick:
        if not initialize_client():
            return "Failed to initialize TickTick client. Please check your API credentials."
    
    try:
        conflict_resolver = ConflictResolver(ticktick)
        conflicts = conflict_resolver.get_pending_conflicts(source_id)
        
        if not conflicts:
            return "🎉 **No pending conflicts**\n\nAll ICS sources are synchronized without conflicts."
        
        result = f"⚠️ **Pending Sync Conflicts** ({len(conflicts)} total)\n\n"
        
        for conflict in conflicts:
            source = conflict.source_id
            result += f"🔴 **Conflict #{conflict.id}**\n"
            result += f"• Source ID: {source}\n"
            result += f"• ICS UID: {conflict.ics_uid}\n"
            result += f"• TickTick Task: {conflict.ticktick_task_id}\n"
            result += f"• Type: {conflict.conflict_type}\n"
            result += f"• Detected: {conflict.detected_at.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        result += "💡 **How to resolve**:\n"
        result += "Use `resolve_ics_conflict(conflict_id, resolution)` to resolve conflicts.\n"
        result += "Available resolutions: 'keep_ics', 'keep_ticktick', 'keep_both', 'delete_both'"
        
        return result
        
    except Exception as e:
        logger.error(f"Error in get_ics_conflicts: {e}")
        return f"Error getting conflicts: {str(e)}"

@mcp.tool()
async def resolve_ics_conflict(
    conflict_id: int,
    resolution: str
) -> str:
    """
    Resolve a synchronization conflict.
    
    Args:
        conflict_id: ID of the conflict to resolve
        resolution: Resolution strategy ('keep_ics', 'keep_ticktick', 'keep_both', 'delete_both')
    """
    if not ticktick:
        if not initialize_client():
            return "Failed to initialize TickTick client. Please check your API credentials."
    
    if resolution not in ['keep_ics', 'keep_ticktick', 'keep_both', 'delete_both']:
        return "❌ Invalid resolution. Use: keep_ics, keep_ticktick, keep_both, delete_both"
    
    try:
        conflict_resolver = ConflictResolver(ticktick)
        success = conflict_resolver.resolve_conflict(conflict_id, resolution)
        
        if success:
            return f"✅ **Conflict resolved successfully**\n\n" \
                   f"• Conflict ID: {conflict_id}\n" \
                   f"• Resolution: {resolution}\n" \
                   f"• Resolved at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n" \
                   f"The conflict has been resolved according to your chosen strategy."
        else:
            return f"❌ **Failed to resolve conflict {conflict_id}**\n\n" \
                   f"Please check the logs for more details or try a different resolution strategy."
        
    except Exception as e:
        logger.error(f"Error in resolve_ics_conflict: {e}")
        return f"Error resolving conflict: {str(e)}"

# Initialize client on module load (non-blocking)
# Client will be initialized on first request if needed
logger.info("TickTick MCP Remote Server starting...")

# Try to setup credentials from environment if .env doesn't exist
if not os.path.exists('.env'):
    try:
        from .non_interactive_auth import setup_credentials_from_env
        if setup_credentials_from_env():
            logger.info("Credentials loaded from environment variables")
            # Reload dotenv to pick up the new .env file
            load_dotenv()
    except Exception as e:
        logger.warning(f"Failed to setup credentials from environment: {e}")

# HTML template for the login page
LOGIN_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TickTick MCP - Authorization</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: #f5f5f5;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            padding: 20px;
        }}
        
        .container {{
            background: white;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1), 0 1px 3px rgba(0, 0, 0, 0.08);
            max-width: 400px;
            width: 100%;
            padding: 40px;
        }}
        
        .logo {{
            text-align: center;
            margin-bottom: 30px;
        }}
        
        .logo h1 {{
            color: #333;
            font-size: 24px;
            font-weight: 600;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
        }}
        
        .logo .icon {{
            width: 32px;
            height: 32px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
        }}
        
        .auth-info {{
            background-color: #f8f9fa;
            border: 1px solid #e9ecef;
            border-radius: 8px;
            padding: 16px;
            margin-bottom: 24px;
        }}
        
        .auth-info h2 {{
            font-size: 16px;
            color: #333;
            margin-bottom: 8px;
            font-weight: 500;
        }}
        
        .auth-info .client-name {{
            font-weight: 600;
            color: #007bff;
        }}
        
        .auth-info .redirect-url {{
            font-size: 12px;
            color: #6c757d;
            word-break: break-all;
            margin-top: 4px;
        }}
        
        .form-group {{
            margin-bottom: 20px;
        }}
        
        label {{
            display: block;
            margin-bottom: 8px;
            color: #495057;
            font-size: 14px;
            font-weight: 500;
        }}
        
        input[type="text"],
        input[type="password"] {{
            width: 100%;
            padding: 10px 14px;
            border: 1px solid #ced4da;
            border-radius: 6px;
            font-size: 14px;
            transition: border-color 0.15s ease-in-out, box-shadow 0.15s ease-in-out;
        }}
        
        input[type="text"]:focus,
        input[type="password"]:focus {{
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }}
        
        .button-group {{
            display: flex;
            gap: 12px;
            margin-top: 24px;
        }}
        
        button {{
            flex: 1;
            padding: 10px 20px;
            border: none;
            border-radius: 6px;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.15s ease-in-out;
        }}
        
        .btn-cancel {{
            background-color: #e9ecef;
            color: #495057;
        }}
        
        .btn-cancel:hover {{
            background-color: #dee2e6;
        }}
        
        .btn-approve {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }}
        
        .btn-approve:hover {{
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
        }}
        
        .error-message {{
            background-color: #f8d7da;
            border: 1px solid #f5c6cb;
            color: #721c24;
            padding: 12px;
            border-radius: 6px;
            margin-bottom: 20px;
            font-size: 14px;
        }}
        
        .hidden {{
            display: none;
        }}
        
        @media (max-width: 480px) {{
            .container {{
                padding: 30px 20px;
            }}
            
            .logo h1 {{
                font-size: 20px;
            }}
            
            .button-group {{
                flex-direction: column;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">
            <h1>
                <span class="icon">T</span>
                TickTick MCP
            </h1>
        </div>
        
        <div class="auth-info">
            <h2><span class="client-name">{client_name}</span> is requesting access</h2>
            <div class="redirect-url">Redirect: {redirect_url}</div>
        </div>
        
        <div id="error-message" class="error-message {error_class}">
            {error_message}
        </div>
        
        <form method="POST" action="{form_action}">
            <div class="form-group">
                <label for="username">Username</label>
                <input type="text" id="username" name="username" required autofocus>
            </div>
            
            <div class="form-group">
                <label for="password">Password</label>
                <input type="password" id="password" name="password" required>
            </div>
            
            <input type="hidden" name="client_id" value="{client_id}">
            <input type="hidden" name="redirect_uri" value="{redirect_uri}">
            <input type="hidden" name="response_type" value="{response_type}">
            <input type="hidden" name="state" value="{state}">
            <input type="hidden" name="scope" value="{scope}">
            
            <div class="button-group">
                <button type="button" class="btn-cancel" onclick="handleCancel()">Cancel</button>
                <button type="submit" class="btn-approve">Approve</button>
            </div>
        </form>
    </div>
    
    <script>
        function handleCancel() {{
            // Redirect back with an error
            const params = new URLSearchParams(window.location.search);
            const redirectUri = params.get('redirect_uri');
            const state = params.get('state');
            
            if (redirectUri) {{
                const separator = redirectUri.includes('?') ? '&' : '?';
                window.location.href = redirectUri + separator + 'error=access_denied' + (state ? '&state=' + state : '');
            }}
        }}
    </script>
</body>
</html>
"""

def cleanup_expired_tokens():
    """Remove expired authorization codes and database tokens."""
    current_time = time.time()

    # Clean up auth codes
    expired_codes = [code for code, data in auth_codes.items() if data['expires_at'] < current_time]
    for code in expired_codes:
        del auth_codes[code]

    # Clean up database tokens
    cleanup_expired_tokens_db()

async def mcp_sse_with_heartbeat(mcp_app, scope, receive, send):
    """
    Wrap MCP SSE connection with periodic heartbeat to prevent connection timeouts.
    Sends SSE comment every 30 seconds to keep the connection alive.
    """
    # Create a custom send function that intercepts responses
    heartbeat_task = None
    send_lock = asyncio.Lock()

    async def send_with_heartbeat(message):
        """Custom send that allows heartbeat to be sent"""
        async with send_lock:
            await send(message)

    async def heartbeat_loop():
        """Send SSE comments every 30 seconds to keep connection alive"""
        while True:
            try:
                await asyncio.sleep(30)  # 30 seconds interval (< 60s proxy timeout)
                async with send_lock:
                    # Send SSE comment (won't interrupt data stream)
                    await send({
                        'type': 'http.response.body',
                        'body': b': heartbeat\n\n',
                        'more_body': True
                    })
                    logger.debug("SSE heartbeat sent")
            except asyncio.CancelledError:
                logger.info("SSE heartbeat stopped")
                break
            except Exception as e:
                logger.error(f"SSE heartbeat error: {e}")
                break

    # Intercept the initial response to start heartbeat
    original_send = send

    async def intercepting_send(message):
        nonlocal heartbeat_task
        if message['type'] == 'http.response.start':
            # Start heartbeat after response headers are sent
            heartbeat_task = asyncio.create_task(heartbeat_loop())
        await send_with_heartbeat(message)

    try:
        # Call the original MCP app with intercepting send
        await mcp_app(scope, receive, intercepting_send)
    finally:
        # Clean up heartbeat task
        if heartbeat_task:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass

def run_remote_server(
    host: str = "0.0.0.0",
    port: int = 8000,
    log_level: str = "info"
):
    """Run the remote server with SSE support and OAuth authentication."""
    logger.info(f"Starting TickTick MCP Remote Server with OAuth on {host}:{port}")
    logger.info("=" * 60)
    logger.info("🔐 OAuth Credentials:")
    logger.info(f"   Username: {OAUTH_USERNAME}")
    logger.info(f"   Password: {OAUTH_PASSWORD}")
    logger.info("=" * 60)
    
    # Run the server with SSE transport using FastMCP's built-in method
    # Set environment variables for uvicorn
    import os
    os.environ["HOST"] = host
    os.environ["PORT"] = str(port)
    
    # Use the sse_app method to get the ASGI app
    import uvicorn
    from starlette.applications import Starlette
    from starlette.routing import Mount, Route
    from starlette.responses import PlainTextResponse
    from starlette.middleware import Middleware
    
    # Create a custom ASGI app with OAuth authentication
    mcp_app = mcp.sse_app()
    base_url = f"http://{host}:{port}"
    
    async def oauth_app(scope, receive, send):
        """ASGI app that handles OAuth authentication"""
        if scope["type"] == "http":
            path = scope["path"]
            headers = dict(scope.get("headers", []))
            
            # Parse query parameters
            query_string = scope.get("query_string", b"").decode("utf-8")
            query_params = urllib.parse.parse_qs(query_string)
            
            # Handle OAuth discovery endpoint
            if path == "/.well-known/oauth-authorization-server":
                # Extract the actual host from request headers
                host_header = headers.get(b'host', b'').decode('utf-8')
                
                # Check for X-Forwarded-Proto header (for reverse proxy scenarios)
                proto_header = headers.get(b'x-forwarded-proto', b'').decode('utf-8')
                protocol = proto_header if proto_header else 'https' if host_header and ':443' in host_header else 'http'
                
                # Construct the actual issuer URL based on the request
                if host_header:
                    issuer_url = f"{protocol}://{host_header}"
                else:
                    # Fallback to base_url if no host header
                    issuer_url = base_url
                
                discovery = {
                    "issuer": issuer_url,
                    "authorization_endpoint": f"{issuer_url}/oauth/authorize",
                    "token_endpoint": f"{issuer_url}/oauth/token",
                    "registration_endpoint": f"{issuer_url}/oauth/register",
                    "scopes_supported": ["mcp"],
                    "response_types_supported": ["code"],
                    "response_modes_supported": ["query"],
                    "grant_types_supported": ["authorization_code", "client_credentials", "refresh_token"],
                    "token_endpoint_auth_methods_supported": ["client_secret_basic", "client_secret_post", "none"],
                    "revocation_endpoint": f"{issuer_url}/oauth/token",
                    "code_challenge_methods_supported": ["plain", "S256"]
                }
                
                response_body = json.dumps(discovery).encode()
                await send({
                    'type': 'http.response.start',
                    'status': 200,
                    'headers': [
                        (b'content-type', b'application/json'),
                        (b'access-control-allow-origin', b'*'),
                        (b'cache-control', b'max-age=3600'),
                    ],
                })
                await send({
                    'type': 'http.response.body',
                    'body': response_body,
                })
                return
            
            # Handle OAuth authorize endpoint (GET)
            if path == "/oauth/authorize" and scope["method"] == "GET":
                # Extract parameters
                client_id = query_params.get('client_id', [''])[0]
                redirect_uri = query_params.get('redirect_uri', [''])[0]
                response_type = query_params.get('response_type', [''])[0]
                state = query_params.get('state', [''])[0]
                scope_param = query_params.get('scope', [''])[0]
                
                # Validate required parameters
                if not client_id or not redirect_uri or response_type != 'code':
                    await send({
                        'type': 'http.response.start',
                        'status': 400,
                        'headers': [(b'content-type', b'text/plain')],
                    })
                    await send({
                        'type': 'http.response.body',
                        'body': b'Invalid request parameters',
                    })
                    return
                
                # Prepare template variables
                template_vars = {
                    'client_name': 'claude.ai' if 'claude.ai' in redirect_uri else client_id,
                    'client_id': client_id,
                    'redirect_uri': redirect_uri,
                    'redirect_url': redirect_uri,
                    'response_type': response_type,
                    'state': state,
                    'scope': scope_param,
                    'form_action': '/oauth/authorize',
                    'error_message': '',
                    'error_class': 'hidden'
                }
                
                # Render the login page
                html = LOGIN_PAGE_TEMPLATE.format(**template_vars)
                
                await send({
                    'type': 'http.response.start',
                    'status': 200,
                    'headers': [
                        (b'content-type', b'text/html; charset=utf-8'),
                        (b'cache-control', b'no-store'),
                    ],
                })
                await send({
                    'type': 'http.response.body',
                    'body': html.encode('utf-8'),
                })
                return
            
            # Handle OAuth authorize endpoint (POST)
            if path == "/oauth/authorize" and scope["method"] == "POST":
                # Read form data
                body = b""
                while True:
                    message = await receive()
                    if message["type"] == "http.request":
                        body += message.get("body", b"")
                        if not message.get("more_body", False):
                            break
                
                # Parse form data
                form_data = urllib.parse.parse_qs(body.decode('utf-8'))
                
                # Extract form fields
                username = form_data.get('username', [''])[0]
                password = form_data.get('password', [''])[0]
                client_id = form_data.get('client_id', [''])[0]
                redirect_uri = form_data.get('redirect_uri', [''])[0]
                response_type = form_data.get('response_type', [''])[0]
                state = form_data.get('state', [''])[0]
                scope_param = form_data.get('scope', [''])[0]
                
                # Validate credentials
                if username == OAUTH_USERNAME and password == OAUTH_PASSWORD:
                    # Generate authorization code
                    auth_code = secrets.token_urlsafe(32)
                    
                    # Store auth code with metadata (expires in 10 minutes)
                    auth_codes[auth_code] = {
                        'client_id': client_id,
                        'redirect_uri': redirect_uri,
                        'expires_at': time.time() + 600,
                        'username': username,
                        'scope': scope_param
                    }
                    
                    # Redirect back to client with auth code
                    redirect_params = {'code': auth_code}
                    if state:
                        redirect_params['state'] = state
                    
                    redirect_url = redirect_uri + ('&' if '?' in redirect_uri else '?') + urllib.parse.urlencode(redirect_params)
                    
                    await send({
                        'type': 'http.response.start',
                        'status': 302,
                        'headers': [
                            (b'location', redirect_url.encode()),
                            (b'cache-control', b'no-store'),
                        ],
                    })
                    await send({
                        'type': 'http.response.body',
                        'body': b'',
                    })
                else:
                    # Invalid credentials - show error
                    template_vars = {
                        'client_name': 'claude.ai' if 'claude.ai' in redirect_uri else client_id,
                        'client_id': client_id,
                        'redirect_uri': redirect_uri,
                        'redirect_url': redirect_uri,
                        'response_type': response_type,
                        'state': state,
                        'scope': scope_param,
                        'form_action': '/oauth/authorize',
                        'error_message': 'Invalid username or password',
                        'error_class': ''
                    }
                    
                    html = LOGIN_PAGE_TEMPLATE.format(**template_vars)
                    
                    await send({
                        'type': 'http.response.start',
                        'status': 401,
                        'headers': [
                            (b'content-type', b'text/html; charset=utf-8'),
                            (b'cache-control', b'no-store'),
                        ],
                    })
                    await send({
                        'type': 'http.response.body',
                        'body': html.encode('utf-8'),
                    })
                return
            
            # Handle OAuth token endpoint
            if path == "/oauth/token" and scope["method"] == "POST":
                # Read body
                body = b""
                while True:
                    message = await receive()
                    if message["type"] == "http.request":
                        body += message.get("body", b"")
                        if not message.get("more_body", False):
                            break
                
                # Parse form data
                form_data = urllib.parse.parse_qs(body.decode('utf-8'))
                
                grant_type = form_data.get('grant_type', [''])[0]
                code = form_data.get('code', [''])[0]
                redirect_uri = form_data.get('redirect_uri', [''])[0]
                
                # Extract client credentials from Authorization header or form data
                auth_header = headers.get(b'authorization', b'').decode('utf-8')
                client_id = form_data.get('client_id', [''])[0]
                client_secret = form_data.get('client_secret', [''])[0]
                
                # Try Authorization header if not in form data
                if not client_id and not client_secret and auth_header.startswith('Basic '):
                    try:
                        credentials = base64.b64decode(auth_header[6:]).decode('utf-8')
                        client_id, client_secret = credentials.split(':', 1)
                    except:
                        pass
                
                # Handle different grant types
                if grant_type == 'client_credentials':
                    # Client Credentials Grant - direct authentication with client ID and secret
                    if not client_id or not client_secret:
                        error_response = json.dumps({'error': 'invalid_client', 'error_description': 'Client credentials required'}).encode()
                        await send({
                            'type': 'http.response.start',
                            'status': 400,
                            'headers': [
                                (b'content-type', b'application/json'),
                                (b'cache-control', b'no-store'),
                            ],
                        })
                        await send({
                            'type': 'http.response.body',
                            'body': error_response,
                        })
                        return

                    # Validate client credentials
                    if client_id != OAUTH_CLIENT_ID or client_secret != OAUTH_CLIENT_SECRET:
                        error_response = json.dumps({'error': 'invalid_client', 'error_description': 'Invalid client credentials'}).encode()
                        await send({
                            'type': 'http.response.start',
                            'status': 401,
                            'headers': [
                                (b'content-type', b'application/json'),
                                (b'cache-control', b'no-store'),
                            ],
                        })
                        await send({
                            'type': 'http.response.body',
                            'body': error_response,
                        })
                        return

                    # Generate access token and refresh token
                    access_token = secrets.token_urlsafe(64)
                    refresh_token = secrets.token_urlsafe(64)

                    # Calculate expiry times
                    access_expires_at = time.time() + 3600  # 1 hour
                    refresh_expires_at = time.time() + 2592000  # 30 days

                    # Save access token to database
                    save_token_to_db(
                        token=access_token,
                        token_type='access',
                        client_id=client_id,
                        username=None,
                        scope='mcp',
                        grant_type='client_credentials',
                        expires_at=access_expires_at
                    )

                    # Save refresh token to database
                    save_token_to_db(
                        token=refresh_token,
                        token_type='refresh',
                        client_id=client_id,
                        username=None,
                        scope='mcp',
                        grant_type='client_credentials',
                        expires_at=refresh_expires_at,
                        parent_token=access_token
                    )

                    # Create token response with refresh token
                    token_response = {
                        'access_token': access_token,
                        'token_type': 'Bearer',
                        'expires_in': 3600,
                        'refresh_token': refresh_token,
                        'scope': 'mcp'
                    }

                    response_body = json.dumps(token_response).encode()
                    await send({
                        'type': 'http.response.start',
                        'status': 200,
                        'headers': [
                            (b'content-type', b'application/json'),
                            (b'cache-control', b'no-store'),
                        ],
                    })
                    await send({
                        'type': 'http.response.body',
                        'body': response_body,
                    })
                    return

                elif grant_type == 'refresh_token':
                    # Refresh Token Grant - exchange refresh token for new access token
                    refresh_token_value = form_data.get('refresh_token', [''])[0]

                    if not refresh_token_value:
                        error_response = json.dumps({'error': 'invalid_request', 'error_description': 'refresh_token required'}).encode()
                        await send({
                            'type': 'http.response.start',
                            'status': 400,
                            'headers': [
                                (b'content-type', b'application/json'),
                                (b'cache-control', b'no-store'),
                            ],
                        })
                        await send({
                            'type': 'http.response.body',
                            'body': error_response,
                        })
                        return

                    # Validate refresh token from database
                    refresh_token_data = get_token_from_db(refresh_token_value)

                    if not refresh_token_data or refresh_token_data['token_type'] != 'refresh':
                        error_response = json.dumps({'error': 'invalid_grant', 'error_description': 'Invalid or expired refresh token'}).encode()
                        await send({
                            'type': 'http.response.start',
                            'status': 400,
                            'headers': [
                                (b'content-type', b'application/json'),
                                (b'cache-control', b'no-store'),
                            ],
                        })
                        await send({
                            'type': 'http.response.body',
                            'body': error_response,
                        })
                        return

                    # Delete old access token if exists
                    if refresh_token_data.get('parent_token'):
                        delete_token_from_db(refresh_token_data['parent_token'])

                    # Generate new access token
                    new_access_token = secrets.token_urlsafe(64)
                    access_expires_at = time.time() + 3600  # 1 hour

                    # Save new access token to database
                    save_token_to_db(
                        token=new_access_token,
                        token_type='access',
                        client_id=refresh_token_data['client_id'],
                        username=refresh_token_data.get('username'),
                        scope=refresh_token_data['scope'],
                        grant_type=refresh_token_data['grant_type'],
                        expires_at=access_expires_at
                    )

                    # Update refresh token's parent_token reference
                    db_session = get_db_session()
                    try:
                        db_token = db_session.query(OAuthToken).filter_by(token=refresh_token_value).first()
                        if db_token:
                            db_token.parent_token = new_access_token
                            db_session.commit()
                    finally:
                        db_session.close()

                    # Create token response
                    token_response = {
                        'access_token': new_access_token,
                        'token_type': 'Bearer',
                        'expires_in': 3600,
                        'refresh_token': refresh_token_value,  # Return the same refresh token
                        'scope': refresh_token_data['scope']
                    }

                    logger.info(f"Refreshed access token for client {refresh_token_data['client_id']}")

                    response_body = json.dumps(token_response).encode()
                    await send({
                        'type': 'http.response.start',
                        'status': 200,
                        'headers': [
                            (b'content-type', b'application/json'),
                            (b'cache-control', b'no-store'),
                        ],
                    })
                    await send({
                        'type': 'http.response.body',
                        'body': response_body,
                    })
                    return
                    
                elif grant_type != 'authorization_code' or not code:
                    error_response = json.dumps({'error': 'invalid_request'}).encode()
                    await send({
                        'type': 'http.response.start',
                        'status': 400,
                        'headers': [
                            (b'content-type', b'application/json'),
                            (b'cache-control', b'no-store'),
                        ],
                    })
                    await send({
                        'type': 'http.response.body',
                        'body': error_response,
                    })
                    return
                
                # Validate authorization code
                auth_data = auth_codes.get(code)
                if not auth_data or auth_data['expires_at'] < time.time():
                    error_response = json.dumps({'error': 'invalid_grant'}).encode()
                    await send({
                        'type': 'http.response.start',
                        'status': 400,
                        'headers': [
                            (b'content-type', b'application/json'),
                            (b'cache-control', b'no-store'),
                        ],
                    })
                    await send({
                        'type': 'http.response.body',
                        'body': error_response,
                    })
                    return

                # Remove used auth code
                del auth_codes[code]

                # Generate access token and refresh token
                access_token = secrets.token_urlsafe(64)
                refresh_token = secrets.token_urlsafe(64)

                # Calculate expiry times
                access_expires_at = time.time() + 3600  # 1 hour
                refresh_expires_at = time.time() + 2592000  # 30 days

                # Save access token to database
                save_token_to_db(
                    token=access_token,
                    token_type='access',
                    client_id=auth_data['client_id'],
                    username=auth_data['username'],
                    scope=auth_data.get('scope', ''),
                    grant_type='authorization_code',
                    expires_at=access_expires_at
                )

                # Save refresh token to database
                save_token_to_db(
                    token=refresh_token,
                    token_type='refresh',
                    client_id=auth_data['client_id'],
                    username=auth_data['username'],
                    scope=auth_data.get('scope', ''),
                    grant_type='authorization_code',
                    expires_at=refresh_expires_at,
                    parent_token=access_token
                )

                # Create token response with refresh token
                token_response = {
                    'access_token': access_token,
                    'token_type': 'Bearer',
                    'expires_in': 3600,
                    'refresh_token': refresh_token,
                    'scope': auth_data.get('scope', '')
                }
                
                response_body = json.dumps(token_response).encode()
                await send({
                    'type': 'http.response.start',
                    'status': 200,
                    'headers': [
                        (b'content-type', b'application/json'),
                        (b'cache-control', b'no-store'),
                    ],
                })
                await send({
                    'type': 'http.response.body',
                    'body': response_body,
                })
                return
            
            # Handle client registration endpoint
            if path == "/oauth/register" and scope["method"] == "POST":
                # For now, we'll accept any client registration
                # In production, you might want to validate and store client credentials
                
                # Read the request body
                body = b""
                while True:
                    message = await receive()
                    if message["type"] == "http.request":
                        body += message.get("body", b"")
                        if not message.get("more_body", False):
                            break
                
                try:
                    registration_data = json.loads(body.decode('utf-8')) if body else {}
                except json.JSONDecodeError:
                    registration_data = {}
                
                # Generate a client ID
                client_id = secrets.token_urlsafe(16)
                
                # Create registration response
                registration_response = {
                    "client_id": client_id,
                    "client_id_issued_at": int(time.time()),
                    "grant_types": ["authorization_code", "refresh_token"],
                    "response_types": ["code"],
                    "redirect_uris": registration_data.get("redirect_uris", []),
                    "token_endpoint_auth_method": "none"
                }
                
                response_body = json.dumps(registration_response).encode()
                await send({
                    'type': 'http.response.start',
                    'status': 201,
                    'headers': [
                        (b'content-type', b'application/json'),
                        (b'cache-control', b'no-store'),
                    ],
                })
                await send({
                    'type': 'http.response.body',
                    'body': response_body,
                })
                return
            
            # Check Bearer token for API endpoints
            auth_header = headers.get(b'authorization', b'').decode('utf-8')
            token = None
            
            if auth_header.startswith('Bearer '):
                token = auth_header[7:]
            
            # Clean up expired tokens periodically
            cleanup_expired_tokens()
            
            # Validate token for protected endpoints
            if path in ['/sse', '/messages']:
                if not token:
                    # Return 401 Unauthorized
                    await send({
                        'type': 'http.response.start',
                        'status': 401,
                        'headers': [
                            (b'content-type', b'text/plain'),
                            (b'www-authenticate', b'Bearer'),
                        ],
                    })
                    await send({
                        'type': 'http.response.body',
                        'body': b'Unauthorized',
                    })
                    return

                # Validate token from database
                token_data = get_token_from_db(token)

                if not token_data or token_data['token_type'] != 'access':
                    # Invalid or expired token
                    await send({
                        'type': 'http.response.start',
                        'status': 401,
                        'headers': [
                            (b'content-type', b'text/plain'),
                            (b'www-authenticate', b'Bearer'),
                        ],
                    })
                    await send({
                        'type': 'http.response.body',
                        'body': b'Token expired or invalid',
                    })
                    return
            
            # Handle simple login for web management interface
            if path == '/api/login' and scope["method"] == "POST":
                # Read request body
                body = b""
                while True:
                    message = await receive()
                    if message["type"] == "http.request":
                        body += message.get("body", b"")
                        if not message.get("more_body", False):
                            break
                
                try:
                    request_data = json.loads(body.decode('utf-8'))
                    username = request_data.get('username')
                    password = request_data.get('password')
                    
                    # Simple authentication check
                    if username == OAUTH_USERNAME and password == OAUTH_PASSWORD:
                        # Generate a simple token
                        token = secrets.token_urlsafe(64)

                        # Store token with expiration (24 hours) in database
                        expires_at = time.time() + 86400  # 24 hours
                        save_token_to_db(
                            token=token,
                            token_type='access',
                            client_id='web',
                            username=username,
                            scope='web',
                            grant_type='web_login',
                            expires_at=expires_at
                        )
                        
                        response_data = json.dumps({
                            'success': True,
                            'token': token,
                            'username': username
                        }).encode()
                        
                        await send({
                            'type': 'http.response.start',
                            'status': 200,
                            'headers': [
                                (b'content-type', b'application/json'),
                                (b'access-control-allow-origin', b'*'),
                            ],
                        })
                        await send({
                            'type': 'http.response.body',
                            'body': response_data,
                        })
                        return
                    else:
                        # Invalid credentials
                        response_data = json.dumps({
                            'success': False,
                            'error': 'Invalid credentials'
                        }).encode()
                        
                        await send({
                            'type': 'http.response.start',
                            'status': 401,
                            'headers': [
                                (b'content-type', b'application/json'),
                                (b'access-control-allow-origin', b'*'),
                            ],
                        })
                        await send({
                            'type': 'http.response.body',
                            'body': response_data,
                        })
                        return
                        
                except json.JSONDecodeError:
                    response_data = json.dumps({
                        'success': False,
                        'error': 'Invalid JSON'
                    }).encode()
                    
                    await send({
                        'type': 'http.response.start',
                        'status': 400,
                        'headers': [
                            (b'content-type', b'application/json'),
                            (b'access-control-allow-origin', b'*'),
                        ],
                    })
                    await send({
                        'type': 'http.response.body',
                        'body': response_data,
                    })
                    return
            
            # Handle web management interface API
            if path.startswith('/tools/call') and scope["method"] == "POST":
                # Read request body
                body = b""
                while True:
                    message = await receive()
                    if message["type"] == "http.request":
                        body += message.get("body", b"")
                        if not message.get("more_body", False):
                            break
                
                try:
                    request_data = json.loads(body.decode('utf-8'))
                    tool_name = request_data.get('name')
                    tool_args = request_data.get('arguments', {})
                    
                    # Route to appropriate MCP tool
                    result = None
                    if tool_name == 'get_ics_sync_status':
                        # For web interface, return structured data instead of formatted string
                        if not ticktick:
                            if not initialize_client():
                                result = {'error': 'Failed to initialize TickTick client'}
                            else:
                                sync_engine = ICSSyncEngine(ticktick)
                                status = sync_engine.get_sync_status(tool_args.get('source_id'))
                                result = status
                        else:
                            sync_engine = ICSSyncEngine(ticktick)
                            status = sync_engine.get_sync_status(tool_args.get('source_id'))
                            result = status
                    elif tool_name == 'add_ics_source':
                        result = await add_ics_source(
                            tool_args.get('name'),
                            tool_args.get('url'),
                            tool_args.get('project_id'),
                            tool_args.get('sync_interval', 3600)
                        )
                    elif tool_name == 'sync_ics_now':
                        result = await sync_ics_now(tool_args.get('source_id'))
                    elif tool_name == 'manage_ics_filter_rules':
                        result = await manage_ics_filter_rules(
                            tool_args.get('source_id'),
                            tool_args.get('action'),
                            tool_args.get('rule_type'),
                            tool_args.get('rule_value')
                        )
                    elif tool_name == 'get_ics_conflicts':
                        result = await get_ics_conflicts(tool_args.get('source_id'))
                    elif tool_name == 'resolve_ics_conflict':
                        result = await resolve_ics_conflict(
                            tool_args.get('conflict_id'),
                            tool_args.get('resolution')
                        )
                    elif tool_name == 'get_projects':
                        # For web interface, return raw project data
                        if not ticktick:
                            if not initialize_client():
                                result = {'error': 'Failed to initialize TickTick client'}
                            else:
                                projects = ticktick.get_projects()
                                result = projects if 'error' not in projects else {'error': projects['error']}
                        else:
                            projects = ticktick.get_projects()
                            result = projects if 'error' not in projects else {'error': projects['error']}
                    elif tool_name == 'create_project':
                        result = await create_project(
                            tool_args.get('name'),
                            tool_args.get('color', '#3498db')
                        )
                    else:
                        result = f"Unknown tool: {tool_name}"
                    
                    response_data = {"result": result}
                    response_body = json.dumps(response_data).encode()
                    
                    await send({
                        'type': 'http.response.start',
                        'status': 200,
                        'headers': [
                            (b'content-type', b'application/json'),
                            (b'access-control-allow-origin', b'*'),
                        ],
                    })
                    await send({
                        'type': 'http.response.body',
                        'body': response_body,
                    })
                    return
                    
                except Exception as e:
                    error_response = json.dumps({"error": str(e)}).encode()
                    await send({
                        'type': 'http.response.start',
                        'status': 500,
                        'headers': [
                            (b'content-type', b'application/json'),
                        ],
                    })
                    await send({
                        'type': 'http.response.body',
                        'body': error_response,
                    })
                    return

            # Handle root path for server info
            if path == '/':
                server_info = {
                    "mcp": "1.0",
                    "name": "ticktick-mcp",
                    "description": "TickTick MCP Server with OAuth authentication"
                }
                response_body = json.dumps(server_info).encode()
                await send({
                    'type': 'http.response.start',
                    'status': 200,
                    'headers': [
                        (b'content-type', b'application/json'),
                        (b'access-control-allow-origin', b'*'),
                    ],
                })
                await send({
                    'type': 'http.response.body',
                    'body': response_body,
                })
                return
            
            # Serve static files for web interface
            if path.startswith('/web/') or path == '/web':
                # Serve the React app
                import os
                web_dir = os.path.join(os.path.dirname(__file__), '..', 'web', 'dist')
                
                if path == '/web' or path == '/web/':
                    file_path = os.path.join(web_dir, 'index.html')
                else:
                    file_path = os.path.join(web_dir, path[5:])  # Remove '/web/' prefix
                
                if os.path.exists(file_path) and os.path.isfile(file_path):
                    # Determine content type
                    content_type = b'text/html'
                    if file_path.endswith('.js'):
                        content_type = b'application/javascript'
                    elif file_path.endswith('.css'):
                        content_type = b'text/css'
                    elif file_path.endswith('.json'):
                        content_type = b'application/json'
                    
                    with open(file_path, 'rb') as f:
                        file_content = f.read()
                    
                    await send({
                        'type': 'http.response.start',
                        'status': 200,
                        'headers': [
                            (b'content-type', content_type),
                            (b'cache-control', b'public, max-age=3600'),
                        ],
                    })
                    await send({
                        'type': 'http.response.body',
                        'body': file_content,
                    })
                    return
            
            # Pass to the MCP app for other paths (with SSE heartbeat wrapper)
            if path == '/sse':
                # Wrap the SSE connection with heartbeat
                await mcp_sse_with_heartbeat(mcp_app, scope, receive, send)
            else:
                await mcp_app(scope, receive, send)
        else:
            # For non-HTTP (like WebSocket), pass through
            await mcp_app(scope, receive, send)
    
    # Create Starlette app with our custom OAuth ASGI app
    app = Starlette(
        routes=[
            Mount('/', app=oauth_app),
        ]
    )
    
    # Update the log messages
    logger.info(f"OAuth discovery: http://{host}:{port}/.well-known/oauth-authorization-server")
    logger.info(f"OAuth authorize: http://{host}:{port}/oauth/authorize")
    logger.info(f"OAuth token: http://{host}:{port}/oauth/token")
    logger.info(f"SSE endpoint: http://{host}:{port}/sse (requires Bearer token)")
    logger.info("\nTo use with Claude.ai Integrations:")
    logger.info(f"  Integration URL: https://your-domain.com/sse")
    logger.info("  Claude.ai will automatically handle OAuth flow")
    logger.info("\n" + "=" * 60)
    logger.info("🔑 Login with these credentials:")
    logger.info(f"   Username: {OAUTH_USERNAME}")
    logger.info(f"   Password: {OAUTH_PASSWORD}")
    logger.info("=" * 60 + "\n")
    
    # Run with uvicorn
    uvicorn.run(app, host=host, port=port, log_level=log_level)

if __name__ == "__main__":
    run_remote_server()