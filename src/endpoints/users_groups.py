import asyncio
import json
import requests
import azure.functions as func

from endpoints.common import GRAPH_API_ENDPOINT, get_access_token, build_json_headers
from graph_metadata_manager import GraphMetadataManager


def get_user_http(req: func.HttpRequest) -> func.HttpResponse:
    """Get a specific user by id, with Redis metadata cache. Application token used."""
    try:
        user_id = req.route_params.get('user_id')
        if not user_id:
            return func.HttpResponse("Missing user_id in URL path", status_code=400)

        manager = GraphMetadataManager()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            cached_data = loop.run_until_complete(manager.get_cached_metadata("user", user_id))
            if cached_data:
                return func.HttpResponse(json.dumps(cached_data), status_code=200, mimetype="application/json")
        finally:
            loop.close()

        token = get_access_token()
        if not token:
            return func.HttpResponse("Authentication failed. Application token required.", status_code=401)

        headers = build_json_headers(token)
        response = requests.get(f"{GRAPH_API_ENDPOINT}/users/{user_id}", headers=headers, timeout=10)
        if response.status_code == 200:
            user_data = response.json()
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(manager.cache_user_metadata(user_id))
            finally:
                loop.close()
            return func.HttpResponse(json.dumps(user_data), status_code=200, mimetype="application/json")
        return func.HttpResponse(
            f"Error: {response.status_code} - {response.text}", status_code=response.status_code
        )
    except Exception as e:
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)


def list_deleted_users_http(req: func.HttpRequest) -> func.HttpResponse:
    """List deleted users. Application token used."""
    try:
        token = get_access_token()
        if not token:
            return func.HttpResponse("Authentication failed. Application token required.", status_code=401)

        headers = build_json_headers(token)
        response = requests.get(
            f"{GRAPH_API_ENDPOINT}/directory/deletedItems/microsoft.graph.user",
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


def list_group_members_http(req: func.HttpRequest) -> func.HttpResponse:
    """List group members. Application token used."""
    try:
        group_id = req.route_params.get('group_id')
        if not group_id:
            return func.HttpResponse("Missing group_id in URL path", status_code=400)

        token = get_access_token()
        if not token:
            return func.HttpResponse("Authentication failed. Application token required.", status_code=401)

        headers = build_json_headers(token)
        response = requests.get(
            f"{GRAPH_API_ENDPOINT}/groups/{group_id}/members",
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


def add_user_to_group_http(req: func.HttpRequest) -> func.HttpResponse:
    """Add a user to a group. Application token used."""
    try:
        req_body = req.get_json()
        if not req_body:
            return func.HttpResponse("Request body required", status_code=400)

        group_id = req_body.get('groupId')
        user_id = req_body.get('userId')
        if not all([group_id, user_id]):
            return func.HttpResponse("Missing required fields: groupId, userId", status_code=400)

        token = get_access_token()
        if not token:
            return func.HttpResponse("Authentication failed. Application token required.", status_code=401)

        headers = build_json_headers(token)
        data = {"@odata.id": f"{GRAPH_API_ENDPOINT}/users/{user_id}"}
        response = requests.post(
            f"{GRAPH_API_ENDPOINT}/groups/{group_id}/members/$ref",
            headers=headers,
            json=data,
            timeout=10,
        )
        if response.status_code == 204:
            return func.HttpResponse(
                f"User {user_id} added to group {group_id} successfully",
                status_code=204,
            )
        return func.HttpResponse(
            f"Error: {response.status_code} - {response.text}", status_code=response.status_code
        )
    except Exception as e:
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)


def reset_password_http(req: func.HttpRequest) -> func.HttpResponse:
    """Reset a user's password. Application token used."""
    try:
        req_body = req.get_json()
        if not req_body:
            return func.HttpResponse("Request body required", status_code=400)

        user_id = req_body.get('userId')
        temp_password = req_body.get('temporaryPassword')
        if not all([user_id, temp_password]):
            return func.HttpResponse("Missing required fields: userId, temporaryPassword", status_code=400)

        token = get_access_token()
        if not token:
            return func.HttpResponse("Authentication failed. Application token required.", status_code=401)

        headers = build_json_headers(token)
        data = {"passwordProfile": {"forceChangePasswordNextSignIn": True, "password": temp_password}}
        response = requests.patch(
            f"{GRAPH_API_ENDPOINT}/users/{user_id}", headers=headers, json=data, timeout=10
        )
        if response.status_code == 204:
            return func.HttpResponse(
                f"Password reset successfully for user {user_id}", status_code=204
            )
        return func.HttpResponse(
            f"Error: {response.status_code} - {response.text}", status_code=response.status_code
        )
    except Exception as e:
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)


