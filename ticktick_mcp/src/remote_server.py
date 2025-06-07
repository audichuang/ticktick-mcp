import asyncio
import os
import json
import logging
import time
import secrets
import urllib.parse
import base64
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv

from mcp.server.fastmcp import FastMCP
from .ticktick_client import TickTickClient

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# OAuth configuration
OAUTH_USERNAME = os.getenv("OAUTH_USERNAME", "admin")
OAUTH_PASSWORD = os.getenv("OAUTH_PASSWORD", "password")

# In-memory storage for OAuth
auth_codes = {}  # code -> {client_id, redirect_uri, expires_at, username}
access_tokens = {}  # token -> {username, expires_at, scope}

# Create FastMCP server
mcp = FastMCP("ticktick-remote")

# Create TickTick client
ticktick = None

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
    reminders: List[str] = None
) -> str:
    """
    Create a new task in TickTick with optional reminders.
    
    Args:
        title: Task title
        project_id: ID of the project to add the task to
        content: Task description/content (optional)
        start_date: Start date in ISO format YYYY-MM-DDThh:mm:ss+0000 (optional)
        due_date: Due date in ISO format YYYY-MM-DDThh:mm:ss+0000 (optional)
        priority: Priority level (0: None, 1: Low, 3: Medium, 5: High) (optional)
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
        
        task = ticktick.create_task(
            title=title,
            project_id=project_id,
            content=content,
            start_date=start_date,
            due_date=due_date,
            priority=priority,
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
    reminders: List[str] = None
) -> str:
    """
    Update an existing task in TickTick with optional reminders.
    
    Args:
        task_id: ID of the task to update
        project_id: ID of the project the task belongs to
        title: New task title (optional)
        content: New task description/content (optional)
        start_date: New start date in ISO format YYYY-MM-DDThh:mm:ss+0000 (optional)
        due_date: New due date in ISO format YYYY-MM-DDThh:mm:ss+0000 (optional)
        priority: New priority level (0: None, 1: Low, 3: Medium, 5: High) (optional)
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
        
        task = ticktick.update_task(
            task_id=task_id,
            project_id=project_id,
            title=title,
            content=content,
            start_date=start_date,
            due_date=due_date,
            priority=priority,
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
    """Remove expired authorization codes and access tokens."""
    current_time = time.time()
    
    # Clean up auth codes
    expired_codes = [code for code, data in auth_codes.items() if data['expires_at'] < current_time]
    for code in expired_codes:
        del auth_codes[code]
    
    # Clean up access tokens
    expired_tokens = [token for token, data in access_tokens.items() if data['expires_at'] < current_time]
    for token in expired_tokens:
        del access_tokens[token]

def run_remote_server(
    host: str = "0.0.0.0",
    port: int = 8000,
    log_level: str = "info"
):
    """Run the remote server with SSE support and OAuth authentication."""
    logger.info(f"Starting TickTick MCP Remote Server with OAuth on {host}:{port}")
    logger.info(f"OAuth username: {OAUTH_USERNAME}")
    
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
                    "grant_types_supported": ["authorization_code", "refresh_token"],
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
                
                # Extract client credentials from Authorization header
                auth_header = headers.get(b'authorization', b'').decode('utf-8')
                client_id = None
                client_secret = None
                
                if auth_header.startswith('Basic '):
                    try:
                        credentials = base64.b64decode(auth_header[6:]).decode('utf-8')
                        client_id, client_secret = credentials.split(':', 1)
                    except:
                        pass
                
                if grant_type != 'authorization_code' or not code:
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
                
                # Generate access token
                access_token = secrets.token_urlsafe(64)
                
                # Store access token
                access_tokens[access_token] = {
                    'username': auth_data['username'],
                    'expires_at': time.time() + 3600,  # 1 hour
                    'scope': auth_data.get('scope', '')
                }
                
                # Create token response
                token_response = {
                    'access_token': access_token,
                    'token_type': 'Bearer',
                    'expires_in': 3600,
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
                if not token or token not in access_tokens:
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
                
                # Check if token is expired
                token_data = access_tokens[token]
                if token_data['expires_at'] < time.time():
                    del access_tokens[token]
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
                        'body': b'Token expired',
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
            
            # Pass to the MCP app for other paths
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
    
    # Run with uvicorn
    uvicorn.run(app, host=host, port=port, log_level=log_level)

if __name__ == "__main__":
    run_remote_server()