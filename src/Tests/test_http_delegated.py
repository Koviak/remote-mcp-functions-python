"""
Test HTTP endpoint to demonstrate delegated access (OBO)

This creates a simple HTTP endpoint that shows how to use delegated access.
To fully test this, you would need to deploy to Azure with built-in auth enabled.
"""

import logging
import azure.functions as func
from azure.identity import OnBehalfOfCredential
import os

# Create a test function app for demonstration
test_app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


@test_app.route(route="test-delegated-access", methods=["GET"])
def test_delegated_access_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint that demonstrates delegated access pattern"""
    
    logging.info("Testing delegated access in HTTP endpoint")
    
    # In a real deployment with built-in auth enabled, 
    # the user token would be in this header
    user_token = req.headers.get('X-MS-TOKEN-AAD-ACCESS-TOKEN')
    
    if not user_token:
        # This is expected in local development
        return func.HttpResponse(
            body="""
            <h2>Delegated Access Test</h2>
            <p><strong>Local Development Mode</strong></p>
            <p>✗ No user token found (expected in local development)</p>
            
            <h3>To use delegated access:</h3>
            <ol>
                <li>Deploy this function to Azure</li>
                <li>Enable built-in authentication (Azure AD)</li>
                <li>Access the function through the authenticated endpoint</li>
                <li>Azure will provide the user token in X-MS-TOKEN-AAD-ACCESS-TOKEN header</li>
            </ol>
            
            <h3>Current Configuration:</h3>
            <ul>
                <li>AZURE_CLIENT_ID: {}</li>
                <li>AZURE_TENANT_ID: {}</li>
                <li>DOWNSTREAM_API_SCOPE: {}</li>
            </ul>
            
            <p><strong>Note:</strong> MCP triggers cannot access these headers, 
            only HTTP triggers can use delegated access.</p>
            """.format(
                '✓ Set' if os.getenv('AZURE_CLIENT_ID') else '✗ Not set',
                '✓ Set' if os.getenv('AZURE_TENANT_ID') else '✗ Not set',
                os.getenv('DOWNSTREAM_API_SCOPE', 'Not set')
            ),
            mimetype="text/html",
            status_code=200
        )
    
    # This code would execute in production with built-in auth
    try:
        # Exchange user token for downstream API token
        credential = OnBehalfOfCredential(
            tenant_id=os.getenv("AZURE_TENANT_ID"),
            client_id=os.getenv("AZURE_CLIENT_ID"),
            client_secret=os.getenv("AZURE_CLIENT_SECRET"),
            user_assertion=user_token
        )
        
        # Get token for downstream API
        scope = os.getenv("DOWNSTREAM_API_SCOPE", "https://graph.microsoft.com/.default")
        token = credential.get_token(scope)
        
        return func.HttpResponse(
            body=f"""
            <h2>Delegated Access Success!</h2>
            <p>✓ Successfully exchanged user token for downstream API token</p>
            <p>Token expires at: {token.expires_on}</p>
            <p>Scope: {scope}</p>
            """,
            mimetype="text/html",
            status_code=200
        )
        
    except Exception as e:
        return func.HttpResponse(
            body=f"""
            <h2>Delegated Access Error</h2>
            <p>✗ Failed to exchange token: {str(e)}</p>
            """,
            mimetype="text/html",
            status_code=500
        )


if __name__ == "__main__":
    print("Test HTTP Endpoint for Delegated Access")
    print("=" * 50)
    print("\nThis demonstrates how delegated access works with HTTP triggers.")
    print("To test locally, the function app would need to be running.")
    print("\nIn production:")
    print("1. Deploy to Azure")
    print("2. Enable built-in authentication") 
    print("3. Access through authenticated endpoint")
    print("\nEndpoint: /api/test-delegated-access") 