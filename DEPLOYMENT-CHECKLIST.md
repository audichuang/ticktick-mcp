# TickTick MCP Remote Server Deployment Checklist

## Pre-deployment Testing

Run these tests locally before deploying:

```bash
# 1. Test server info endpoint (Claude.ai will check this)
curl -i http://localhost:8000/{YOUR_PASSWORD}
curl -i http://localhost:8000/{YOUR_PASSWORD}/

# 2. Test SSE endpoint
curl -i http://localhost:8000/{YOUR_PASSWORD}/sse

# 3. Test with wrong password (should return 404)
curl -i http://localhost:8000/wrong-password
curl -i http://localhost:8000/wrong-password/sse
```

## Environment Variables

Create `.env` file with:
```
TICKTICK_CLIENT_ID=your_client_id
TICKTICK_CLIENT_SECRET=your_client_secret
TICKTICK_ACCESS_TOKEN=your_access_token
TICKTICK_REFRESH_TOKEN=your_refresh_token
MCP_PASSWORD=your-secure-password
```

## Docker Deployment

1. Build and push:
```bash
docker build -t yourdockerhub/ticktick-mcp:latest .
docker push yourdockerhub/ticktick-mcp:latest
```

2. Deploy with docker-compose:
```yaml
version: "3.8"
services:
  ticktick-mcp:
    image: yourdockerhub/ticktick-mcp:latest
    container_name: ticktick-mcp-server
    ports:
      - "8000:8000"
    env_file:
      - .env
    restart: unless-stopped
```

## Cloudflare Tunnel Setup

1. Create tunnel pointing to `http://localhost:8000`
2. No additional authentication needed (password is in URL)

## Claude.ai Integration

Add integration with URL:
```
https://your-domain.com/{YOUR_PASSWORD}/sse
```

## Security Notes

- Password is part of the URL path
- All endpoints require the password
- Wrong password returns 404 (looks like service doesn't exist)
- No additional authentication needed at reverse proxy level

## Endpoints Summary

| Endpoint | Purpose | Response |
|----------|---------|----------|
| `/{password}` | Server info (Claude.ai check) | JSON with server info |
| `/{password}/sse` | SSE connection | Event stream |
| `/{password}/messages` | API calls | 202 Accepted |
| `/wrong-password/*` | Any wrong password | 404 Not Found |