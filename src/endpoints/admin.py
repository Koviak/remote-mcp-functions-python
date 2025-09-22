import json
import requests
import azure.functions as func

from endpoints.common import GRAPH_API_ENDPOINT, get_access_token, build_json_headers


def list_groups_http(req: func.HttpRequest) -> func.HttpResponse:
    """List Microsoft 365 groups (Unified). Uses application token."""
    try:
        token = get_access_token()
        if not token:
            return func.HttpResponse(
                "Authentication failed. Application token required.",
                status_code=401,
            )

        headers = build_json_headers(token)
        response = requests.get(
            f"{GRAPH_API_ENDPOINT}/groups"
            "?$filter=groupTypes/any(c:c eq 'Unified')"
            "&$select=id,displayName,description,mail",
            headers=headers,
            timeout=10,
        )

        if response.status_code == 200:
            return func.HttpResponse(response.text, status_code=200, mimetype="application/json")
        return func.HttpResponse(
            f"Error: {response.status_code} - {response.text}", status_code=response.status_code
        )
    except Exception as e:
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)


def list_users_http(req: func.HttpRequest) -> func.HttpResponse:
    """List all users in the tenant. Uses application token."""
    try:
        token = get_access_token()
        if not token:
            return func.HttpResponse(
                "Authentication failed. Application token required.",
                status_code=401,
            )

        headers = build_json_headers(token)
        response = requests.get(
            f"{GRAPH_API_ENDPOINT}/users?$select=id,displayName,userPrincipalName,mail&$orderby=displayName",
            headers=headers,
            timeout=10,
        )

        if response.status_code == 200:
            return func.HttpResponse(response.text, status_code=200, mimetype="application/json")
        return func.HttpResponse(
            f"Error: {response.status_code} - {response.text}", status_code=response.status_code
        )
    except Exception as e:
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)


def list_groups_with_planner_http(req: func.HttpRequest) -> func.HttpResponse:
    """List only groups that have Planner plans. Uses application token."""
    try:
        token = get_access_token()
        if not token:
            return func.HttpResponse(
                "Authentication failed. Application token required.",
                status_code=401,
            )

        headers = build_json_headers(token)

        response = requests.get(
            f"{GRAPH_API_ENDPOINT}/groups"
            "?$filter=groupTypes/any(c:c eq 'Unified')"
            "&$select=id,displayName,description,mail",
            headers=headers,
            timeout=10,
        )
        if response.status_code != 200:
            return func.HttpResponse(
                f"Error: {response.status_code} - {response.text}", status_code=response.status_code
            )

        groups = response.json().get("value", [])
        groups_with_plans = []
        for group in groups:
            gid = group.get("id")
            plans_resp = requests.get(
                f"{GRAPH_API_ENDPOINT}/groups/{gid}/planner/plans",
                headers=headers,
                timeout=10,
            )
            if plans_resp.status_code == 200 and plans_resp.json().get("value"):
                groups_with_plans.append(group)

        return func.HttpResponse(
            json.dumps({"value": groups_with_plans}),
            status_code=200,
            mimetype="application/json",
        )
    except Exception as e:
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)


def check_group_planner_status_http(req: func.HttpRequest) -> func.HttpResponse:
    """Check if a group has Planner enabled and list plans. Uses application token."""
    try:
        group_name = req.params.get('displayName')
        if not group_name:
            return func.HttpResponse("Missing required parameter: displayName", status_code=400)

        token = get_access_token()
        if not token:
            return func.HttpResponse(
                "Authentication failed. Application token required.",
                status_code=401,
            )

        headers = build_json_headers(token)
        response = requests.get(
            f"{GRAPH_API_ENDPOINT}/groups?$filter=displayName eq '{group_name}'&$select=id,displayName",
            headers=headers,
            timeout=10,
        )
        if response.status_code != 200:
            return func.HttpResponse(
                f"Error finding group: {response.status_code} - {response.text}",
                status_code=response.status_code,
            )

        groups = response.json().get("value", [])
        if not groups:
            return func.HttpResponse(f"No group found with display name: {group_name}", status_code=404)

        group = groups[0]
        result = {
            "groupId": group["id"],
            "displayName": group["displayName"],
        }

        plans_response = requests.get(
            f"{GRAPH_API_ENDPOINT}/groups/{group['id']}/planner/plans",
            headers=headers,
            timeout=10,
        )
        if plans_response.status_code == 200:
            plans = plans_response.json().get("value", [])
            result["plans"] = [{"id": p.get("id"), "title": p.get("title")} for p in plans]
            result["planCount"] = len(plans)
        else:
            result["plansError"] = f"{plans_response.status_code} - {plans_response.text}"

        return func.HttpResponse(json.dumps(result), status_code=200, mimetype="application/json")
    except Exception as e:
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)


