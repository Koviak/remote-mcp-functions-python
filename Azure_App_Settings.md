# Azure App Settings (Agency-Swarm)

This document captures the settings observed from the provided Azure Portal screenshots for the app “Agency-Swarm”.

## Identifiers
- Application (client) ID: `fd79a94d-f572-4439-bba2-6465e0c40122`
- Tenant ID: `cb629dfe-9f7b-497f-b0d2-502dd53d8227` (in SAML/WS-Fed endpoints)
- Publisher domain: `koviakbuilt.com`

## Endpoints (as shown)
- Authority URL (organizations): `https://login.microsoftonline.com/organizations`
- Authority URL (any org directory): `https://login.microsoftonline.com/organizations`
- Authority URL (common): `https://login.microsoftonline.com/common`
- Authority URL (consumers): `https://login.microsoftonline.com/consumers`
- OAuth 2.0 authorize (v2.0): `https://login.microsoftonline.com/organizations/oauth2/v2.0/authorize`
- OAuth 2.0 token (v2.0): `https://login.microsoftonline.com/organizations/oauth2/v2.0/token`
- OAuth 2.0 authorize (v1.0): `https://login.microsoftonline.com/organizations/oauth2/authorize`
- OAuth 2.0 token (v1.0): `https://login.microsoftonline.com/organizations/oauth2/token`
- SAML-P sign‑on endpoint: `https://login.microsoftonline.com/cb629dfe-9f7b-497f-b0d2-502dd53d8227/saml2`
- SAML-P sign‑out endpoint: `https://login.microsoftonline.com/cb629dfe-9f7b-497f-b0d2-502dd53d8227/saml2`
- WS‑Federation sign‑on endpoint: `https://login.microsoftonline.com/cb629dfe-9f7b-497f-b0d2-502dd53d8227/wsfed`
- Federation metadata document: `https://login.microsoftonline.com/cb629dfe-9f7b-497f-b0d2-502dd53d8227/federationmetadata/2007-06/federationmetadata.xml`
- OpenID Connect metadata (v2.0): `https://login.microsoftonline.com/organizations/v2.0/.well-known/openid-configuration`
- Microsoft Graph API endpoint: `https://graph.microsoft.com`

## Branding & Properties
- Name: `Agency-Swarm`
- Publisher domain: `koviakbuilt.com`
- Terms of service URL: not set
- Privacy statement URL: not set
- Publisher verification: not verified

## Enterprise Application (Service Principal) Properties
- Enabled for users to sign in: `Yes`
- Assignment required?: (appears) `Yes`
- Visible to users?: (appears) `Yes`

## Authentication
- Platform: Web
  - Redirect URIs:
    - `http://localhost:8000/callback`
    - `https://localhost/myapp`
- Implicit grant and hybrid flows:
  - Access tokens (implicit): enabled (checked)
  - ID tokens (implicit/hybrid): enabled (checked)
- Supported account types: `Accounts in any organizational directory (Any Microsoft Entra ID tenant - Multitenant)`
- Advanced settings:
  - Allow public client flows: `Yes`
  - Enabled mobile/desktop flows shown: ROPC (app collects plaintext password), Device Code Flow, Windows Integrated Auth

## Expose an API
- No custom scopes defined
- No authorized client applications

## Integration Assistant (Summary)
- Configure API permissions: Complete
- Configure a valid credential: Complete
- Use certificate credentials instead of password credentials (client secrets): Action required
- Assign owners: Complete
- Provide links to Terms of service and Privacy statement: Action required
- Ensure users can consent by becoming a verified publisher: Action required
- Discouraged: “If you are using authorization code flow, disable the implicit grant settings” – Action required

## User (Agent)
- User: `Annika Hansen (annika@reddypros.com)`
- Status: Enabled
- Group memberships: 5
- Applications: 2
- Assigned roles: 36
- Assigned licenses: 3

---

## Recommendations / Potential Misconfigurations

1) Admin consent for delegated scopes (ROPC) – required
   - Current delegated token requests are failing with `AADSTS65001: consent_required`.
   - Ensure tenant admin consent is granted for the exact delegated scopes used by agent flows (e.g., `openid profile offline_access`, `User.Read`, `Mail.Read`, `Mail.ReadWrite`, `Mail.Send`, `Calendars.Read` or `Calendars.ReadWrite`, `Files.Read.All` or `Files.ReadWrite.All`, `Chat.Read`, `Chat.ReadWrite`, `Tasks.ReadWrite`).

2) Conditional Access / MFA – ROPC cannot satisfy MFA
   - Exempt the agent user and/or this application from MFA or any CA policy that requires interactive sign‑in, otherwise ROPC will fail even with consent.

3) Assignment required? (Enterprise App) – may block access
   - If “Assignment required?” is `Yes`, then the agent user must be explicitly assigned to the Enterprise Application.
   - If you want any licensed user to sign in via ROPC without explicit assignment, set this to `No`.

4) Implicit grant toggles – recommended to disable unless needed
   - Implicit Access token and ID token are enabled; the Integration Assistant flags this as discouraged unless you use implicit/hybrid flows. ROPC and auth‑code w/PKCE do not need them. Consider unchecking both.

5) Terms of Service / Privacy links – add to Branding & properties
   - Integration Assistant shows “Action required”. Add URLs to reduce consent friction and warnings.

6) Publisher verification – recommended for multitenant apps
   - Verification improves trust and may reduce consent friction in cross‑tenant scenarios.

7) Expose an API – no custom scopes needed
   - This is acceptable since the app isn’t acting as a protected resource. No action required unless you plan to expose your own API scopes.

8) Endpoints usage – use tenant‑scoped v2.0 token URL for ROPC
   - Continue using `https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token` for ROPC and backend token flows and `https://graph.microsoft.com` as the resource.

9) Redirect URIs
   - The listed web redirect URIs are not used by ROPC. They are harmless, but you can prune or keep them for interactive flows.

10) Prefer certificate credentials for daemon scenarios
   - Integration Assistant recommends using certificates over client secrets for better security posture.


