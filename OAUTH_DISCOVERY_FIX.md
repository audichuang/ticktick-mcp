# OAuth Discovery Endpoint Fix

## Overview

This update fixes the OAuth discovery endpoint in `ticktick_mcp/src/remote_server.py` to properly use the actual request host instead of the internal bind address. This is crucial for Claude.ai integration and any reverse proxy scenarios.

## The Problem

Previously, the OAuth discovery endpoint at `/.well-known/oauth-authorization-server` was returning URLs based on the bind address (e.g., `http://0.0.0.0:8000`), which would not work when the server is accessed through a domain name or reverse proxy.

## The Solution

The code now:

1. **Extracts the actual host** from the `Host` header in the incoming request
2. **Checks for reverse proxy headers** (`X-Forwarded-Proto`) to determine the correct protocol
3. **Intelligently detects HTTPS** based on port 443 in the host header if no forwarded proto is provided
4. **Constructs dynamic URLs** based on the actual request, not the bind address

## Code Changes

In `ticktick_mcp/src/remote_server.py` around line 726-748:

```python
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
    "response_types_supported": ["code"],
    "grant_types_supported": ["authorization_code"],
    "code_challenge_methods_supported": ["S256"]
}
```

## Testing

A test script `test_oauth_discovery.py` has been created to verify the functionality:

```bash
# Make sure your server is running
python -m ticktick_mcp.cli remote --host 0.0.0.0 --port 8000

# In another terminal, run the test
python test_oauth_discovery.py
```

The test verifies:
1. Local requests work correctly
2. Requests with custom host headers (like from Claude.ai) return the correct URLs
3. HTTPS detection works based on port 443

## Benefits

1. **Claude.ai Integration**: When accessed through `https://ticktickmcp.audichuang.app`, the OAuth URLs will correctly use that domain
2. **Reverse Proxy Support**: Works correctly behind nginx, Apache, or other reverse proxies
3. **Flexible Deployment**: Can be deployed on any domain without code changes
4. **Backward Compatible**: Falls back to the original behavior if no host header is present

## Example Scenarios

### Direct Access
Request to: `http://localhost:8000/.well-known/oauth-authorization-server`
Returns: `"issuer": "http://localhost:8000"`

### Through Claude.ai Domain
Request to: `http://localhost:8000/.well-known/oauth-authorization-server`
With headers: `Host: ticktickmcp.audichuang.app`, `X-Forwarded-Proto: https`
Returns: `"issuer": "https://ticktickmcp.audichuang.app"`

### Behind Reverse Proxy
Request to: `http://localhost:8000/.well-known/oauth-authorization-server`
With headers: `Host: api.example.com:443`
Returns: `"issuer": "https://api.example.com:443"`