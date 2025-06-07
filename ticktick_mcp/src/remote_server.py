import asyncio
import os
import json
import logging
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

# Get password from environment
MCP_PASSWORD = os.getenv("MCP_PASSWORD", "default-password-change-me")
if MCP_PASSWORD == "default-password-change-me":
    logger.warning("Using default password! Please set MCP_PASSWORD environment variable.")

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
    priority: int = 0
) -> str:
    """
    Create a new task in TickTick.
    
    Args:
        title: Task title
        project_id: ID of the project to add the task to
        content: Task description/content (optional)
        start_date: Start date in ISO format YYYY-MM-DDThh:mm:ss+0000 (optional)
        due_date: Due date in ISO format YYYY-MM-DDThh:mm:ss+0000 (optional)
        priority: Priority level (0: None, 1: Low, 3: Medium, 5: High) (optional)
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
        
        task = ticktick.create_task(
            title=title,
            project_id=project_id,
            content=content,
            start_date=start_date,
            due_date=due_date,
            priority=priority
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
    priority: int = None
) -> str:
    """
    Update an existing task in TickTick.
    
    Args:
        task_id: ID of the task to update
        project_id: ID of the project the task belongs to
        title: New task title (optional)
        content: New task description/content (optional)
        start_date: New start date in ISO format YYYY-MM-DDThh:mm:ss+0000 (optional)
        due_date: New due date in ISO format YYYY-MM-DDThh:mm:ss+0000 (optional)
        priority: New priority level (0: None, 1: Low, 3: Medium, 5: High) (optional)
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
        
        task = ticktick.update_task(
            task_id=task_id,
            project_id=project_id,
            title=title,
            content=content,
            start_date=start_date,
            due_date=due_date,
            priority=priority
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

def run_remote_server(
    host: str = "0.0.0.0",
    port: int = 8000,
    log_level: str = "info"
):
    """Run the remote server with SSE support and password protection."""
    # For now, we'll use the standard SSE path without password in URL
    # Password protection should be handled by reverse proxy or API gateway
    logger.info(f"Starting TickTick MCP Remote Server on {host}:{port}")
    logger.info(f"Current MCP_PASSWORD: {MCP_PASSWORD[:4]}..." if len(MCP_PASSWORD) > 4 else "No password set!")
    
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
    
    # Create a custom ASGI app with password protection
    mcp_app = mcp.sse_app()
    base_url = f"http://{host}:{port}"
    
    async def password_protected_app(scope, receive, send):
        """ASGI app that checks password in URL path"""
        if scope["type"] == "http":
            path = scope["path"]
            
            # Handle OAuth discovery endpoints
            # These endpoints indicate OAuth is not supported/required
            if path == "/.well-known/oauth-authorization-server":
                # Return 404 to indicate OAuth is not supported
                await send({
                    'type': 'http.response.start',
                    'status': 404,
                    'headers': [(b'content-type', b'text/plain')],
                })
                await send({
                    'type': 'http.response.body',
                    'body': b'Not Found',
                })
                return
            
            # Handle client registration endpoint
            if path == "/register":
                # Return 404 to indicate registration is not supported
                await send({
                    'type': 'http.response.start',
                    'status': 404,
                    'headers': [(b'content-type', b'text/plain')],
                })
                await send({
                    'type': 'http.response.body',
                    'body': b'Not Found',
                })
                return
            
            # Split path while preserving structure
            path_parts = path.strip('/').split('/') if path.strip('/') else []
            
            # Check if path matches /{password} or /{password}/sse or /{password}/messages
            if len(path_parts) >= 1:
                url_password = path_parts[0]
                # Reconstruct the actual path, preserving trailing slash and query parameters
                remaining_parts = path_parts[1:]
                if remaining_parts:
                    actual_path = '/' + '/'.join(remaining_parts)
                    # Preserve trailing slash if original had it
                    if path.endswith('/') and not actual_path.endswith('/'):
                        actual_path += '/'
                else:
                    actual_path = '/'
                
                # Verify password
                if url_password == MCP_PASSWORD:
                    # Rewrite the path to remove password
                    new_scope = scope.copy()
                    new_scope['path'] = actual_path
                    if 'raw_path' in scope:
                        new_scope['raw_path'] = actual_path.encode()
                    
                    # For SSE endpoint, we need to intercept and modify the response
                    if actual_path == '/sse':
                        # Create a custom send that modifies the SSE data
                        messages_sent = []
                        
                        async def modified_send(message):
                            if message['type'] == 'http.response.body':
                                body = message.get('body', b'')
                                if body and b'data: /messages/' in body:
                                    # Modify the messages URL to include password
                                    body = body.replace(
                                        b'data: /messages/',
                                        f'data: /{MCP_PASSWORD}/messages/'.encode()
                                    )
                                    message = message.copy()
                                    message['body'] = body
                            
                            await send(message)
                        
                        # Pass to the MCP app with modified send
                        await mcp_app(new_scope, receive, modified_send)
                        return
                    
                    # Handle root path for server info/health check
                    if actual_path == '/' or actual_path == '':
                        # Return server info for Claude.ai integration check
                        await send({
                            'type': 'http.response.start',
                            'status': 200,
                            'headers': [
                                (b'content-type', b'application/json'),
                                (b'access-control-allow-origin', b'*'),
                            ],
                        })
                        server_info = {
                            "mcp": "1.0",
                            "name": "ticktick-mcp",
                            "description": "TickTick MCP Server with password protection"
                        }
                        await send({
                            'type': 'http.response.body',
                            'body': json.dumps(server_info).encode(),
                        })
                        return
                    
                    # Pass to the MCP app with rewritten path
                    await mcp_app(new_scope, receive, send)
                    return
            
            # Return 404 if password is wrong or missing
            await send({
                'type': 'http.response.start',
                'status': 404,
                'headers': [(b'content-type', b'text/plain')],
            })
            await send({
                'type': 'http.response.body',
                'body': b'Not Found',
            })
        else:
            # For non-HTTP (like WebSocket), pass through
            await mcp_app(scope, receive, send)
    
    # Create Starlette app with our custom ASGI app
    app = Starlette(
        routes=[
            Mount('/', app=password_protected_app),
        ]
    )
    
    # Update the log messages
    logger.info(f"SSE endpoint will be available at: http://{host}:{port}/{MCP_PASSWORD}/sse")
    logger.info(f"Messages endpoint: http://{host}:{port}/{MCP_PASSWORD}/messages")
    logger.info("To use with Claude.ai Integrations:")
    logger.info(f"  Integration URL: https://your-domain.com/{MCP_PASSWORD}/sse")
    
    # Run with uvicorn
    uvicorn.run(app, host=host, port=port, log_level=log_level)

if __name__ == "__main__":
    run_remote_server()