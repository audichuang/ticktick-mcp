# TickTick MCP Server

A [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server for TickTick that enables interacting with your TickTick task management system directly through Claude and other MCP clients.

## Features

- 📋 View all your TickTick projects and tasks
- ✏️ Create new projects and tasks through natural language
- 🔄 Update existing task details (title, content, dates, priority)
- 🔔 Set task reminders with flexible timing options
- ✅ Mark tasks as complete
- 🗑️ Delete tasks and projects
- 🔄 Full integration with TickTick's open API
- 🔌 Seamless integration with Claude and other MCP clients

## Prerequisites

- Python 3.10 or higher
- [uv](https://github.com/astral-sh/uv) - Fast Python package installer and resolver
- TickTick account with API access
- TickTick API credentials (Client ID, Client Secret, Access Token)

## Installation

### Option 1: Local Installation (Claude Desktop)

1. **Clone this repository**:
   ```bash
   git clone https://github.com/jacepark12/ticktick-mcp.git
   cd ticktick-mcp
   ```

2. **Install with uv**:
   ```bash
   # Install uv if you don't have it already
   curl -LsSf https://astral.sh/uv/install.sh | sh

   # Create a virtual environment
   uv venv

   # Activate the virtual environment
   # On macOS/Linux:
   source .venv/bin/activate
   # On Windows:
   .venv\Scripts\activate

   # Install the package
   uv pip install -e .
   ```

### Option 2: Remote Server (Claude.ai Integrations)

For running as a remote server accessible from anywhere, see [README-REMOTE.md](README-REMOTE.md). This allows you to:
- Access TickTick from any device through Claude.ai
- Run the server on your NAS or cloud server
- Use OAuth authentication for secure access

#### OAuth Server for Claude.ai

If you need OAuth authentication flow (similar to Sentry's integration), we provide a built-in OAuth server:

1. **Run the OAuth Server**:
   ```bash
   python ticktick_mcp/run_oauth_server.py --host 0.0.0.0 --port 8080
   ```

2. **Configure OAuth Credentials** in `.env`:
   ```env
   OAUTH_USERNAME=admin
   OAUTH_PASSWORD=your-secure-password-here
   ```

3. **OAuth Flow**:
   - Users are redirected to your OAuth server's login page
   - After authentication, they're redirected back to Claude.ai with an authorization code
   - Claude.ai exchanges the code for an access token

See [OAuth_README.md](OAuth_README.md) for detailed OAuth server documentation.

3. **Authenticate with TickTick**:
   ```bash
   # Run the authentication flow
   uv run -m ticktick_mcp.cli auth
   ```

   This will:
   - Ask for your TickTick Client ID and Client Secret
   - Open a browser window for you to log in to TickTick
   - Automatically save your access tokens to a `.env` file

4. **Test your configuration**:
   ```bash
   uv run test_server.py
   ```
   This will verify that your TickTick credentials are working correctly.

## Authentication with TickTick

This server uses OAuth2 to authenticate with TickTick. The setup process is straightforward:

1. Register your application at the [TickTick Developer Center](https://developer.ticktick.com/manage)
   - Set the redirect URI to `http://localhost:8000/callback`
   - Note your Client ID and Client Secret

2. Run the authentication command:
   ```bash
   uv run -m ticktick_mcp.cli auth
   ```

3. Follow the prompts to enter your Client ID and Client Secret

4. A browser window will open for you to authorize the application with your TickTick account

5. After authorizing, you'll be redirected back to the application, and your access tokens will be automatically saved to the `.env` file

The server handles token refresh automatically, so you won't need to reauthenticate unless you revoke access or delete your `.env` file.

## Authentication with Dida365

[滴答清单 - Dida365](https://dida365.com/home) is China version of TickTick, and the authentication process is similar to TickTick. Follow these steps to set up Dida365 authentication:

1. Register your application at the [Dida365 Developer Center](https://developer.dida365.com/manage)
   - Set the redirect URI to `http://localhost:8000/callback`
   - Note your Client ID and Client Secret

2. Add environment variables to your `.env` file:
   ```env
   TICKTICK_BASE_URL='https://api.dida365.com/open/v1'
   TICKTICK_AUTH_URL='https://dida365.com/oauth/authorize'
   TICKTICK_TOKEN_URL='https://dida365.com/oauth/token'
   ```

3. Follow the same authentication steps as for TickTick

## Usage with Claude for Desktop

1. Install [Claude for Desktop](https://claude.ai/download)
2. Edit your Claude for Desktop configuration file:

   **macOS**:
   ```bash
   nano ~/Library/Application\ Support/Claude/claude_desktop_config.json
   ```

   **Windows**:
   ```bash
   notepad %APPDATA%\Claude\claude_desktop_config.json
   ```

3. Add the TickTick MCP server configuration, using absolute paths:
   ```json
   {
      "mcpServers": {
         "ticktick": {
            "command": "<absolute path to uv>",
            "args": ["run", "--directory", "<absolute path to ticktick-mcp directory>", "-m", "ticktick_mcp.cli", "run"]
         }
      }
   }
   ```

4. Restart Claude for Desktop

Once connected, you'll see the TickTick MCP server tools available in Claude, indicated by the 🔨 (tools) icon.

## Available MCP Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `get_projects` | List all your TickTick projects | None |
| `get_project` | Get details about a specific project | `project_id` |
| `get_project_tasks` | List all tasks in a project | `project_id` |
| `get_task` | Get details about a specific task | `project_id`, `task_id` |
| `create_task` | Create a new task | `title`, `project_id`, `content` (optional), `start_date` (optional), `due_date` (optional), `priority` (optional), `reminders` (optional) |
| `update_task` | Update an existing task | `task_id`, `project_id`, `title` (optional), `content` (optional), `start_date` (optional), `due_date` (optional), `priority` (optional), `reminders` (optional) |
| `complete_task` | Mark a task as complete | `project_id`, `task_id` |
| `delete_task` | Delete a task | `project_id`, `task_id` |
| `create_project` | Create a new project | `name`, `color` (optional), `view_mode` (optional) |
| `delete_project` | Delete a project | `project_id` |

### Task Reminders

The TickTick MCP server supports setting reminders for tasks using the TRIGGER format. When creating or updating tasks, you can specify reminders as a list of trigger strings:

**Reminder Format Examples:**
- `"TRIGGER:PT0S"` - At the time of the event
- `"TRIGGER:PT15M"` - 15 minutes before
- `"TRIGGER:PT30M"` - 30 minutes before
- `"TRIGGER:P0DT1H0M0S"` - 1 hour before
- `"TRIGGER:P0DT2H0M0S"` - 2 hours before
- `"TRIGGER:P1DT0H0M0S"` - 1 day before
- `"TRIGGER:P7DT0H0M0S"` - 1 week before

**Multiple Reminders:**
You can set multiple reminders for a single task by providing a list:
```json
["TRIGGER:P1DT0H0M0S", "TRIGGER:P0DT1H0M0S", "TRIGGER:PT0S"]
```
This would remind you 1 day before, 1 hour before, and at the time of the event.

**Removing Reminders:**
To remove all reminders from a task, update it with an empty reminders list: `[]`

## Example Prompts for Claude

Here are some example prompts to use with Claude after connecting the TickTick MCP server:

- "Show me all my TickTick projects"
- "Create a new task called 'Finish MCP server documentation' in my work project with high priority"
- "Create a task 'Team meeting' with reminders 1 hour and 15 minutes before the due time"
- "Add a reminder 30 minutes before to my 'Doctor appointment' task"
- "List all tasks in my personal project"
- "Mark the task 'Buy groceries' as complete"
- "Create a new project called 'Vacation Planning' with a blue color"
- "When is my next deadline in TickTick?"
- "Create a task 'Submit report' due tomorrow at 5 PM with reminders 1 day before and at the time"

### Date and Time Zone Handling

The MCP server accepts dates in ISO 8601 format with timezone offset. **Important**: Always include the correct timezone offset to ensure tasks appear at the right time.

**Common timezone offsets**:
- Taiwan/China/Singapore: `+0800`
- Japan/Korea: `+0900`
- UTC: `+0000`

**Correct format examples**:
- Taiwan time 8AM: `2025-06-09T08:00:00+0800`
- Japan time 3PM: `2025-06-09T15:00:00+0900`
- UTC midnight: `2025-06-09T00:00:00+0000`

**Natural language tips**:
- Be explicit: "明天早上8點台灣時間" or "8AM Taiwan time tomorrow"
- Claude may default to UTC if timezone is unclear
- Always verify the timezone offset in the generated command

**For detailed timezone guidance, see [TIMEZONE_GUIDE.md](TIMEZONE_GUIDE.md)**

## Development

### Project Structure

```
ticktick-mcp/
├── .env.template          # Template for environment variables
├── README.md              # Project documentation
├── requirements.txt       # Project dependencies
├── setup.py               # Package setup file
├── test_server.py         # Test script for server configuration
└── ticktick_mcp/          # Main package
    ├── __init__.py        # Package initialization
    ├── authenticate.py    # OAuth authentication utility
    ├── cli.py             # Command-line interface
    └── src/               # Source code
        ├── __init__.py    # Module initialization
        ├── auth.py        # OAuth authentication implementation
        ├── server.py      # MCP server implementation
        └── ticktick_client.py  # TickTick API client
```

### Authentication Flow

The project implements a complete OAuth 2.0 flow for TickTick:

1. **Initial Setup**: User provides their TickTick API Client ID and Secret
2. **Browser Authorization**: User is redirected to TickTick to grant access
3. **Token Reception**: A local server receives the OAuth callback with the authorization code
4. **Token Exchange**: The code is exchanged for access and refresh tokens
5. **Token Storage**: Tokens are securely stored in the local `.env` file
6. **Token Refresh**: The client automatically refreshes the access token when it expires

This simplifies the user experience by handling the entire OAuth flow programmatically.

### Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
