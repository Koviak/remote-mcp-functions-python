# Example: Converting MCP tools to HTTP endpoints
# Add these to your function_app.py if you want direct HTTP access

import azure.functions as func

# HTTP endpoint version of list_groups
@app.route(route="list_groups", methods=["GET"])
def list_groups_http(req: func.HttpRequest) -> func.HttpResponse:
    try:
        token = get_access_token()
        if not token:
            return func.HttpResponse(
                "Authentication failed",
                status_code=401
            )
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(
            f"{GRAPH_API_ENDPOINT}/groups"
            "?$filter=groupTypes/any(c:c eq 'Unified')"
            "&$select=id,displayName,description,mail",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            return func.HttpResponse(
                response.text,
                status_code=200,
                mimetype="application/json"
            )
        else:
            return func.HttpResponse(
                f"Error: {response.status_code}",
                status_code=response.status_code
            )
            
    except Exception as e:
        return func.HttpResponse(
            f"Error: {str(e)}",
            status_code=500
        )

# HTTP endpoint version of create_plan
@app.route(route="create_plan", methods=["POST"])
def create_plan_http(req: func.HttpRequest) -> func.HttpResponse:
    try:
        req_body = req.get_json()
        title = req_body.get('title')
        group_id = req_body.get('groupId')
        
        if not title or not group_id:
            return func.HttpResponse(
                "Missing title or groupId",
                status_code=400
            )
        
        token = get_access_token()
        if not token:
            return func.HttpResponse(
                "Authentication failed",
                status_code=401
            )
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        data = {
            "owner": group_id,
            "title": title
        }
        
        response = requests.post(
            f"{GRAPH_API_ENDPOINT}/planner/plans",
            headers=headers,
            json=data,
            timeout=10
        )
        
        if response.status_code == 201:
            return func.HttpResponse(
                response.text,
                status_code=201,
                mimetype="application/json"
            )
        else:
            return func.HttpResponse(
                f"Error: {response.status_code}",
                status_code=response.status_code
            )
            
    except Exception as e:
        return func.HttpResponse(
            f"Error: {str(e)}",
            status_code=500
        )

# Then you could call:
# GET  http://localhost:7071/api/list_groups
# POST http://localhost:7071/api/create_plan
#      Body: {"title": "My Plan", "groupId": "group-id-here"} 