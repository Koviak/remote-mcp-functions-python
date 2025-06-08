# Microsoft Graph Webhook Permissions Setup

## Required Azure AD Application Permissions

To enable webhook subscriptions for the V5 Planner Sync Service, you need to add the following permissions to your Azure AD application:

### Application Permissions (Admin Consent Required)

1. **Subscription.Read.All**
   - **Purpose**: Required to create and manage webhook subscriptions
   - **Description**: Read all webhook subscriptions
   - **Admin Consent**: Yes

2. **Group.Read.All** 
   - **Purpose**: Access group plans and tasks
   - **Description**: Read all groups
   - **Admin Consent**: Yes

3. **Tasks.ReadWrite** (if not already added)
   - **Purpose**: Read and write Planner tasks
   - **Description**: Create, read, update, and delete user's tasks and task lists
   - **Admin Consent**: No (but recommended as Application permission)

### How to Add Permissions

#### Option 1: Azure Portal (Recommended)

1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to **Azure Active Directory** > **App registrations**
3. Find your application (search for your `AZURE_CLIENT_ID`)
4. Click on **API permissions**
5. Click **Add a permission**
6. Select **Microsoft Graph**
7. Choose **Application permissions**
8. Search for and add:
   - `Subscription.Read.All`
   - `Group.Read.All`
   - `Tasks.ReadWrite` (if not present)
9. Click **Grant admin consent for [Your Organization]**

#### Option 2: PowerShell Script

```powershell
# Install required module if not present
Install-Module Microsoft.Graph -Scope CurrentUser

# Connect to Microsoft Graph
Connect-MgGraph -Scopes "Application.ReadWrite.All"

# Get your application
$appId = "YOUR_AZURE_CLIENT_ID"
$app = Get-MgApplication -Filter "appId eq '$appId'"

# Get Microsoft Graph service principal
$graphSP = Get-MgServicePrincipal -Filter "appId eq '00000003-0000-0000-c000-000000000000'"

# Required permissions
$requiredPermissions = @(
    "Subscription.Read.All",
    "Group.Read.All", 
    "Tasks.ReadWrite"
)

# Add permissions
foreach ($permission in $requiredPermissions) {
    $graphPermission = $graphSP.AppRoles | Where-Object { $_.Value -eq $permission }
    if ($graphPermission) {
        $appRole = @{
            Id = $graphPermission.Id
            Type = "Role"
        }
        
        Update-MgApplication -ApplicationId $app.Id -RequiredResourceAccess @{
            ResourceAppId = "00000003-0000-0000-c000-000000000000"
            ResourceAccess = @($appRole)
        }
        
        Write-Host "Added permission: $permission"
    }
}

# Grant admin consent (requires Global Admin)
# This step may need to be done manually in the portal
```

## Verification

After adding permissions, you can verify they're working by:

1. **Test webhook creation**:
   ```bash
   cd src
   python test_webhook_permissions.py
   ```

2. **Check the V5 sync service logs**:
   - Look for "✅ Webhook setup completed" instead of 403 errors
   - Should see "Created webhook subscription: [subscription-id]"

3. **Manual API test**:
   ```bash
   # Get an app-only token and test subscription creation
   curl -X POST "https://graph.microsoft.com/v1.0/subscriptions" \
     -H "Authorization: Bearer YOUR_APP_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "changeType": "created,updated,deleted",
       "notificationUrl": "https://agency-swarm.ngrok.app/api/graph_webhook",
       "resource": "/planner/tasks",
       "expirationDateTime": "2025-06-09T16:00:00.000Z",
       "clientState": "annika_planner_sync_v5"
     }'
   ```

## Common Issues

### 403 Forbidden Error
- **Cause**: Missing `Subscription.Read.All` permission
- **Solution**: Add the permission and grant admin consent

### 400 Bad Request - Invalid notificationUrl
- **Cause**: ngrok not running or webhook URL not accessible
- **Solution**: Ensure ngrok is running and URL is publicly accessible

### 400 Bad Request - Invalid resource
- **Cause**: Application doesn't have permission to access the resource
- **Solution**: Add `Group.Read.All` and `Tasks.ReadWrite` permissions

## Security Notes

- **Application permissions** require admin consent but allow the app to work without a signed-in user
- **Delegated permissions** work with a signed-in user but may have limitations
- For production, consider using **certificate-based authentication** instead of client secrets
- Webhook subscriptions expire after 24-48 hours and need renewal

## Next Steps

Once permissions are added:

1. Restart the V5 sync service
2. Check logs for successful webhook creation
3. Test by creating/updating tasks in Planner
4. Verify notifications are received in Function App logs 