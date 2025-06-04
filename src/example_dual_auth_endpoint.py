"""
Example: HTTP Endpoints with Dual Authentication Support

This shows how to create HTTP endpoints that work with:
1. App-only authentication (default)
2. Delegated authentication (when user token available)
3. Agent delegated authentication (for autonomous scenarios)
"""

import json
import logging
import azure.functions as func
import requests
from http_auth_helper import get_http_access_token

# Microsoft Graph API endpoint
GRAPH_API_ENDPOINT = "https://graph.microsoft.com/v1.0"


def example_get_user_info_http(req: func.HttpRequest) -> func.HttpResponse:
    """
    Example endpoint that adapts to available authentication
    
    Priority:
    1. User delegated access (if built-in auth provides token)
    2. Agent delegated access (if agent credentials configured)
    3. App-only access (fallback)
    """
    try:
        # Get token with automatic fallback
        token = get_http_access_token(req, prefer_delegated=True)
        
        if not token:
            return func.HttpResponse(
                "Authentication failed",
                status_code=401
            )
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        # Try to get user info - will work differently based on auth type
        # - Delegated: Returns info about the authenticated user
        # - App-only: Needs to specify a user ID
        
        user_id = req.params.get('userId', 'me')
        
        if user_id == 'me':
            # This only works with delegated access
            endpoint = f"{GRAPH_API_ENDPOINT}/me"
        else:
            # This works with both delegated and app-only
            endpoint = f"{GRAPH_API_ENDPOINT}/users/{user_id}"
        
        response = requests.get(
            endpoint,
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            # Add auth info to response
            data['_auth_info'] = {
                'endpoint_used': endpoint,
                'auth_available': True
            }
            
            return func.HttpResponse(
                json.dumps(data, indent=2),
                status_code=200,
                mimetype="application/json"
            )
        elif response.status_code == 400 and user_id == 'me':
            # /me doesn't work with app-only auth
            return func.HttpResponse(
                json.dumps({
                    "error": "The /me endpoint requires delegated access",
                    "suggestion": "Provide a specific userId parameter",
                    "_auth_info": {
                        "likely_auth_type": "app-only",
                        "hint": ("Enable built-in auth or use agent "
                                 "credentials for delegated access")
                    }
                }),
                status_code=400,
                mimetype="application/json"
            )
        else:
            return func.HttpResponse(
                f"Error: {response.status_code} - {response.text}",
                status_code=response.status_code
            )
            
    except Exception as e:
        logging.error(f"Error in example endpoint: {e}")
        return func.HttpResponse(
            f"Error: {str(e)}",
            status_code=500
        )


def example_send_email_http(req: func.HttpRequest) -> func.HttpResponse:
    """
    Example endpoint for sending email
    
    With delegated access: Sends as the authenticated user
    With app-only access: Must specify a sender
    """
    try:
        req_body = req.get_json()
        if not req_body:
            return func.HttpResponse(
                "Request body required",
                status_code=400
            )
        
        to_email = req_body.get('to')
        subject = req_body.get('subject')
        body = req_body.get('body')
        from_user = req_body.get('from')  # Required for app-only
        
        if not all([to_email, subject, body]):
            return func.HttpResponse(
                "Missing required fields: to, subject, body",
                status_code=400
            )
        
        # Get token - will use best available method
        token = get_http_access_token(req, prefer_delegated=True)
        
        if not token:
            return func.HttpResponse(
                "Authentication failed",
                status_code=401
            )
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        # Check if we can use /me/sendMail (delegated) or need user context
        test_response = requests.get(
            f"{GRAPH_API_ENDPOINT}/me",
            headers=headers,
            timeout=5
        )
        
        is_delegated = test_response.status_code == 200
        
        data = {
            "message": {
                "subject": subject,
                "body": {
                    "contentType": "Text",
                    "content": body
                },
                "toRecipients": [{
                    "emailAddress": {"address": to_email}
                }]
            }
        }
        
        if is_delegated:
            # Use delegated endpoint
            endpoint = f"{GRAPH_API_ENDPOINT}/me/sendMail"
            auth_type = "delegated"
        else:
            # Use app-only endpoint
            if not from_user:
                return func.HttpResponse(
                    json.dumps({
                        "error": "App-only authentication requires 'from' field",
                        "message": "Specify the sender's email or user ID"
                    }),
                    status_code=400,
                    mimetype="application/json"
                )
            
            endpoint = f"{GRAPH_API_ENDPOINT}/users/{from_user}/sendMail"
            auth_type = "app-only"
        
        response = requests.post(
            endpoint,
            headers=headers,
            json=data,
            timeout=10
        )
        
        if response.status_code == 202:
            return func.HttpResponse(
                json.dumps({
                    "status": "success",
                    "message": f"Email sent to {to_email}",
                    "_auth_info": {
                        "auth_type": auth_type,
                        "endpoint_used": endpoint
                    }
                }),
                status_code=200,
                mimetype="application/json"
            )
        else:
            return func.HttpResponse(
                f"Error: {response.status_code} - {response.text}",
                status_code=response.status_code
            )
            
    except Exception as e:
        logging.error(f"Error sending email: {e}")
        return func.HttpResponse(
            f"Error: {str(e)}",
            status_code=500
        )


def register_dual_auth_endpoints(app):
    """Register example endpoints that support both auth methods"""
    
    # User info endpoint - adapts based on auth
    app.route(route="user/info", methods=["GET"])(
        example_get_user_info_http
    )
    
    # Send email endpoint - works with both auth types
    app.route(route="email/send", methods=["POST"])(
        example_send_email_http
    )
    
    print("Dual-auth example endpoints registered!") 