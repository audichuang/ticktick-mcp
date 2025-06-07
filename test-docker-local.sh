#!/bin/bash
set -e

echo "🧪 Testing TickTick MCP Docker image locally"
echo ""

# Configuration
IMAGE_NAME="ticktick-mcp:latest"
CONTAINER_NAME="ticktick-mcp-test"
TEST_PASSWORD="test-password-123"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

# Step 1: Build the image
echo "📦 Building Docker image..."
docker build -t ${IMAGE_NAME} .

# Step 2: Check if .env file exists
if [ ! -f ".env" ]; then
    echo "⚠️  No .env file found. Creating a test .env file..."
    echo "# Test environment file" > .env
    echo "MCP_PASSWORD=${TEST_PASSWORD}" >> .env
    echo "TICKTICK_CLIENT_ID=test-client-id" >> .env
    echo "TICKTICK_CLIENT_SECRET=test-client-secret" >> .env
    echo "TICKTICK_ACCESS_TOKEN=" >> .env
    echo "TICKTICK_REFRESH_TOKEN=" >> .env
    echo ""
    echo "⚠️  Note: You'll need to run 'uv run -m ticktick_mcp.cli auth' first to get real tokens"
fi

# Step 3: Stop and remove existing test container if exists
echo "🧹 Cleaning up existing test container..."
docker stop ${CONTAINER_NAME} 2>/dev/null || true
docker rm ${CONTAINER_NAME} 2>/dev/null || true

# Step 4: Run the container
echo "🚀 Starting test container..."
docker run -d \
    --name ${CONTAINER_NAME} \
    -p 8000:8000 \
    --env-file .env \
    ${IMAGE_NAME}

# Wait for container to start
echo "⏳ Waiting for container to start..."
sleep 5

# Step 5: Check if container is running
if docker ps | grep -q ${CONTAINER_NAME}; then
    echo "✅ Container is running!"
    echo ""
    
    # Show logs
    echo "📋 Container logs:"
    docker logs ${CONTAINER_NAME}
    echo ""
    
    # Show the SSE endpoint
    echo "🌐 SSE endpoint should be available at:"
    echo "   http://localhost:8000/${TEST_PASSWORD}/mcp/sse"
    echo ""
    
    # Test with curl
    echo "🔍 Testing SSE endpoint with curl..."
    curl -s -N -m 5 "http://localhost:8000/${TEST_PASSWORD}/mcp/sse" || echo "Note: SSE connection test completed"
    
    echo ""
    echo "✅ Test completed!"
    echo ""
    echo "📝 Next steps:"
    echo "1. Check the logs: docker logs -f ${CONTAINER_NAME}"
    echo "2. Stop the test: docker stop ${CONTAINER_NAME}"
    echo "3. Remove container: docker rm ${CONTAINER_NAME}"
else
    echo "❌ Container failed to start!"
    echo "Checking logs..."
    docker logs ${CONTAINER_NAME}
    exit 1
fi