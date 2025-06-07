#!/bin/bash

echo "Testing TickTick MCP Remote Server"
echo "=================================="

# Get session ID from SSE endpoint
echo "1. Getting session ID..."
SESSION_ID=$(curl -s --max-time 2 http://localhost:8000/sse | grep -o 'session_id=[^&]*' | cut -d= -f2)
echo "Session ID: $SESSION_ID"

# Test tools/list
echo -e "\n2. Testing tools/list..."
curl -X POST "http://localhost:8000/messages/?session_id=${SESSION_ID}" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "1",
    "method": "tools/list"
  }'
echo -e "\n"

# Test calling get_projects tool
echo "3. Testing get_projects tool..."
curl -X POST "http://localhost:8000/messages/?session_id=${SESSION_ID}" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "2",
    "method": "tools/call",
    "params": {
      "name": "get_projects",
      "arguments": {}
    }
  }'
echo -e "\n"

echo "Test completed!"