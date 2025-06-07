#!/bin/bash
set -e

echo "🧪 Testing TickTick MCP Docker fix"
echo ""

# Clean up any existing containers
echo "🧹 Cleaning up..."
docker stop ticktick-mcp-server 2>/dev/null || true
docker rm ticktick-mcp-server 2>/dev/null || true

# Build the image
echo "📦 Building Docker image..."
docker build -t ticktick-mcp:test .

# Create a test .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "📝 Creating test .env file..."
    cat > .env << EOF
# Test credentials
MCP_PASSWORD=test-password-123
TICKTICK_CLIENT_ID=test-client-id
TICKTICK_CLIENT_SECRET=test-client-secret
TICKTICK_ACCESS_TOKEN=test-token
TICKTICK_REFRESH_TOKEN=test-refresh
EOF
fi

# Run the container
echo "🚀 Starting container..."
docker run -d \
    --name ticktick-mcp-server \
    -p 8000:8000 \
    --env-file .env \
    ticktick-mcp:test

# Wait for startup
echo "⏳ Waiting for server to start..."
sleep 5

# Check logs
echo "📋 Container logs:"
docker logs ticktick-mcp-server

# Check if running
if docker ps | grep -q ticktick-mcp-server; then
    echo ""
    echo "✅ Container is running!"
    echo "🌐 SSE endpoint: http://localhost:8000/test-password-123/mcp/sse"
else
    echo ""
    echo "❌ Container failed to start"
    exit 1
fi