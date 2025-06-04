# Microsoft 365 API Permissions Reference

This document lists all API permissions granted to the "Koviak Built" application across Microsoft Graph, Office 365 Management APIs, and OneNote services.

## Summary

- **Microsoft Graph**: 296 permissions
- **Office 365 Management APIs**: 3 permissions  
- **OneNote**: 6 permissions
- **Total**: 305 permissions

All permissions listed below have been **Granted for Koviak Built**.

---

## Table of Contents

1. [Microsoft Graph Permissions](#microsoft-graph-permissions)
   - [Application Management](#application-management)
   - [Bookings](#bookings)
   - [Bookmarks & Browser](#bookmarks--browser)
   - [Calendar & Mail](#calendar--mail)
   - [Calls & Communications](#calls--communications)
   - [Teams Channels](#teams-channels)
   - [Teams Chat](#teams-chat)
   - [Cloud Services](#cloud-services)
   - [Community & Viva Engage](#community--viva-engage)
   - [Contacts](#contacts)
   - [Directory & Identity](#directory--identity)
   - [Email Protocols](#email-protocols)
   - [External Data](#external-data)
   - [Files & SharePoint](#files--sharepoint)
   - [Finance](#finance)
   - [Goals](#goals)
   - [Groups](#groups)
   - [Identity & Security](#identity--security)
   - [Managed Tenants](#managed-tenants)
   - [Network Access](#network-access)
   - [Notes & OneNote](#notes--onenote)
   - [Online Meetings](#online-meetings)
   - [Organization](#organization)
   - [People](#people)
   - [Places](#places)
   - [Printing](#printing)
   - [Profile](#profile)
   - [Programs](#programs)
   - [Q&A](#qa)
   - [Reports](#reports)
   - [Role Management](#role-management)
   - [Scheduling](#scheduling)
   - [Search](#search)
   - [Security](#security)
   - [Service Activity](#service-activity)
   - [SharePoint](#sharepoint)
   - [Short Notes](#short-notes)
   - [Subscriptions](#subscriptions)
   - [Synchronization](#synchronization)
   - [Tasks](#tasks)
   - [Teams Core](#teams-core)
   - [Teams Activity](#teams-activity)
   - [Teams Apps](#teams-apps)
   - [Teams Tabs](#teams-tabs)
   - [Teams User Configuration](#teams-user-configuration)
   - [Term Store](#term-store)
   - [Threat Assessment](#threat-assessment)
   - [User Management](#user-management)
   - [Virtual Appointments](#virtual-appointments)
   - [Virtual Events](#virtual-events)
   - [Authentication](#authentication)
   - [Other](#other)
2. [Office 365 Management APIs](#office-365-management-apis)
3. [OneNote](#onenote)

---

## Microsoft Graph Permissions

### Application Management

| Permission | Type | Description | Admin Consent |
|------------|------|-------------|---------------|
| AppCatalog.ReadWrite.All | Application | Read and write to all app catalogs | Yes |
| Application-RemoteDesktopConfig.ReadWrite.All | Application | Read and write the remote desktop security configuration for all apps | Yes |
| Application.ReadWrite.OwnedBy | Application | Manage apps that this app creates or owns | Yes |

### Bookings

| Permission | Type | Description | Admin Consent |
|------------|------|-------------|---------------|
| Bookings.Manage.All | Delegated | Manage bookings information | No |
| Bookings.Read.All | Application | Read all Bookings related resources | Yes |
| Bookings.ReadWrite.All | Delegated | Read and write bookings information | No |
| BookingsAppointment.ReadWrite.All | Application | Read and write all Bookings related resources | Yes |

### Bookmarks & Browser

| Permission | Type | Description | Admin Consent |
|------------|------|-------------|---------------|
| Bookmark.Read.All | Delegated | Read all bookmarks that the user can access | No |
| Bookmark.Read.All | Application | Read all bookmarks | Yes |
| BrowserSiteLists.ReadWrite.All | Delegated | Read and write browser site lists for your organization | No |

### Calendar & Mail

| Permission | Type | Description | Admin Consent |
|------------|------|-------------|---------------|
| Calendars.ReadWrite | Delegated | Have full access to user calendars | No |
| Calendars.ReadWrite | Application | Read and write calendars in all mailboxes | Yes |
| Calendars.ReadWrite.Shared | Delegated | Read and write user and shared calendars | No |
| Mail.Read | Delegated | Read user mail | No |
| Mail.Read.Shared | Delegated | Read user and shared mail | No |
| Mail.ReadBasic | Delegated | Read user basic mail | No |
| Mail.ReadBasic.Shared | Delegated | Read user and shared basic mail | No |
| Mail.ReadWrite | Delegated | Read and write access to user mail | No |
| Mail.ReadWrite | Application | Read and write mail in all mailboxes | Yes |
| Mail.ReadWrite.Shared | Delegated | Read and write user and shared mail | No |
| Mail.Send | Delegated | Send mail as a user | No |
| Mail.Send | Application | Send mail as any user | Yes |
| Mail.Send.Shared | Delegated | Send mail on behalf of others | No |
| MailboxSettings.ReadWrite | Delegated | Read and write user mailbox settings | No |
| MailboxSettings.ReadWrite | Application | Read and write all user mailbox settings | Yes |

### Calls & Communications

| Permission | Type | Description | Admin Consent |
|------------|------|-------------|---------------|
| Calls.AccessMedia.All | Application | Access media streams in a call as an app | Yes |
| Calls.Initiate.All | Application | Initiate outgoing 1 to 1 calls from the app | Yes |
| Calls.InitiateGroupCall.All | Application | Initiate outgoing group calls from the app | Yes |
| Calls.JoinGroupCall.All | Application | Join group calls and meetings as an app | Yes |
| Calls.JoinGroupCallAsGuest.All | Application | Join group calls and meetings as a guest | Yes |

### Teams Channels

| Permission | Type | Description | Admin Consent |
|------------|------|-------------|---------------|
| Channel.Create | Application | Create channels | Yes |
| Channel.Delete.All | Application | Delete channels | Yes |
| Channel.ReadBasic.All | Application | Read the names and descriptions of all channels | Yes |
| ChannelMember.ReadWrite.All | Application | Add and remove members from all channels | Yes |
| ChannelMessage.Read.All | Delegated | Read user channel messages | Yes |
| ChannelMessage.Read.All | Application | Read all channel messages | Yes |
| ChannelMessage.UpdatePolicyViolation.All | Application | Flag channel messages for violating policy | Yes |
| ChannelSettings.ReadWrite.All | Application | Read and write the names, descriptions, and settings of all channels | Yes |

### Teams Chat

| Permission | Type | Description | Admin Consent |
|------------|------|-------------|---------------|
| Chat.Create | Delegated | Create chats | No |
| Chat.Create | Application | Create chats | Yes |
| Chat.ManageDeletion.All | Delegated | Delete and recover deleted chats | Yes |
| Chat.ManageDeletion.All | Application | Delete and recover deleted chats | Yes |
| Chat.Read | Delegated | Read user chat messages | No |
| Chat.Read.All | Application | Read all chat messages | Yes |
| Chat.Read.WhereInstalled | Application | Read all chat messages for chats where the associated Teams application is installed | Yes |
| Chat.ReadBasic | Delegated | Read names and members of user chat threads | No |
| Chat.ReadBasic.All | Application | Read names and members of all chat threads | Yes |
| Chat.ReadBasic.WhereInstalled | Application | Read names and members of all chat threads where the associated Teams application is installed | Yes |
| Chat.ReadWrite | Delegated | Read and write user chat messages | No |
| Chat.ReadWrite.All | Delegated | Read and write all chat messages | Yes |
| Chat.ReadWrite.All | Application | Read and write all chat messages | Yes |
| Chat.ReadWrite.WhereInstalled | Application | Read and write all chat messages for chats where the associated Teams application is installed | Yes |
| Chat.UpdatePolicyViolation.All | Application | Flag chat messages for violating policy | Yes |
| ChatMember.Read.WhereInstalled | Application | Read the members of all chats where the associated Teams application is installed | Yes |
| ChatMember.ReadWrite | Delegated | Add and remove members from chats | Yes |
| ChatMember.ReadWrite.All | Application | Add and remove members from all chats | Yes |
| ChatMember.ReadWrite.WhereInstalled | Application | Add and remove members from all chats where the associated Teams application is installed | Yes |
| ChatMessage.Read | Delegated | Read user chat messages | No |
| ChatMessage.Read.All | Application | Read all chat messages | Yes |
| ChatMessage.Send | Delegated | Send user chat messages | No |

### Cloud Services

| Permission | Type | Description | Admin Consent |
|------------|------|-------------|---------------|
| CloudApp-Discovery.Read.All | Application | Read all discovered cloud applications data | Yes |
| CloudPC.ReadWrite.All | Application | Read and write Cloud PCs | Yes |

### Community & Viva Engage

| Permission | Type | Description | Admin Consent |
|------------|------|-------------|---------------|
| Community.ReadWrite.All | Delegated | Read and write all Viva Engage communities | Yes |

### Contacts

| Permission | Type | Description | Admin Consent |
|------------|------|-------------|---------------|
| Contacts.ReadWrite | Delegated | Have full access to user contacts | No |
| Contacts.ReadWrite | Application | Read and write contacts in all mailboxes | Yes |
| Contacts.ReadWrite.Shared | Delegated | Read and write user and shared contacts | No |

### Directory & Identity

| Permission | Type | Description | Admin Consent |
|------------|------|-------------|---------------|
| CustomAuthenticationExtension.ReadWrite.All | Delegated | Read and write your organization's custom authentication extensions | Yes |
| Device.ReadWrite.All | Application | Read and write devices | Yes |
| Directory.AccessAsUser.All | Delegated | Access directory as the signed in user | Yes |
| Directory.ReadWrite.All | Delegated | Read and write directory data | Yes |
| Directory.ReadWrite.All | Application | Read and write directory data | Yes |
| Domain.Read.All | Application | Read domains | Yes |
| Domain.ReadWrite.All | Application | Read and write domains | Yes |

### Email Protocols

| Permission | Type | Description | Admin Consent |
|------------|------|-------------|---------------|
| EAS.AccessAsUser.All | Delegated | Access mailboxes via Exchange ActiveSync | No |
| EWS.AccessAsUser.All | Delegated | Access mailboxes as the signed-in user via Exchange Web Services | No |
| IMAP.AccessAsUser.All | Delegated | Read and write access to mailboxes via IMAP | No |
| POP.AccessAsUser.All | Delegated | Read and write access to mailboxes via POP | No |
| SMTP.Send | Delegated | Send emails from mailboxes using SMTP AUTH | No |

### External Data

| Permission | Type | Description | Admin Consent |
|------------|------|-------------|---------------|
| ExternalItem.ReadWrite.OwnedBy | Delegated | Read and write external items | Yes |
| ExternalUserProfile.ReadWrite.All | Delegated | Read and write external user profiles | Yes |

### Files & SharePoint

| Permission | Type | Description | Admin Consent |
|------------|------|-------------|---------------|
| Files.Read.All | Application | Read files in all site collections | Yes |
| Files.Read.Selected | Delegated | Read files that the user selects (preview) | No |
| Files.ReadWrite.All | Delegated | Have full access to all files user can access | No |
| Files.ReadWrite.All | Application | Read and write files in all site collections | Yes |
| Files.ReadWrite.AppFolder | Delegated | Have full access to the application's folder (preview) | No |
| Files.ReadWrite.AppFolder | Application | Have full access to the application's folder without a signed in user | Yes |
| Files.ReadWrite.Selected | Delegated | Read and write files that the user selects (preview) | No |
| Files.SelectedOperations.Selected | Application | Access selected Files without a signed in user | Yes |
| FileStorageContainer.Selected | Delegated | Access selected file storage containers | Yes |
| FileStorageContainer.Selected | Application | Access selected file storage containers | Yes |

### Finance

| Permission | Type | Description | Admin Consent |
|------------|------|-------------|---------------|
| Financials.ReadWrite.All | Delegated | Read and write financials data | No |

### Goals

| Permission | Type | Description | Admin Consent |
|------------|------|-------------|---------------|
| Goals-Export.ReadWrite.All | Delegated | Have full access to all goals and export jobs a user can access | Yes |

### Groups

| Permission | Type | Description | Admin Consent |
|------------|------|-------------|---------------|
| Group.Create | Application | Create groups | Yes |
| Group.ReadWrite.All | Delegated | Read and write all groups | Yes |
| Group.ReadWrite.All | Application | Read and write all groups | Yes |
| GroupMember.ReadWrite.All | Delegated | Read and write group memberships | Yes |
| GroupMember.ReadWrite.All | Application | Read and write all group memberships | Yes |

### Identity & Security

| Permission | Type | Description | Admin Consent |
|------------|------|-------------|---------------|
| IdentityRiskyUser.Read.All | Delegated | Read identity risky user information | Yes |
| IdentityRiskyUser.ReadWrite.All | Delegated | Read and write risky user information | Yes |
| IdentityRiskyUser.ReadWrite.All | Application | Read and write all risky user information | Yes |

### Managed Tenants

| Permission | Type | Description | Admin Consent |
|------------|------|-------------|---------------|
| ManagedTenants.ReadWrite.All | Delegated | Read and write all managed tenant information | Yes |

### Network Access

| Permission | Type | Description | Admin Consent |
|------------|------|-------------|---------------|
| NetworkAccess-Reports.Read.All | Application | Read all network access reports | Yes |
| NetworkAccess.ReadWrite.All | Application | Read and write all network access information | Yes |
| NetworkAccessBranch.ReadWrite.All | Application | Read and write properties of all branches for network access | Yes |

### Notes & OneNote

| Permission | Type | Description | Admin Consent |
|------------|------|-------------|---------------|
| Notes.Create | Delegated | Create user OneNote notebooks | No |
| Notes.Read.All | Delegated | Read all OneNote notebooks that user can access | No |
| Notes.ReadWrite | Delegated | Read and write user OneNote notebooks | No |
| Notes.ReadWrite.All | Delegated | Read and write all OneNote notebooks that user can access | No |
| Notes.ReadWrite.All | Application | Read and write all OneNote notebooks | Yes |

### Online Meetings

| Permission | Type | Description | Admin Consent |
|------------|------|-------------|---------------|
| OnlineMeetingArtifact.Read.All | Application | Read online meeting artifacts | Yes |
| OnlineMeetingRecording.Read.All | Delegated | Read all recordings of online meetings | Yes |
| OnlineMeetingRecording.Read.All | Application | Read all recordings of online meetings | Yes |
| OnlineMeetings.ReadWrite | Delegated | Read and create user's online meetings | No |
| OnlineMeetings.ReadWrite.All | Application | Read and create online meetings | Yes |
| OnlineMeetingTranscript.Read.All | Delegated | Read all transcripts of online meetings | Yes |
| OnlineMeetingTranscript.Read.All | Application | Read all transcripts of online meetings | Yes |

### Organization

| Permission | Type | Description | Admin Consent |
|------------|------|-------------|---------------|
| Organization.ReadWrite.All | Application | Read and write organization information | Yes |
| OrganizationalBranding.ReadWrite.All | Application | Read and write organizational branding information | Yes |
| OrgSettings-AppsAndServices.ReadWrite.All | Application | Read and write organization-wide apps and services settings | Yes |
| OrgSettings-Forms.ReadWrite.All | Application | Read and write organization-wide Microsoft Forms settings | Yes |
| OrgSettings-Microsoft365Install.Read.All | Application | Read organization-wide Microsoft 365 apps installation settings | Yes |
| OrgSettings-Microsoft365Install.ReadWrite.All | Application | Read and write organization-wide Microsoft 365 apps installation settings | Yes |
| OrgSettings-Todo.ReadWrite.All | Delegated | Read and write organization-wide Microsoft To Do settings | Yes |
| OrgSettings-Todo.ReadWrite.All | Application | Read and write organization-wide Microsoft To Do settings | Yes |

### People

| Permission | Type | Description | Admin Consent |
|------------|------|-------------|---------------|
| People.Read | Delegated | Read users' relevant people lists | No |
| People.Read.All | Delegated | Read all users' relevant people lists | Yes |
| People.Read.All | Application | Read all users' relevant people lists | Yes |
| PeopleSettings.ReadWrite.All | Delegated | Read and write tenant-wide people settings | Yes |
| PeopleSettings.ReadWrite.All | Application | Read and write all tenant-wide people settings | Yes |

### Places

| Permission | Type | Description | Admin Consent |
|------------|------|-------------|---------------|
| Place.ReadWrite.All | Delegated | Read and write organization places | Yes |
| PlaceDevice.ReadWrite.All | Delegated | Read and write all workplace devices | Yes |
| PlaceDevice.ReadWrite.All | Application | Read and write all workplace devices | Yes |

### Printing

| Permission | Type | Description | Admin Consent |
|------------|------|-------------|---------------|
| Printer.ReadWrite.All | Application | Read and update printers | Yes |
| PrintJob.Manage.All | Application | Perform advanced operations on print jobs | Yes |
| PrintJob.ReadWrite.All | Application | Read and write print jobs | Yes |
| PrintSettings.Read.All | Application | Read tenant-wide print settings | Yes |
| PrintTaskDefinition.ReadWrite.All | Application | Read, write and update print task definitions | Yes |

### Profile

| Permission | Type | Description | Admin Consent |
|------------|------|-------------|---------------|
| ProfilePhoto.Read.All | Application | Read profile photo of a user or group | Yes |
| ProfilePhoto.ReadWrite.All | Delegated | Read and write profile photo of a user or group | Yes |
| ProfilePhoto.ReadWrite.All | Application | Read and write profile photo of a user or group | Yes |

### Programs

| Permission | Type | Description | Admin Consent |
|------------|------|-------------|---------------|
| ProgramControl.Read.All | Application | Read all programs | Yes |
| ProgramControl.ReadWrite.All | Delegated | Manage all programs that user can access | Yes |
| ProgramControl.ReadWrite.All | Application | Manage all programs | Yes |

### Q&A

| Permission | Type | Description | Admin Consent |
|------------|------|-------------|---------------|
| QnA.Read.All | Application | Read all Question and Answers | Yes |

### Reports

| Permission | Type | Description | Admin Consent |
|------------|------|-------------|---------------|
| Reports.Read.All | Application | Read all usage reports | Yes |

### Role Management

| Permission | Type | Description | Admin Consent |
|------------|------|-------------|---------------|
| ResourceSpecificPermissionGrant.ReadForUser | Delegated | Read resource specific permissions granted on a user account | Yes |
| RoleAssignmentSchedule.ReadWrite.Directory | Delegated | Read, update, and delete all active role assignments for your company's directory | Yes |
| RoleEligibilitySchedule.ReadWrite.Directory | Delegated | Read, update, and delete all eligible role assignments for your company's directory | Yes |
| RoleManagement.Read.CloudPC | Delegated | Read Cloud PC RBAC settings | Yes |
| RoleManagement.ReadWrite.CloudPC | Delegated | Read and write Cloud PC RBAC settings | Yes |
| RoleManagement.ReadWrite.Directory | Delegated | Read and write directory RBAC settings | Yes |
| RoleManagement.ReadWrite.Exchange | Delegated | Read and write Exchange Online RBAC configuration | Yes |
| RoleManagementAlert.ReadWrite.Directory | Delegated | Read all alert data, configure alerts, and take actions on all alerts for your company's directory | Yes |
| RoleManagementPolicy.ReadWrite.AzureADGroup | Delegated | Read, update, and delete all policies in PIM for Groups | Yes |
| RoleManagementPolicy.ReadWrite.Directory | Delegated | Read, update, and delete all policies for privileged role assignments of your company's directory | Yes |

### Scheduling

| Permission | Type | Description | Admin Consent |
|------------|------|-------------|---------------|
| Schedule-WorkingTime.ReadWrite.All | Application | Trigger working time policies and read the working time status | Yes |
| Schedule.ReadWrite.All | Delegated | Read and write user schedule items | Yes |
| Schedule.ReadWrite.All | Application | Read and write all schedule items | Yes |
| SchedulePermissions.ReadWrite.All | Delegated | Read/Write schedule permissions for a role | Yes |
| SchedulePermissions.ReadWrite.All | Application | Read/Write schedule permissions for a role | Yes |

### Search

| Permission | Type | Description | Admin Consent |
|------------|------|-------------|---------------|
| SearchConfiguration.ReadWrite.All | Delegated | Read and write your organization's search configuration | Yes |
| SearchConfiguration.ReadWrite.All | Application | Read and write your organization's search configuration | Yes |

### Security

| Permission | Type | Description | Admin Consent |
|------------|------|-------------|---------------|
| SecurityActions.ReadWrite.All | Delegated | Read and update your organization's security actions | Yes |
| SecurityAlert.ReadWrite.All | Delegated | Read and write to all security alerts | Yes |
| SecurityAnalyzedMessage.ReadWrite.All | Delegated | Read metadata, detection details, and execute remediation actions on emails in your organization | Yes |
| SecurityEvents.ReadWrite.All | Application | Read and update your organization's security events | Yes |
| SecurityIncident.ReadWrite.All | Application | Read and write to all security incidents | Yes |

### Service Activity

| Permission | Type | Description | Admin Consent |
|------------|------|-------------|---------------|
| ServiceActivity-OneDrive.Read.All | Delegated | Read all One Drive service activity | Yes |
| ServiceActivity-OneDrive.Read.All | Application | Read all One Drive service activity | Yes |
| ServiceActivity-Teams.Read.All | Delegated | Read all Teams service activity | Yes |
| ServiceActivity-Teams.Read.All | Application | Read all Teams service activity | Yes |

### SharePoint

| Permission | Type | Description | Admin Consent |
|------------|------|-------------|---------------|
| SharePointTenantSettings.ReadWrite.All | Delegated | Read and change SharePoint and OneDrive tenant settings | Yes |
| Sites.FullControl.All | Delegated | Have full control of all site collections | Yes |
| Sites.FullControl.All | Application | Have full control of all site collections | Yes |
| Sites.Manage.All | Delegated | Create, edit, and delete items and lists in all site collections | No |
| Sites.Manage.All | Application | Create, edit, and delete items and lists in all site collections | Yes |
| Sites.Read.All | Application | Read items in all site collections | Yes |
| Sites.ReadWrite.All | Delegated | Edit or delete items in all site collections | No |
| Sites.ReadWrite.All | Application | Read and write items in all site collections | Yes |
| Sites.Selected | Delegated | Access selected Sites, on behalf of the signed-in user | No |
| Sites.Selected | Application | Access selected site collections | Yes |

### Short Notes

| Permission | Type | Description | Admin Consent |
|------------|------|-------------|---------------|
| ShortNotes.ReadWrite | Delegated | Read, create, edit, and delete short notes of the signed-in user | No |

### Subscriptions

| Permission | Type | Description | Admin Consent |
|------------|------|-------------|---------------|
| Subscription.Read.All | Delegated | Read all webhook subscriptions | Yes |

### Synchronization

| Permission | Type | Description | Admin Consent |
|------------|------|-------------|---------------|
| Synchronization.ReadWrite.All | Delegated | Read and write all Azure AD synchronization data | Yes |
| Synchronization.ReadWrite.All | Application | Read and write all Azure AD synchronization data | Yes |
| SynchronizationData-User.Upload | Delegated | Upload user data to the identity synchronization service | Yes |
| SynchronizationData-User.Upload | Application | Upload user data to the identity synchronization service | Yes |

### Tasks

| Permission | Type | Description | Admin Consent |
|------------|------|-------------|---------------|
| Tasks.ReadWrite | Delegated | Create, read, update, and delete user's tasks and task lists | No |
| Tasks.ReadWrite.All | Application | Read and write all users' tasks and tasklists | Yes |
| Tasks.ReadWrite.Shared | Delegated | Read and write user and shared tasks | No |

### Teams Core

| Permission | Type | Description | Admin Consent |
|------------|------|-------------|---------------|
| Team.Create | Delegated | Create teams | No |
| Team.Create | Application | Create teams | Yes |
| Team.ReadBasic.All | Delegated | Read the names and descriptions of teams | No |
| Team.ReadBasic.All | Application | Get a list of all teams | Yes |
| TeamMember.ReadWrite.All | Delegated | Add and remove members from teams | Yes |
| TeamMember.ReadWrite.All | Application | Add and remove members from all teams | Yes |
| TeamMember.ReadWriteNonOwnerRole.All | Delegated | Add and remove members with non-owner role for all teams | Yes |
| TeamMember.ReadWriteNonOwnerRole.All | Application | Add and remove members with non-owner role for all teams | Yes |
| TeamSettings.ReadWrite.All | Delegated | Read and change teams' settings | Yes |
| TeamSettings.ReadWrite.All | Application | Read and change all teams' settings | Yes |
| TeamTemplates.Read | Delegated | Read available Teams templates | No |
| TeamTemplates.Read.All | Application | Read all available Teams Templates | Yes |
| Teamwork.Migrate.All | Application | Create chat and channel messages with anyone's identity and with any timestamp | Yes |
| Teamwork.Read.All | Delegated | Read organizational teamwork settings | Yes |
| Teamwork.Read.All | Application | Read organizational teamwork settings | Yes |
| TeamworkAppSettings.ReadWrite.All | Delegated | Read and write Teams app settings | Yes |
| TeamworkAppSettings.ReadWrite.All | Application | Read and write Teams app settings | Yes |
| TeamworkDevice.ReadWrite.All | Delegated | Read and write Teams devices | Yes |
| TeamworkDevice.ReadWrite.All | Application | Read and write Teams devices | Yes |
| TeamworkTag.ReadWrite | Delegated | Read and write tags in Teams | Yes |
| TeamworkTag.ReadWrite.All | Application | Read and write tags in Teams | Yes |
| TeamworkUserInteraction.Read.All | Delegated | Read all of the possible Teams interactions between the user and other users | Yes |

### Teams Activity

| Permission | Type | Description | Admin Consent |
|------------|------|-------------|---------------|
| TeamsActivity.Read | Delegated | Read user's teamwork activity feed | No |
| TeamsActivity.Read.All | Application | Read all users' teamwork activity feed | Yes |
| TeamsActivity.Send | Delegated | Send a teamwork activity as the user | No |
| TeamsActivity.Send | Application | Send a teamwork activity to any user | Yes |

### Teams Apps

| Permission | Type | Description | Admin Consent |
|------------|------|-------------|---------------|
| TeamsAppInstallation.ReadForChat.All | Application | Read installed Teams apps for all chats | Yes |
| TeamsAppInstallation.ReadForTeam.All | Application | Read installed Teams apps for all teams | Yes |
| TeamsAppInstallation.ReadForUser.All | Application | Read installed Teams apps for all users | Yes |
| TeamsAppInstallation.ReadWriteAndConsentForChat | Delegated | Manage installed Teams apps in chats | Yes |
| TeamsAppInstallation.ReadWriteAndConsentForChat.All | Application | Manage installation and permission grants of Teams apps for all chats | Yes |
| TeamsAppInstallation.ReadWriteAndConsentForTeam | Delegated | Manage installed Teams apps in teams | Yes |
| TeamsAppInstallation.ReadWriteAndConsentForTeam.All | Application | Manage installation and permission grants of Teams apps for all teams | Yes |
| TeamsAppInstallation.ReadWriteAndConsentForUser | Delegated | Manage installation and permission grants of Teams apps in users' personal scope | Yes |
| TeamsAppInstallation.ReadWriteAndConsentForUser.All | Application | Manage installation and permission grants of Teams apps in a user account | Yes |
| TeamsAppInstallation.ReadWriteAndConsentSelfForChat | Delegated | Allow the Teams app to manage itself and its permission grants in chats | Yes |
| TeamsAppInstallation.ReadWriteAndConsentSelfForChat.All | Application | Allow the Teams app to manage itself and its permission grants for all chats | Yes |
| TeamsAppInstallation.ReadWriteAndConsentSelfForTeam | Delegated | Allow the Teams app to manage itself and its permission grants in teams | Yes |
| TeamsAppInstallation.ReadWriteAndConsentSelfForTeam.All | Application | Allow the Teams app to manage itself and its permission grants for all teams | Yes |
| TeamsAppInstallation.ReadWriteAndConsentSelfForUser | Delegated | Allow the Teams app to manage itself and its permission grants in user accounts | Yes |
| TeamsAppInstallation.ReadWriteAndConsentSelfForUser.All | Application | Allow the Teams app to manage itself and its permission grants in all user accounts | Yes |
| TeamsAppInstallation.ReadWriteForChat | Delegated | Manage installed Teams apps in chats | Yes |
| TeamsAppInstallation.ReadWriteForChat.All | Application | Manage Teams apps for all chats | Yes |
| TeamsAppInstallation.ReadWriteForTeam | Delegated | Manage installed Teams apps in teams | Yes |
| TeamsAppInstallation.ReadWriteForTeam.All | Application | Manage Teams apps for all teams | Yes |
| TeamsAppInstallation.ReadWriteForUser | Delegated | Manage user's installed Teams apps | Yes |
| TeamsAppInstallation.ReadWriteForUser.All | Application | Manage Teams apps for all users | Yes |
| TeamsAppInstallation.ReadWriteSelfForChat | Delegated | Allow the Teams app to manage itself in chats | Yes |
| TeamsAppInstallation.ReadWriteSelfForChat.All | Application | Allow the Teams app to manage itself for all chats | Yes |
| TeamsAppInstallation.ReadWriteSelfForTeam | Delegated | Allow the app to manage itself in teams | Yes |
| TeamsAppInstallation.ReadWriteSelfForTeam.All | Application | Allow the Teams app to manage itself for all teams | Yes |
| TeamsAppInstallation.ReadWriteSelfForUser | Delegated | Allow the Teams app to manage itself for a user | No |
| TeamsAppInstallation.ReadWriteSelfForUser.All | Application | Allow the app to manage itself for all users | Yes |

### Teams Tabs

| Permission | Type | Description | Admin Consent |
|------------|------|-------------|---------------|
| TeamsTab.Create | Delegated | Create tabs in Microsoft Teams | Yes |
| TeamsTab.Create | Application | Create tabs in Microsoft Teams | Yes |
| TeamsTab.ReadWrite.All | Delegated | Read and write tabs in Microsoft Teams | Yes |
| TeamsTab.ReadWrite.All | Application | Read and write tabs in Microsoft Teams | Yes |
| TeamsTab.ReadWriteForChat | Delegated | Allow the Teams app to manage all tabs in chats | Yes |
| TeamsTab.ReadWriteForChat.All | Application | Allow the Teams app to manage all tabs for all chats | Yes |
| TeamsTab.ReadWriteForTeam | Delegated | Allow the Teams app to manage all tabs in teams | Yes |
| TeamsTab.ReadWriteForTeam.All | Application | Allow the Teams app to manage all tabs for all teams | Yes |
| TeamsTab.ReadWriteForUser | Delegated | Allow the Teams app to manage all tabs for a user | No |
| TeamsTab.ReadWriteForUser.All | Application | Allow the app to manage all tabs for all users | Yes |
| TeamsTab.ReadWriteSelfForChat | Delegated | Allow the Teams app to manage only its own tabs in chats | Yes |
| TeamsTab.ReadWriteSelfForChat.All | Application | Allow the Teams app to manage only its own tabs for all chats | Yes |
| TeamsTab.ReadWriteSelfForTeam | Delegated | Allow the Teams app to manage only its own tabs in teams | Yes |
| TeamsTab.ReadWriteSelfForTeam.All | Application | Allow the Teams app to manage only its own tabs for all teams | Yes |
| TeamsTab.ReadWriteSelfForUser | Delegated | Allow the Teams app to manage only its own tabs for a user | No |
| TeamsTab.ReadWriteSelfForUser.All | Application | Allow the Teams app to manage only its own tabs for all users | Yes |

### Teams User Configuration

| Permission | Type | Description | Admin Consent |
|------------|------|-------------|---------------|
| TeamsUserConfiguration.Read.All | Delegated | Read Teams user configurations | Yes |
| TeamsUserConfiguration.Read.All | Application | Read Teams user configurations | Yes |

### Term Store

| Permission | Type | Description | Admin Consent |
|------------|------|-------------|---------------|
| TermStore.ReadWrite.All | Delegated | Read and write term store data | Yes |

### Threat Assessment

| Permission | Type | Description | Admin Consent |
|------------|------|-------------|---------------|
| ThreatAssessment.ReadWrite.All | Delegated | Read and write threat assessment requests | Yes |

### User Management

| Permission | Type | Description | Admin Consent |
|------------|------|-------------|---------------|
| User.EnableDisableAccount.All | Delegated | Enable and disable user accounts | Yes |
| User.EnableDisableAccount.All | Application | Enable and disable user accounts | Yes |
| User.Export.All | Delegated | Export user's data | Yes |
| User.Export.All | Application | Export user's data | Yes |
| User.Invite.All | Delegated | Invite guest users to the organization | Yes |
| User.Invite.All | Application | Invite guest users to the organization | Yes |
| User.ManageIdentities.All | Delegated | Manage user identities | Yes |
| User.ManageIdentities.All | Application | Manage all users' identities | Yes |
| User.Read | Delegated | Sign in and read user profile | No |
| User.Read.All | Delegated | Read all users' full profiles | Yes |
| User.ReadBasic.All | Delegated | Read all users' basic profiles | No |
| User.ReadWrite | Delegated | Read and write access to user profile | No |
| User.ReadWrite.All | Delegated | Read and write all users' full profiles | Yes |
| User.ReadWrite.All | Application | Read and write all users' full profiles | Yes |
| UserAuthenticationMethod.Read.All | Application | Read all users' authentication methods | Yes |
| UserAuthenticationMethod.ReadWrite.All | Application | Read and write all users' authentication methods | Yes |
| UserNotification.ReadWrite.CreatedByApp | Application | Deliver and manage all user's notifications | Yes |
| UserTeamwork.Read | Delegated | Read user teamwork settings | Yes |
| UserTeamwork.Read.All | Application | Read all user teamwork settings | Yes |
| UserTimelineActivity.Write.CreatedByApp | Delegated | Write app activity to users' timeline | No |

### Virtual Appointments

| Permission | Type | Description | Admin Consent |
|------------|------|-------------|---------------|
| VirtualAppointment.ReadWrite | Delegated | Read and write a user's virtual appointments | Yes |
| VirtualAppointment.ReadWrite.All | Application | Read-write all virtual appointments for users, as authorized by online meetings app access policy | Yes |
| VirtualAppointmentNotification.Send | Delegated | Send notification regarding virtual appointments for the signed-in user | Yes |
| VirtualAppointmentNotification.Send | Application | Send notification regarding virtual appointments as any user | Yes |

### Virtual Events

| Permission | Type | Description | Admin Consent |
|------------|------|-------------|---------------|
| VirtualEvent.Read.All | Application | Read all users' virtual events | Yes |
| VirtualEvent.ReadWrite | Delegated | Read and write your virtual events | Yes |
| VirtualEventRegistration-Anon.ReadWrite.All | Application | Read and write anonymous users' virtual event registrations | Yes |

### Authentication

| Permission | Type | Description | Admin Consent |
|------------|------|-------------|---------------|
| email | Delegated | View users' email address | No |
| offline_access | Delegated | Maintain access to data you have given it access to | No |
| openid | Delegated | Sign users in | No |
| profile | Delegated | View users' basic profile | No |

### Other

| Permission | Type | Description | Admin Consent |
|------------|------|-------------|---------------|
| Family.Read | Delegated | Read your family info | No |
| f20584af-9290-4153-9280-ff8bb2c0ea7f | Application | (No description provided) | Yes |

---

## Office 365 Management APIs

| Permission | Type | Description | Admin Consent |
|------------|------|-------------|---------------|
| ActivityFeed.Read | Delegated | Read activity data for your organization | Yes |
| ActivityFeed.ReadDlp | Delegated | Read DLP policy events including detected sensitive data | Yes |
| ServiceHealth.Read | Delegated | Read service health information for your organization | Yes |

---

## OneNote

| Permission | Type | Description | Admin Consent |
|------------|------|-------------|---------------|
| Notes.Create | Delegated | Create pages in OneNote notebooks | No |
| Notes.Read | Delegated | View OneNote notebooks | No |
| Notes.Read.All | Delegated | View OneNote notebooks in your organization | No |
| Notes.ReadWrite | Delegated | View and modify OneNote notebooks | No |
| Notes.ReadWrite.All | Delegated | View and modify OneNote notebooks in your organization | No |
| Notes.ReadWrite.CreatedByApp | Delegated | Application-only OneNote notebook access | No |

---

## Key Information

### Permission Types
- **Delegated**: Permissions that allow the app to act on behalf of the signed-in user
- **Application**: Permissions that allow the app to act without a signed-in user

### Admin Consent
- **Yes**: Administrator approval is required for these permissions
- **No**: Users can consent to these permissions themselves

### Common Permission Patterns
- `.Read` - Read-only access
- `.ReadWrite` - Read and write access
- `.All` - Access to all resources of that type
- `.Shared` - Access to shared resources
- `.Selected` - Access to specific selected resources
- `.OwnedBy` - Access only to resources owned by the app
</rewritten_file> 