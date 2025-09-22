import json
import requests
import azure.functions as func

from endpoints.common import (
    GRAPH_API_ENDPOINT,
    _get_token_and_base_for_me,
    build_json_headers,
)


def list_calendars_http(req: func.HttpRequest) -> func.HttpResponse:
    """List calendars for the signed-in user. Delegated token required."""
    try:
        token, base = _get_token_and_base_for_me("Calendars.ReadWrite.Shared")
        if not token or not base:
            return func.HttpResponse(
                "Authentication failed. Delegated token required for calendars.",
                status_code=401,
            )
        headers = build_json_headers(token)
        response = requests.get(f"{GRAPH_API_ENDPOINT}{base}/calendars", headers=headers, timeout=10)
        if response.status_code == 200:
            return func.HttpResponse(response.text, status_code=200, mimetype="application/json")
        return func.HttpResponse(
            f"Error: {response.status_code} - {response.text}", status_code=response.status_code
        )
    except Exception as e:
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)


def create_calendar_http(req: func.HttpRequest) -> func.HttpResponse:
    """Create a calendar for the signed-in user. Delegated token required."""
    try:
        req_body = req.get_json()
        if not req_body:
            return func.HttpResponse("Request body required", status_code=400)
        name = req_body.get('name')
        if not name:
            return func.HttpResponse("Missing required field: name", status_code=400)

        token, base = _get_token_and_base_for_me("Calendars.ReadWrite")
        if not token or not base:
            return func.HttpResponse(
                "Authentication failed. Delegated token required for calendar.",
                status_code=401,
            )

        headers = build_json_headers(token)
        data = {"name": name}
        color = req_body.get('color')
        if color:
            data['color'] = color
        response = requests.post(
            f"{GRAPH_API_ENDPOINT}{base}/calendars",
            headers=headers,
            json=data,
            timeout=10,
        )
        if response.status_code == 201:
            return func.HttpResponse(response.text, status_code=201, mimetype="application/json")
        return func.HttpResponse(
            f"Error: {response.status_code} - {response.text}", status_code=response.status_code
        )
    except Exception as e:
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)


def get_calendar_view_http(req: func.HttpRequest) -> func.HttpResponse:
    """Get calendar view for a time range. Delegated token required."""
    try:
        start_date = req.params.get('startDateTime')
        end_date = req.params.get('endDateTime')
        if not start_date or not end_date:
            return func.HttpResponse(
                "Missing required parameters: startDateTime, endDateTime",
                status_code=400,
            )

        token, base = _get_token_and_base_for_me("Calendars.ReadWrite")
        if not token or not base:
            return func.HttpResponse(
                json.dumps({
                    "error": "auth_unavailable",
                    "message": "Delegated token missing and app-only fallback not configured",
                }),
                status_code=503,
                mimetype="application/json",
            )

        headers = build_json_headers(token)
        url = f"{GRAPH_API_ENDPOINT}{base}/calendar/calendarView"
        response = requests.get(
            url,
            params={"startDateTime": start_date, "endDateTime": end_date},
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


def get_event_http(req: func.HttpRequest) -> func.HttpResponse:
    """Get a specific event by id. Delegated token required."""
    try:
        event_id = req.route_params.get('event_id')
        if not event_id:
            return func.HttpResponse("Missing event_id in URL path", status_code=400)

        token, base = _get_token_and_base_for_me("Calendars.ReadWrite.Shared")
        if not token or not base:
            return func.HttpResponse(
                "Authentication failed. Delegated token required for calendar.",
                status_code=401,
            )
        headers = build_json_headers(token)
        response = requests.get(
            f"{GRAPH_API_ENDPOINT}{base}/events/{event_id}", headers=headers, timeout=10
        )
        if response.status_code == 200:
            return func.HttpResponse(response.text, status_code=200, mimetype="application/json")
        return func.HttpResponse(
            f"Error: {response.status_code} - {response.text}", status_code=response.status_code
        )
    except Exception as e:
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)


def update_event_http(req: func.HttpRequest) -> func.HttpResponse:
    """Update an event. Delegated token required."""
    try:
        event_id = req.route_params.get('event_id')
        if not event_id:
            return func.HttpResponse("Missing event_id in URL path", status_code=400)

        req_body = req.get_json()
        if not req_body:
            return func.HttpResponse("Request body required", status_code=400)

        token, base = _get_token_and_base_for_me("Calendars.ReadWrite")
        if not token or not base:
            return func.HttpResponse(
                "Authentication failed. Delegated token required for calendar.",
                status_code=401,
            )

        headers = build_json_headers(token)
        data = {}
        for key in ("subject", "start", "end", "body", "location"):
            if key in req_body:
                data[key] = req_body[key]
        response = requests.patch(
            f"{GRAPH_API_ENDPOINT}{base}/events/{event_id}",
            headers=headers,
            json=data,
            timeout=10,
        )
        if response.status_code == 200:
            return func.HttpResponse(response.text, status_code=200, mimetype="application/json")
        return func.HttpResponse(
            f"Error: {response.status_code} - {response.text}", status_code=response.status_code
        )
    except Exception as e:
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)


def delete_event_http(req: func.HttpRequest) -> func.HttpResponse:
    """Delete an event. Delegated token required."""
    try:
        event_id = req.route_params.get('event_id')
        if not event_id:
            return func.HttpResponse("Missing event_id in URL path", status_code=400)

        token, base = _get_token_and_base_for_me("Calendars.ReadWrite")
        if not token or not base:
            return func.HttpResponse(
                "Authentication failed. Delegated token required for calendar.",
                status_code=401,
            )
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.delete(
            f"{GRAPH_API_ENDPOINT}{base}/events/{event_id}", headers=headers, timeout=10
        )
        if response.status_code == 204:
            return func.HttpResponse("Event deleted successfully", status_code=204)
        return func.HttpResponse(
            f"Error: {response.status_code} - {response.text}", status_code=response.status_code
        )
    except Exception as e:
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)


def accept_event_http(req: func.HttpRequest) -> func.HttpResponse:
    """Accept an event invitation. Delegated token required."""
    try:
        event_id = req.route_params.get('event_id')
        if not event_id:
            return func.HttpResponse("Missing event_id in URL path", status_code=400)

        req_body = req.get_json()
        comment = req_body.get('comment', '') if req_body else ''
        send_response = (req_body.get('sendResponse', True) if req_body else True)

        token, base = _get_token_and_base_for_me("Calendars.ReadWrite")
        if not token or not base:
            return func.HttpResponse(
                "Authentication failed. Delegated token required for calendar.",
                status_code=401,
            )
        headers = build_json_headers(token)
        data = {"comment": comment, "sendResponse": send_response}
        response = requests.post(
            f"{GRAPH_API_ENDPOINT}{base}/events/{event_id}/accept",
            headers=headers,
            json=data,
            timeout=10,
        )
        if response.status_code == 202:
            return func.HttpResponse("Event accepted successfully", status_code=202)
        return func.HttpResponse(
            f"Error: {response.status_code} - {response.text}", status_code=response.status_code
        )
    except Exception as e:
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)


def decline_event_http(req: func.HttpRequest) -> func.HttpResponse:
    """Decline an event invitation. Delegated token required."""
    try:
        event_id = req.route_params.get('event_id')
        if not event_id:
            return func.HttpResponse("Missing event_id in URL path", status_code=400)

        req_body = req.get_json()
        comment = req_body.get('comment', '') if req_body else ''
        send_response = (req_body.get('sendResponse', True) if req_body else True)

        token, base = _get_token_and_base_for_me("Calendars.ReadWrite")
        if not token or not base:
            return func.HttpResponse(
                "Authentication failed. Delegated token required for calendar.",
                status_code=401,
            )
        headers = build_json_headers(token)
        data = {"comment": comment, "sendResponse": send_response}
        response = requests.post(
            f"{GRAPH_API_ENDPOINT}{base}/events/{event_id}/decline",
            headers=headers,
            json=data,
            timeout=10,
        )
        if response.status_code == 202:
            return func.HttpResponse("Event declined successfully", status_code=202)
        return func.HttpResponse(
            f"Error: {response.status_code} - {response.text}", status_code=response.status_code
        )
    except Exception as e:
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)


def find_meeting_times_http(req: func.HttpRequest) -> func.HttpResponse:
    """Find meeting times. Delegated token required."""
    try:
        req_body = req.get_json()
        if not req_body:
            return func.HttpResponse("Request body required", status_code=400)

        attendees = req_body.get('attendees', [])
        time_constraint = req_body.get('timeConstraint')
        meeting_duration = req_body.get('meetingDuration', 'PT1H')

        token, base = _get_token_and_base_for_me("Calendars.ReadWrite.Shared")
        if not token or not base:
            return func.HttpResponse(
                "Authentication failed. Delegated token required for calendar.",
                status_code=401,
            )

        headers = build_json_headers(token)
        data = {
            "attendees": [{"emailAddress": {"address": email}} for email in attendees],
            "meetingDuration": meeting_duration,
        }
        if time_constraint:
            data['timeConstraint'] = time_constraint

        response = requests.post(
            f"{GRAPH_API_ENDPOINT}{base}/findMeetingTimes",
            headers=headers,
            json=data,
            timeout=10,
        )
        if response.status_code == 200:
            return func.HttpResponse(response.text, status_code=200, mimetype="application/json")
        return func.HttpResponse(
            f"Error: {response.status_code} - {response.text}", status_code=response.status_code
        )
    except Exception as e:
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)


def create_event_http(req: func.HttpRequest) -> func.HttpResponse:
    """Create calendar event. Delegated token required."""
    try:
        req_body = req.get_json()
        if not req_body:
            return func.HttpResponse("Request body required", status_code=400)

        subject = req_body.get('subject')
        start_time = req_body.get('start')
        end_time = req_body.get('end')
        attendees_str = req_body.get('attendees', '')
        if not all([subject, start_time, end_time]):
            return func.HttpResponse("Missing required fields: subject, start, end", status_code=400)

        token, base = _get_token_and_base_for_me("Calendars.ReadWrite")
        if not token or not base:
            return func.HttpResponse(
                "Authentication failed. Delegated token required for calendar.",
                status_code=401,
            )
        headers = build_json_headers(token)
        data = {
            "subject": subject,
            "start": {"dateTime": start_time, "timeZone": "UTC"},
            "end": {"dateTime": end_time, "timeZone": "UTC"},
        }
        if attendees_str:
            attendees = []
            for email in attendees_str.split(","):
                email = email.strip()
                if email:
                    attendees.append({"emailAddress": {"address": email}})
            data["attendees"] = attendees

        response = requests.post(
            f"{GRAPH_API_ENDPOINT}{base}/events",
            headers=headers,
            json=data,
            timeout=10,
        )
        if response.status_code == 201:
            event = response.json()
            return func.HttpResponse(
                json.dumps({"id": event.get("id"), "message": "Event created successfully"}),
                status_code=201,
                mimetype="application/json",
            )
        return func.HttpResponse(
            f"Error: {response.status_code} - {response.text}", status_code=response.status_code
        )
    except Exception as e:
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)


def list_upcoming_http(req: func.HttpRequest) -> func.HttpResponse:
    """List upcoming events. Delegated token required."""
    try:
        token, base = _get_token_and_base_for_me("Calendars.ReadWrite.Shared")
        if not token or not base:
            return func.HttpResponse(
                json.dumps({"status": "unavailable", "reason": "delegated token missing"}),
                status_code=503,
                mimetype="application/json",
            )
        headers = build_json_headers(token)
        response = requests.get(
            f"{GRAPH_API_ENDPOINT}{base}/events"
            "?$select=id,subject,start,end,attendees&$top=20&$orderby=start/dateTime",
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


