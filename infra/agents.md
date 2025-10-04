## Upstream Context
- [Root agents.md](../agents.md) - Remote MCP Functions mission, stack, runtime environment, and global workflow expectations
# infra subsystem guide

## Mission
- Provision Azure resources for the remote MCP Function App, networking, and RBAC dependencies. Align deployments with the architecture documented in `.cursor/rules/ms-mcp-system-architecture.mdc`.
- Keep infrastructure templates in sync with the service behaviour described in `.cursor/rules/module_Function_App.mdc`, `.cursor/rules/module_Webhook_System.mdc`, and `.cursor/rules/module_Start_Services.mdc`.

## Key files
- `main.bicep` - subscription-scope entry point that builds the resource group, storage, function plan, networking, and supporting identity. Parameters are defined in `main.parameters.json`.
- `app/api.bicep`, `app/rbac.bicep`, and `app/storage-PrivateEndpoint.bicep` - modularised deployments for the Function App, role assignments, and private endpoints. Update these when Azure bindings or managed identities change.
- `azure.yaml` and `abbreviations.json` - helper metadata used by automation to stamp consistent names.

## Deployment workflow
1. Log in with the Azure CLI: `az login` and set the subscription.
2. Validate changes: `az deployment sub what-if --name mcp-dev --location <region> --template-file infra/main.bicep --parameters @infra/main.parameters.json`.
3. Deploy: `az deployment sub create --name mcp-dev --location <region> --template-file infra/main.bicep --parameters @infra/main.parameters.json | tee ../.cursor/artifacts/infra-deploy.log`.
4. Record outputs (resource group, function app name, storage account) in the runbook and ensure `GRAPH_WEBHOOK_URL`, Redis endpoints, and credentials are updated in the application settings post-deploy.

## Configuration notes
- `environmentName` drives the short hash appended to resource names. Changing it will create a new resource set; coordinate with operations before updating.
- Keep parameter files free of secrets. Store credentials in Azure Key Vault or deployment pipelines and hydrate the Function App settings separately.
- RBAC assignments in `app/rbac.bicep` rely on service principal object IDs. Verify them whenever an identity is rotated.

## Verification
- After deployment, hit `/api/health/ready` on the new Function App and confirm Redis connectivity via `token_api_endpoints.py` health checks.
- Review Azure Monitor diagnostics for the function, storage, and networking resources. Align logging retention with the guidance in `.cursor/rules/module_Webhook_System.mdc` if webhook traffic flows through private endpoints.

## Maintenance
- Update this guide when templates change, new parameters are introduced, or deployment commands are adjusted.
- Capture any recurring deployment issues (policy blocks, quota limits) here with remediation steps so future runs remain deterministic.

