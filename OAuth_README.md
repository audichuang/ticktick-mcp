# TickTick MCP OAuth Server

This OAuth server provides a secure authentication flow for clients like Claude.ai to access the TickTick MCP server.

## Features

- **Modern Login Page**: Clean, responsive design that works on all devices
- **Secure Authentication**: Username/password authentication with environment variable configuration
- **Standard OAuth 2.0 Flow**: Implements authorization code grant type
- **Client Information Display**: Shows which application is requesting access
- **Error Handling**: Clear error messages and proper error responses

## Quick Start

1. **Configure Environment Variables**

   Copy `.env.example` to `.env` and set your OAuth credentials:
   ```bash
   OAUTH_USERNAME=admin
   OAUTH_PASSWORD=your-secure-password-here
   ```

2. **Run the OAuth Server**

   ```bash
   python ticktick_mcp/run_oauth_server.py
   ```

   Or with custom host/port:
   ```bash
   python ticktick_mcp/run_oauth_server.py --host 0.0.0.0 --port 8080
   ```

3. **Access the Server**

   The OAuth endpoints will be available at:
   - Authorization: `http://localhost:8080/oauth/authorize`
   - Token: `http://localhost:8080/oauth/token`

## OAuth Flow

1. **Client Redirect**: Claude.ai (or another OAuth client) redirects users to:
   ```
   http://your-domain.com/oauth/authorize?
     client_id=your-client-id&
     redirect_uri=https://claude.ai/callback&
     response_type=code&
     state=random-state
   ```

2. **Login Page**: Users see a login form with:
   - Client name (e.g., "claude.ai is requesting access")
   - Redirect URL for transparency
   - Username and password fields
   - Cancel and Approve buttons

3. **Authentication**: After successful login, users are redirected back to the client with an authorization code:
   ```
   https://claude.ai/callback?code=auth-code&state=random-state
   ```

4. **Token Exchange**: The client exchanges the authorization code for an access token:
   ```bash
   POST /oauth/token
   Content-Type: application/x-www-form-urlencoded
   Authorization: Basic base64(client_id:client_secret)

   grant_type=authorization_code&
   code=auth-code&
   redirect_uri=https://claude.ai/callback
   ```

## Security Considerations

- **Change Default Credentials**: Always change the default username and password in production
- **Use HTTPS**: Deploy with SSL/TLS in production environments
- **Secure Storage**: Keep your `.env` file secure and never commit it to version control
- **Token Expiration**: Authorization codes expire after 10 minutes for security

## Customization

### Styling the Login Page

The login page HTML is embedded in `oauth_server.py`. You can customize:
- Colors and branding
- Logo and icons
- Form fields and validation
- Error messages

### Adding Features

You can extend the OAuth server with:
- Multiple user support
- Database storage for codes and tokens
- Refresh token support
- Scope validation
- Client registration

## Troubleshooting

### Common Issues

1. **"Invalid username or password"**
   - Check your `.env` file has the correct `OAUTH_USERNAME` and `OAUTH_PASSWORD`
   - Ensure the `.env` file is in the correct location

2. **"Invalid grant" error**
   - The authorization code may have expired (10-minute timeout)
   - The code may have already been used

3. **Connection refused**
   - Ensure the OAuth server is running
   - Check the host and port configuration

### Debug Mode

Run with debug logging:
```bash
python ticktick_mcp/run_oauth_server.py --debug
```

## Integration with Claude Desktop

To use this OAuth server with Claude Desktop:

1. Run the OAuth server on a publicly accessible domain
2. Configure your MCP server settings to use the OAuth endpoints
3. When prompted in Claude, you'll be redirected to the login page
4. After successful authentication, you'll be returned to Claude with access

## Development

### Running Tests

Test the OAuth flow manually:

```bash
# 1. Start the server
python ticktick_mcp/run_oauth_server.py

# 2. Visit the authorization URL in a browser
# http://localhost:8080/oauth/authorize?client_id=test&redirect_uri=http://localhost:3000/callback&response_type=code

# 3. Login with your configured credentials

# 4. Exchange the code for a token
curl -X POST http://localhost:8080/oauth/token \
  -H "Authorization: Basic $(echo -n 'client_id:client_secret' | base64)" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=authorization_code&code=YOUR_CODE&redirect_uri=http://localhost:3000/callback"
```

### Docker Deployment

Create a `Dockerfile`:

```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8080

CMD ["python", "ticktick_mcp/run_oauth_server.py", "--host", "0.0.0.0", "--port", "8080"]
```

Build and run:
```bash
docker build -t ticktick-oauth .
docker run -p 8080:8080 --env-file .env ticktick-oauth
```