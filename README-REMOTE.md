# TickTick MCP Remote Server Setup

This guide explains how to run the TickTick MCP server as a remote service that can be accessed from anywhere through Claude.ai Integrations.

## Overview

The remote mode allows you to:
- Run the MCP server on your NAS, VPS, or any server
- Access your TickTick tasks from any device (desktop, mobile, tablet)
- Use Claude.ai's Integration feature instead of Claude Desktop
- Secure access with password protection

## Security Features

- **Password Protection**: Access is protected by a password in the URL path
- **HTTPS**: Use Cloudflare Tunnel or reverse proxy for encrypted connections
- **Environment Variables**: Sensitive credentials stored in environment variables

## Setup Instructions

### 1. Local Setup (First Time Only)

⚠️ **Important**: The authentication process requires interactive browser access, so it must be done locally first.

First, authenticate with TickTick to get your credentials:

```bash
# Install dependencies
uv sync

# Authenticate with TickTick (opens browser for OAuth)
uv run -m ticktick_mcp.cli auth
```

This will:
1. Ask for your TickTick Client ID and Secret
2. Open a browser for OAuth authorization
3. Save tokens to `.env` file

**Note**: You cannot run this authentication process inside Docker. You must complete it locally first.

### 2. Configure Environment

Create or update your `.env` file with a secure password:

```bash
# Copy the example file
cp .env.example .env

# Edit .env and set your MCP_PASSWORD
MCP_PASSWORD=your-very-secure-password-here
```

### 3. Docker Deployment

#### Option A: Using Pre-built Docker Hub Image (Easiest)

```bash
# Pull the image from Docker Hub
docker pull audichuang880208/ticktick-mcp:latest

# Run with docker-compose (using docker-compose.prod.yml)
docker-compose -f docker-compose.prod.yml up -d

# Or run directly with docker
docker run -d \
  --name ticktick-mcp \
  -p 8000:8000 \
  --env-file .env \
  audichuang880208/ticktick-mcp:latest
```

#### Option B: Build Locally

```bash
# Build and run with docker-compose
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the server
docker-compose down
```

### 4. Local Development (Without Docker)

```bash
# Run the remote server locally
uv run -m ticktick_mcp.cli remote --host 0.0.0.0 --port 8000
```

### 5. Cloudflare Tunnel Setup (Recommended for Production)

1. Install Cloudflare Tunnel on your server
2. Create a tunnel:
   ```bash
   cloudflared tunnel create ticktick-mcp
   ```
3. Configure the tunnel to point to your MCP server:
   ```yaml
   tunnel: YOUR_TUNNEL_ID
   credentials-file: /path/to/credentials.json
   
   ingress:
     - hostname: ticktick-mcp.yourdomain.com
       service: http://localhost:8000
     - service: http_status:404
   ```
4. Run the tunnel:
   ```bash
   cloudflared tunnel run ticktick-mcp
   ```

### 6. Configure Claude.ai Integration

1. Go to Claude.ai Settings > Integrations
2. Click "Add integration"
3. Enter:
   - **Name**: TickTick
   - **URL**: `https://your-domain.com/{password}/mcp/sse`
   
   Replace `{password}` with your actual MCP_PASSWORD value.
   
   Example: If your password is `my-secure-pass-123`, the URL would be:
   ```
   https://ticktick-mcp.yourdomain.com/my-secure-pass-123/mcp/sse
   ```

4. Click "Connect"

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `MCP_PASSWORD` | Password for accessing the MCP server | Yes |
| `TICKTICK_CLIENT_ID` | TickTick OAuth Client ID | Yes |
| `TICKTICK_CLIENT_SECRET` | TickTick OAuth Client Secret | Yes |
| `TICKTICK_ACCESS_TOKEN` | TickTick Access Token (auto-generated) | Yes |
| `TICKTICK_REFRESH_TOKEN` | TickTick Refresh Token (auto-generated) | Yes |
| `API_HOST` | API host (default: https://api.ticktick.com) | No |

## Security Best Practices

1. **Use a Strong Password**: Generate a long, random password for `MCP_PASSWORD`
2. **Use HTTPS**: Always use Cloudflare Tunnel or another reverse proxy with SSL
3. **Restrict Access**: Consider IP whitelisting at the firewall or Cloudflare level
4. **Regular Updates**: Keep the Docker image and dependencies updated
5. **Monitor Access**: Check logs regularly for unauthorized access attempts

## Troubleshooting

### Authentication Issues in Docker

The OAuth authentication requires browser interaction, which is not possible in Docker. You have two options:

**Option 1: Pre-authenticate locally (Recommended)**
```bash
# On your local machine
uv run -m ticktick_mcp.cli auth
# Copy the generated tokens from .env to your Docker environment
```

**Option 2: Manual token setup**
If you already have tokens, set them as environment variables:
```bash
TICKTICK_CLIENT_ID=your_client_id
TICKTICK_CLIENT_SECRET=your_client_secret
TICKTICK_ACCESS_TOKEN=your_access_token
TICKTICK_REFRESH_TOKEN=your_refresh_token
```

### Server won't start
- Check if all required environment variables are set
- Verify TickTick credentials are valid: `uv run -m ticktick_mcp.cli auth`
- Check Docker logs: `docker-compose logs`

### Can't connect from Claude.ai
- Verify the URL includes the correct password
- Check if the server is accessible: `curl https://your-domain.com/health`
- Ensure Cloudflare Tunnel is running
- Check server logs for error messages

### Authentication errors
- Re-run authentication: `uv run -m ticktick_mcp.cli auth`
- Check if tokens have expired
- Verify API_HOST matches your TickTick region

## Advanced Configuration

### Custom SSL Certificate (Without Cloudflare)

If not using Cloudflare Tunnel, you can use nginx as a reverse proxy:

```nginx
server {
    listen 443 ssl;
    server_name ticktick-mcp.yourdomain.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        
        # SSE specific headers
        proxy_set_header Cache-Control no-cache;
        proxy_set_header X-Accel-Buffering no;
        proxy_read_timeout 86400;
    }
}
```

### Multiple Users

To support multiple users, you can:
1. Run multiple containers on different ports
2. Use different passwords for each user
3. Create separate Cloudflare Tunnel routes

## Support

For issues or questions:
1. Check the [main README](README.md) for general usage
2. Open an issue on GitHub
3. Check Docker logs for detailed error messages