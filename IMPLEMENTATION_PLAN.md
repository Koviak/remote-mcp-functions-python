# Implementation Plan for Delegated Access (OBO)

1. **Enable Built-in Authentication**
   - Deploy the function app with App Service authentication enabled (or behind API Management).
   - Configure Azure AD as the identity provider so the user signs in only once.

2. **Register Azure AD Application**
   - Register a confidential client in Azure AD with delegated permissions to the downstream API (e.g. Microsoft Graph).
   - Record the client ID, tenant ID and client secret/certificate for use by the function.

3. **Add Dependencies and Settings**
   - Add `azure-identity` to `src/requirements.txt`.
   - Add new settings in `src/local.settings.json` to hold `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_CLIENT_SECRET` and `DOWNSTREAM_API_SCOPE`.

4. **Modify Function Authentication Level**
   - Change `function_app.py` to use `func.AuthLevel.ANONYMOUS` so built-in auth handles authentication.

5. **Implement OBO Logic**
   - In `function_app.py`, use `OnBehalfOfCredential` from `azure.identity` to exchange the incoming user token (available via built-in auth header `X-MS-TOKEN-AAD-ACCESS-TOKEN`) for a token to call the downstream API.
   - Demonstrate acquiring the delegated token in one of the existing functions (e.g., `get_snippet`) and log a message showing it was obtained.

6. **Update README**
   - Document the new configuration steps for built-in auth and OBO usage.
   - Show the new environment variables and a sample code snippet using `OnBehalfOfCredential`.

