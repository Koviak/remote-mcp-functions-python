Below is a structured **Microsoft Graph v1.0 endpoint catalog**.  Every endpoint follows the pattern `https://graph.microsoft.com/v1.0/<resource path>`; swap **`v1.0`** with **`beta`** to call preview APIs.

> **📌 Specialized Documentation Available**  
> For comprehensive coverage of Mail, Calendar, and Planner endpoints (needed for building email/scheduling/task agents), see:  
> **[Mail_Calendar_Planner_Endpoints.md](Mail_Calendar_Planner_Endpoints.md)**

---

## Directory & Identity

| Operation            | Endpoint (v1.0 path)        | Notes                                      |
| -------------------- | --------------------------- | ------------------------------------------ |
| List users           | `/users`                    | Lists all users in the tenant              |
| Get user             | `/users/{user-id}`          | Retrieve a single user object              |
| List groups          | `/groups`                   | Enumerates all Microsoft 365/Entra groups  |
| Get group            | `/groups/{group-id}`        | Retrieve group properties                  |
| List directory roles | `/directoryRoles`           | Shows activated admin roles                |
| Get directory role   | `/directoryRoles/{role-id}` | Read a specific admin role                 |

---

## Applications & Service Principals

```text
/applications                        // app registrations
/applications/{id}                   // specific app
/servicePrincipals                   // enterprise applications
/servicePrincipals/{id}              // specific service principal
/appRoleAssignments                  // application permissions
/oauth2PermissionGrants              // delegated permissions
```

---

## Authentication & Authorization

```text
/identity/authenticationMethods      // authentication methods
/identity/conditionalAccess/policies // conditional access
/identity/conditionalAccess/namedLocations
/policies/authorizationPolicy        // authorization settings
/policies/claimsMappingPolicies      // claims mapping
/policies/tokenLifetimePolicies      // token lifetime
```

---

## Mail, Calendar & Contacts (Outlook)

> **📘 Comprehensive Reference Available**  
> For a complete list of ALL Mail, Calendar, and Planner endpoints with detailed operations, see:  
> **[Mail_Calendar_Planner_Endpoints.md](Mail_Calendar_Planner_Endpoints.md)**

```text
# Basic examples - see comprehensive reference for all endpoints
/me/messages                  // get signed-in user's mail folder
/users/{id}/messages          // another user's mail
/me/events                    // calendar events
/me/calendars                 // list calendars
/me/contacts                  // personal contacts
```

---

## Files & Drives (OneDrive / SharePoint)

| Scope                  | Example Endpoint         | Reference                  |
| ---------------------- | ------------------------ | -------------------------- |
| Signed-in user drive   | `/me/drive`              | Provisioned on first call  |
| Another user drive     | `/users/{id}/drive`      | Same pattern               |
| SharePoint site drives | `/sites/{site-id}/drive` | Site-scoped                |
| Enumerate sites        | `/sites`                 | List all sites             |
| Lists within site      | `/sites/{site-id}/lists` | SharePoint lists           |

---

## Teams & Chat

```text
/teams                        // list or create teams
/teams/{team-id}              // team details
/chats                        // list chats
/chats/{chat-id}              // chat thread
/teams/getAllChannels         // all channels in org
```

---

## Communications & Presence

```text
/communications/calls                 // cloud calls
/communications/callRecords           // call analytics
/communications/onlineMeetings        // meetings
/communications/presences             // user presence
/users/{id}/presence                  // specific user presence
```

---

## Planner & Microsoft To Do

> **📘 Complete Planner Endpoints Available**  
> For ALL Planner endpoints including task board formats, assignments, and more, see:  
> **[Mail_Calendar_Planner_Endpoints.md](Mail_Calendar_Planner_Endpoints.md#planner-endpoints)**

| Resource     | Endpoint                           | Reference     |
| ------------ | ---------------------------------- | ------------- |
| Planner root | `/planner`                         | API overview  |
| Plans        | `/planner/plans`                   |               |
| Buckets      | `/planner/plans/{plan-id}/buckets` |               |
| Tasks        | `/planner/tasks`                   |               |
| To Do lists  | `/me/todo/lists`                   |               |
| To Do tasks  | `/me/todo/lists/{list-id}/tasks`   |               |

---

## Security

```text
/security/alerts              // security alerts
/security/alerts_v2           // new alerts API
/security/incidents           // incident records
/security/tiIndicators        // threat intelligence
/security/attackSimulation    // attack simulation training
```

---

## Device Management (Intune)

| Purpose                | Endpoint                                     | Reference     |
| ---------------------- | -------------------------------------------- | ------------- |
| Intune root            | `/deviceManagement`                          | Overview      |
| Managed devices        | `/deviceManagement/managedDevices`           | List devices  |
| Configuration profiles | `/deviceManagement/deviceConfigurations`     |               |
| Compliance policies    | `/deviceManagement/deviceCompliancePolicies` |               |
| All devices            | `/devices`                                   | Entra devices |

---

## Identity Governance

```text
/identityGovernance                              // root container
/identityGovernance/entitlementManagement        // access packages
/identityGovernance/lifecycleWorkflows           // joiner/leaver workflows
/identityGovernance/accessReviews                // access reviews
/identityGovernance/termsOfUse                   // terms of use agreements
```

---

## Audit & Compliance

```text
/auditLogs/directoryAudits           // directory audit logs
/auditLogs/signIns                   // sign-in logs
/auditLogs/provisioning              // provisioning logs
/privacy/subjectRightsRequests       // GDPR/privacy requests
/compliance/ediscovery               // eDiscovery cases
```

---

## Licensing & Subscriptions

```text
/subscribedSkus                      // available licenses
/users/{id}/licenseDetails           // user licenses
/groups/{id}/assignLicense           // group licensing
/directory/deletedItems              // soft-deleted objects
```

---

## Organization & Domains

```text
/organization                        // tenant details
/domains                             // verified domains
/contracts                           // partner contracts
/directory/administrativeUnits       // admin units
```

---

## Print Services

```text
/print/printers                      // universal print printers
/print/shares                        // printer shares
/print/services                      // print services
/print/taskDefinitions               // print task definitions
```

---

## External Identities

```text
/invitations                         // B2B invitations
/identity/b2xUserFlows               // user flows
/identity/identityProviders          // external IDPs
/identity/userFlowAttributes         // custom attributes
```

---

## Reports & Insights

* **Usage & activity reports:** `/reports` 
* **Sign-in reports:** `/reports/authenticationMethods`
* **Microsoft Teams reports:** `/reports/getTeamsUserActivityCounts`
* **Insights:** `/me/insights/used` (MyAnalytics)

---

## Change Notifications

```text
/subscriptions                       // webhook subscriptions
/subscriptions/{id}                  // manage specific subscription
```

---

## Service Communications

```text
/admin/serviceAnnouncement/healthOverviews    // service health dashboard
/admin/serviceAnnouncement/issues             // service issues
/admin/serviceAnnouncement/messages           // message center
```

---

## Education (Schools, Classes, Students)

```text
/education/schools              // list schools
/education/classes              // list classes
/education/users                // education users
/education/users/{id}/assignments // assignments
```

---

## Additional Solutions

| Workload          | Example Endpoint                           |
| ----------------- | ------------------------------------------ |
| Bookings          | `/solutions/bookingBusinesses`             |
| Search            | `/search/query`                            |
| Insights          | `/me/insights/used`                        |
| External data     | `/external/connections`                    |
| Industry data     | `/external/industryData`                   |
| Threat assessment | `/informationProtection/threatAssessment`  |

---

## Schema & Directory Extensions

```text
/schemaExtensions                    // custom schema definitions
/directoryObjects                    // base directory objects
/directoryRoleTemplates              // available role templates
/applicationTemplates                // app gallery templates
```

---

## Role Management

```text
/roleManagement/directory/roleDefinitions     // custom & built-in roles
/roleManagement/directory/roleAssignments     // role assignments
/roleManagement/directory/roleEligibilitySchedules
/roleManagement/directory/roleAssignmentSchedules
```

---

### How to Use This Table

1. **Base URL:** prepend `https://graph.microsoft.com` to every path.
2. **Versioning:** swap `v1.0` with `beta` for preview functionality.
3. **Permissions:** each call requires delegated or app‐only scopes—see the individual docs (permissions reference).
4. **Authentication:** All endpoints require proper authentication using OAuth 2.0 bearer tokens.

> **Tip:** The list above covers the primary resource collections. For deep-nested child resources (attachments, channel tabs, etc.), consult the linked Microsoft Learn pages or the [OpenAPI description](https://learn.microsoft.com/en-us/graph/) in Graph Explorer.

> **Note:** Some endpoints marked may only be available in the beta version. Always check the official Microsoft Graph documentation for the most current availability status.

This markdown should drop directly into docs or code comments for quick lookup while building Microsoft Graph integrations.
