# Comprehensive HTTP Endpoints for Microsoft Graph API

This document provides a complete list of all HTTP endpoints implemented in the `http_endpoints.py` file for interacting with Microsoft Graph API. These endpoints enable agents to fully manage email, calendar events, and task management in Microsoft 365.

## Authentication
All endpoints use OAuth 2.0 authentication via the `get_access_token()` function which supports both app-only and delegated access.

## Total Endpoints: 69

## Mail Endpoints (16 endpoints)

### Core Mail Operations
1. **List Inbox Messages** - `GET /me/messages`
2. **Get Specific Message** - `GET /me/messages/{message_id}`
3. **Create Draft Message** - `POST /me/messages`
4. **Send Email** - `POST /me/sendMail`
5. **Send Draft Message** - `POST /me/messages/{message_id}/send`
6. **Delete Message** - `DELETE /me/messages/{message_id}`

### Message Actions
7. **Move Message** - `POST /me/messages/{message_id}/move`
8. **Copy Message** - `POST /me/messages/{message_id}/copy`
9. **Reply to Message** - `POST /me/messages/{message_id}/reply`
10. **Reply All** - `POST /me/messages/{message_id}/replyAll`
11. **Forward Message** - `POST /me/messages/{message_id}/forward`

### Mail Folders
12. **List Mail Folders** - `GET /me/mailFolders`
13. **Create Mail Folder** - `POST /me/mailFolders`

### Mail Attachments
14. **List Attachments** - `GET /me/messages/{message_id}/attachments`
15. **Add Attachment** - `POST /me/messages/{message_id}/attachments`

### Additional Mail Features
16. **Sites Search** - `GET /sites?query={query}`

## Calendar Endpoints (9 endpoints)

### Calendar Management
1. **List Calendars** - `GET /me/calendars`
2. **Create Calendar** - `POST /me/calendars`
3. **Get Calendar View** - `GET /me/calendar/calendarView`

### Event Management
4. **Create Event** - `POST /me/events`
5. **Get Event** - `GET /me/events/{event_id}`
6. **Update Event** - `PATCH /me/events/{event_id}`
7. **Delete Event** - `DELETE /me/events/{event_id}`
8. **List Upcoming Events** - `GET /me/events/upcoming`

### Event Actions
9. **Accept Event** - `POST /me/events/{event_id}/accept`
10. **Decline Event** - `POST /me/events/{event_id}/decline`
11. **Find Meeting Times** - `POST /me/findMeetingTimes`

## Planner/Tasks Endpoints (20 endpoints)

### Plan Management
1. **List Plans** - `GET /plans?groupId={groupId}`
2. **Create Plan** - `POST /plans`
3. **Get Plan** - `GET /plans/{plan_id}`
4. **Update Plan** - `PATCH /plans/{plan_id}`
5. **Delete Plan** - `DELETE /plans/{plan_id}`
6. **Get Plan Details** - `GET /plans/{plan_id}/details`

### Task Management
7. **List Tasks** - `GET /tasks?planId={planId}`
8. **Create Task** - `POST /tasks`
9. **Get Task** - `GET /tasks/{task_id}`
10. **Update Task** - `PATCH /tasks/{task_id}`
11. **Delete Task** - `DELETE /tasks/{task_id}`
12. **Get Task Details** - `GET /tasks/{task_id}/details`
13. **Update Task Progress** - `PATCH /tasks/{task_id}/progress`

### User Tasks
14. **List My Tasks** - `GET /me/tasks`
15. **List User Tasks** - `GET /users/{user_id}/tasks`

### Bucket Management
16. **List Buckets** - `GET /plans/{plan_id}/buckets`
17. **Create Bucket** - `POST /buckets`
18. **Get Bucket** - `GET /buckets/{bucket_id}`
19. **Update Bucket** - `PATCH /buckets/{bucket_id}`
20. **Delete Bucket** - `DELETE /buckets/{bucket_id}`

### Task Board Formats
21. **Assigned To Format** - `GET /planner/tasks/{task_id}/assignedToTaskBoardFormat`
22. **Bucket Format** - `GET /planner/tasks/{task_id}/bucketTaskBoardFormat`
23. **Progress Format** - `GET /planner/tasks/{task_id}/progressTaskBoardFormat`

## User & Group Management (7 endpoints)

1. **List Users** - `GET /users`
2. **Get User** - `GET /users/{user_id}`
3. **List Deleted Users** - `GET /directory/deletedItems/microsoft.graph.user`
4. **List Groups** - `GET /groups`
5. **Check Group Planner Status** - `GET /groups/check-planner?displayName={name}`
6. **List Group Members** - `GET /groups/{group_id}/members`
7. **Add User to Group** - `POST /groups/members`
8. **Reset User Password** - `POST /users/resetPassword`

## Teams & Collaboration (4 endpoints)

1. **List Teams** - `GET /teams`
2. **List Channels** - `GET /teams/{team_id}/channels`
3. **Post Channel Message** - `POST /teams/messages`

## Files & Drives (4 endpoints)

1. **List Drives** - `GET /me/drives`
2. **List Root Items** - `GET /me/drive/root/children`
3. **Download File** - `GET /drives/{drive_id}/items/{item_id}/content`

## Security & Reporting (3 endpoints)

1. **Usage Summary** - `GET /reports/usage`
2. **Get Security Alerts** - `GET /security/alerts`
3. **List Managed Devices** - `GET /deviceManagement/managedDevices`

## Usage Examples

### Send an Email
```json
POST /me/sendMail
{
  "to": "user@example.com",
  "subject": "Meeting Tomorrow",
  "body": "Don't forget about our meeting at 2 PM.",
  "bodyType": "text"
}
```

### Create a Task
```json
POST /tasks
{
  "planId": "xqQg5FS2LkCp935s-FIFm2QAFkHM",
  "title": "Review project proposal",
  "bucketId": "hsOf2dhOJkqyYYZEtdzDe2QAIUCR"
}
```

### Accept Meeting Invitation
```json
POST /me/events/{event_id}/accept
{
  "comment": "Looking forward to it!",
  "sendResponse": true
}
```

### Find Meeting Times
```json
POST /me/findMeetingTimes
{
  "attendees": ["john@contoso.com", "jane@contoso.com"],
  "meetingDuration": "PT1H",
  "timeConstraint": {
    "timeslots": [{
      "start": {
        "dateTime": "2024-01-15T09:00:00",
        "timeZone": "Pacific Standard Time"
      },
      "end": {
        "dateTime": "2024-01-15T18:00:00",
        "timeZone": "Pacific Standard Time"
      }
    }]
  }
}
```

## Notes

1. All endpoints require proper authentication via Azure AD
2. Required environment variables:
   - `AZURE_TENANT_ID`
   - `AZURE_CLIENT_ID`
   - `AZURE_CLIENT_SECRET`
3. All timestamps should be in ISO 8601 format
4. For Planner updates, the `If-Match: *` header is automatically included
5. File attachments should be base64 encoded in the `contentBytes` field

This comprehensive set of endpoints enables agents to:
- Manage email workflows (read, send, reply, forward, organize)
- Schedule and manage calendar events
- Create and track tasks in Microsoft Planner
- Collaborate through Teams
- Access and manage files
- Monitor security and usage

All endpoints follow RESTful conventions and return appropriate HTTP status codes. 