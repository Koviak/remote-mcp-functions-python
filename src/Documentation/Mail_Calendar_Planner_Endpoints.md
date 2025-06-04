# Comprehensive Microsoft Graph Mail, Calendar, and Planner Endpoints

This document contains a complete list of ALL Mail, Calendar, and Planner endpoints available in Microsoft Graph API v1.0. These endpoints allow you to build agents that can fully manage email, calendar events, and task management in Microsoft 365.

## Table of Contents
- [Mail Endpoints](#mail-endpoints)
- [Calendar Endpoints](#calendar-endpoints)
- [Planner Endpoints](#planner-endpoints)

---

## Mail Endpoints

### Core Mail Operations

#### Messages
```text
# List messages
GET /me/messages
GET /users/{id | userPrincipalName}/messages
GET /me/mailFolders/{id}/messages
GET /me/mailFolders('Inbox')/messages

# Get specific message
GET /me/messages/{id}
GET /users/{id | userPrincipalName}/messages/{id}

# Create message (draft)
POST /me/messages
POST /users/{id | userPrincipalName}/messages
POST /me/mailFolders/{id}/messages

# Update message
PATCH /me/messages/{id}
PATCH /users/{id | userPrincipalName}/messages/{id}

# Delete message
DELETE /me/messages/{id}
DELETE /users/{id | userPrincipalName}/messages/{id}

# Move message
POST /me/messages/{id}/move
POST /users/{id | userPrincipalName}/messages/{id}/move

# Copy message
POST /me/messages/{id}/copy
POST /users/{id | userPrincipalName}/messages/{id}/copy
```

#### Message Actions
```text
# Send message
POST /me/sendMail
POST /users/{id | userPrincipalName}/sendMail

# Send draft message
POST /me/messages/{id}/send
POST /users/{id | userPrincipalName}/messages/{id}/send

# Reply to message
POST /me/messages/{id}/reply
POST /me/messages/{id}/replyAll

# Create reply draft
POST /me/messages/{id}/createReply
POST /me/messages/{id}/createReplyAll

# Forward message
POST /me/messages/{id}/forward
POST /me/messages/{id}/createForward
```

### Mail Folders

```text
# List mail folders
GET /me/mailFolders
GET /users/{id | userPrincipalName}/mailFolders
GET /me/mailFolders/{id}/childFolders

# Get specific folder
GET /me/mailFolders/{id}
GET /me/mailFolders('Inbox')
GET /me/mailFolders('SentItems')
GET /me/mailFolders('Drafts')
GET /me/mailFolders('DeletedItems')
GET /me/mailFolders('Archive')
GET /me/mailFolders('JunkEmail')

# Create folder
POST /me/mailFolders
POST /me/mailFolders/{id}/childFolders

# Update folder
PATCH /me/mailFolders/{id}

# Delete folder
DELETE /me/mailFolders/{id}

# Move folder
POST /me/mailFolders/{id}/move

# Copy folder
POST /me/mailFolders/{id}/copy
```

### Mail Attachments

```text
# List attachments
GET /me/messages/{id}/attachments
GET /users/{id | userPrincipalName}/messages/{id}/attachments

# Get attachment
GET /me/messages/{id}/attachments/{id}
GET /me/messages/{id}/attachments/{id}/$value

# Add attachment
POST /me/messages/{id}/attachments
POST /users/{id | userPrincipalName}/messages/{id}/attachments

# Delete attachment
DELETE /me/messages/{id}/attachments/{id}

# Large file attachments (upload session)
POST /me/messages/{id}/attachments/createUploadSession
```

### Mail Rules & Categories

```text
# Message rules
GET /me/mailFolders/inbox/messageRules
GET /me/mailFolders/inbox/messageRules/{id}
POST /me/mailFolders/inbox/messageRules
PATCH /me/mailFolders/inbox/messageRules/{id}
DELETE /me/mailFolders/inbox/messageRules/{id}

# Categories (Outlook categories)
GET /me/outlook/masterCategories
GET /me/outlook/masterCategories/{id}
POST /me/outlook/masterCategories
PATCH /me/outlook/masterCategories/{id}
DELETE /me/outlook/masterCategories/{id}
```

### Mail Search & Filter

```text
# Search messages
GET /me/messages?$search="subject:meeting"
GET /me/messages?$filter=subject eq 'Project Update'
GET /me/messages?$filter=from/emailAddress/address eq 'user@contoso.com'
GET /me/messages?$filter=hasAttachments eq true
GET /me/messages?$filter=importance eq 'high'
GET /me/messages?$filter=isRead eq false
GET /me/messages?$filter=receivedDateTime ge 2023-01-01

# Search folders
POST /me/mailFolders/{id}/childFolders
{
  "@odata.type": "microsoft.graph.mailSearchFolder",
  "displayName": "Weekly Digest",
  "includeNestedFolders": true,
  "sourceFolderIds": ["AQMkADY..."],
  "filterQuery": "subject:weekly digest"
}
```

### Mail Settings & Configuration

```text
# Mailbox settings
GET /me/mailboxSettings
PATCH /me/mailboxSettings

# Automatic replies (Out of Office)
GET /me/mailboxSettings/automaticRepliesSetting
PATCH /me/mailboxSettings/automaticRepliesSetting

# Mail tips
POST /me/getMailTips
POST /users/{id}/getMailTips

# Focused inbox overrides
GET /me/inferenceClassification/overrides
POST /me/inferenceClassification/overrides
PATCH /me/inferenceClassification/overrides/{id}
DELETE /me/inferenceClassification/overrides/{id}
```

### Message Tracking & Extended Properties

```text
# Message headers
GET /me/messages/{id}?$select=internetMessageHeaders

# Single-value extended properties
GET /me/messages?$filter=singleValueExtendedProperties/any(ep: ep/id eq 'String {GUID} Name PropertyName' and ep/value eq 'value')

# Multi-value extended properties  
GET /me/messages/{id}?$expand=multiValueExtendedProperties($filter=id eq 'String {GUID} Name PropertyName')
```

---

## Calendar Endpoints

### Core Calendar Operations

#### Calendars
```text
# List calendars
GET /me/calendars
GET /users/{id | userPrincipalName}/calendars
GET /me/calendarGroups/{id}/calendars

# Get calendar
GET /me/calendar
GET /me/calendars/{id}
GET /users/{id | userPrincipalName}/calendar
GET /users/{id | userPrincipalName}/calendars/{id}

# Create calendar
POST /me/calendars
POST /me/calendarGroups/{id}/calendars

# Update calendar
PATCH /me/calendars/{id}

# Delete calendar
DELETE /me/calendars/{id}

# Get calendar view (expanded events)
GET /me/calendar/calendarView?startDateTime={start}&endDateTime={end}
GET /me/calendars/{id}/calendarView?startDateTime={start}&endDateTime={end}
```

#### Events
```text
# List events
GET /me/events
GET /me/calendar/events
GET /me/calendars/{id}/events
GET /users/{id | userPrincipalName}/events
GET /users/{id | userPrincipalName}/calendar/events

# Get event
GET /me/events/{id}
GET /users/{id | userPrincipalName}/events/{id}

# Create event
POST /me/events
POST /me/calendar/events
POST /me/calendars/{id}/events
POST /users/{id | userPrincipalName}/events

# Update event
PATCH /me/events/{id}
PATCH /users/{id | userPrincipalName}/events/{id}

# Delete event
DELETE /me/events/{id}
DELETE /users/{id | userPrincipalName}/events/{id}

# Cancel event (organizer only)
POST /me/events/{id}/cancel
```

#### Event Actions
```text
# Accept event
POST /me/events/{id}/accept

# Tentatively accept
POST /me/events/{id}/tentativelyAccept

# Decline event
POST /me/events/{id}/decline

# Forward event
POST /me/events/{id}/forward

# Snooze reminder
POST /me/events/{id}/snoozeReminder

# Dismiss reminder
POST /me/events/{id}/dismissReminder
```

### Event Instances & Recurrence

```text
# List instances of recurring event
GET /me/events/{id}/instances
GET /me/events/{id}/instances?startDateTime={start}&endDateTime={end}

# Get specific instance
GET /me/events/{id}/instances/{id}

# Update instance
PATCH /me/events/{id}/instances/{id}

# Exception occurrences
GET /me/events/{seriesMasterId}/exceptionOccurrences

# Permanently delete event
POST /me/events/{id}/permanentDelete
```

### Calendar Groups

```text
# List calendar groups
GET /me/calendarGroups
GET /users/{id | userPrincipalName}/calendarGroups

# Get calendar group
GET /me/calendarGroups/{id}

# Create calendar group
POST /me/calendarGroups

# Update calendar group
PATCH /me/calendarGroups/{id}

# Delete calendar group
DELETE /me/calendarGroups/{id}
```

### Meeting & Scheduling

```text
# Find meeting times
POST /me/findMeetingTimes
POST /users/{id}/findMeetingTimes

# Get schedule (free/busy)
POST /me/calendar/getSchedule
POST /users/{id}/calendar/getSchedule

# Calendar permissions
GET /me/calendars/{id}/calendarPermissions
POST /me/calendars/{id}/calendarPermissions
PATCH /me/calendars/{id}/calendarPermissions/{id}
DELETE /me/calendars/{id}/calendarPermissions/{id}
```

### Event Attachments

```text
# List event attachments
GET /me/events/{id}/attachments
GET /me/calendar/events/{id}/attachments

# Get attachment
GET /me/events/{id}/attachments/{id}
GET /me/events/{id}/attachments/{id}/$value

# Add attachment
POST /me/events/{id}/attachments

# Delete attachment
DELETE /me/events/{id}/attachments/{id}
```

### Event Extended Properties

```text
# Single-value extended properties
GET /me/events/{id}?$expand=singleValueExtendedProperties
POST /me/events/{id}/singleValueExtendedProperties

# Multi-value extended properties
GET /me/events/{id}?$expand=multiValueExtendedProperties
POST /me/events/{id}/multiValueExtendedProperties
```

---

## Planner Endpoints

### Core Planner Operations

#### Planner Root
```text
GET /planner
```

#### Plans
```text
# List plans
GET /groups/{group-id}/planner/plans
GET /planner/plans

# Get plan
GET /planner/plans/{plan-id}

# Create plan
POST /planner/plans

# Update plan
PATCH /planner/plans/{plan-id}

# Delete plan
DELETE /planner/plans/{plan-id}

# Get plan details
GET /planner/plans/{plan-id}/details

# Update plan details
PATCH /planner/plans/{plan-id}/details
```

#### Tasks
```text
# List tasks
GET /planner/plans/{plan-id}/tasks
GET /planner/tasks
GET /me/planner/tasks
GET /users/{id | userPrincipalName}/planner/tasks

# Get task
GET /planner/tasks/{task-id}

# Create task
POST /planner/tasks

# Update task
PATCH /planner/tasks/{task-id}

# Delete task
DELETE /planner/tasks/{task-id}

# Get task details
GET /planner/tasks/{task-id}/details

# Update task details
PATCH /planner/tasks/{task-id}/details
```

#### Buckets
```text
# List buckets
GET /planner/plans/{plan-id}/buckets
GET /planner/buckets

# Get bucket
GET /planner/buckets/{bucket-id}

# Create bucket
POST /planner/buckets

# Update bucket
PATCH /planner/buckets/{bucket-id}

# Delete bucket
DELETE /planner/buckets/{bucket-id}

# List tasks in bucket
GET /planner/buckets/{bucket-id}/tasks
```

### Task Board Formats

```text
# Assigned to task board format
GET /planner/tasks/{task-id}/assignedToTaskBoardFormat
PATCH /planner/tasks/{task-id}/assignedToTaskBoardFormat

# Bucket task board format
GET /planner/tasks/{task-id}/bucketTaskBoardFormat
PATCH /planner/tasks/{task-id}/bucketTaskBoardFormat

# Progress task board format
GET /planner/tasks/{task-id}/progressTaskBoardFormat
PATCH /planner/tasks/{task-id}/progressTaskBoardFormat
```

### User Information

```text
# Get user's planner info
GET /me/planner
GET /users/{id | userPrincipalName}/planner

# Get user's assigned plans
GET /me/planner/plans
GET /users/{id | userPrincipalName}/planner/plans

# Get user's created tasks
GET /me/planner/tasks
GET /users/{id | userPrincipalName}/planner/tasks
```

### Plan & Task Properties

#### Plan Properties
- **title**: Plan name
- **owner**: Group ID that owns the plan
- **createdBy**: User who created the plan
- **createdDateTime**: Creation timestamp
- **container**: Container information (group)

#### Task Properties
- **title**: Task title
- **planId**: Associated plan
- **bucketId**: Associated bucket
- **assigneePriority**: Priority for assignee
- **percentComplete**: Completion percentage (0, 50, 100)
- **startDateTime**: Start date
- **dueDateTime**: Due date
- **hasDescription**: Has description flag
- **previewType**: Preview type
- **completedDateTime**: Completion timestamp
- **completedBy**: User who completed
- **referenceCount**: Number of references
- **checklistItemCount**: Number of checklist items
- **activeChecklistItemCount**: Active checklist items
- **conversationThreadId**: Associated conversation
- **orderHint**: Ordering hint
- **assignments**: User assignments

---

## Authentication & Permissions

### Required Permissions

#### Mail Permissions
- **Mail.Read**: Read mail in all folders
- **Mail.ReadWrite**: Read, write, send mail
- **Mail.Send**: Send mail only
- **MailboxSettings.ReadWrite**: Manage mailbox settings

#### Calendar Permissions
- **Calendars.Read**: Read calendars
- **Calendars.ReadWrite**: Full calendar access
- **Calendars.Read.Shared**: Read shared calendars

#### Planner Permissions
- **Tasks.Read**: Read tasks
- **Tasks.ReadWrite**: Create and manage tasks
- **Group.Read.All**: Read group plans
- **Group.ReadWrite.All**: Manage group plans

### Important Notes

1. **Immutable IDs**: Use `Prefer: IdType="ImmutableId"` header for stable IDs
2. **Time Zones**: Use `Prefer: outlook.timezone="{timezone}"` for calendar operations
3. **ETags**: Planner requires `If-Match` header with current etag for updates
4. **Delegated vs Application**: Some operations require delegated permissions
5. **Rate Limits**: Be aware of throttling limits for each service

This comprehensive list covers all available Mail, Calendar, and Planner endpoints in Microsoft Graph v1.0. Use these endpoints to build powerful automation agents that can fully manage email, scheduling, and task management workflows. 