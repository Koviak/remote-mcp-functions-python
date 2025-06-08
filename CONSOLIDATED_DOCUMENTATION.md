# Remote MCP Functions with Microsoft Graph Integration

## 🎯 Project Overview

This project provides a remote MCP (Model Context Protocol) server running on Azure Functions with comprehensive Microsoft Graph integration. It enables autonomous agents to interact with Microsoft 365 services including Planner, Outlook, and Teams through a Redis-first architecture for optimal performance.

## 🏗️ Architecture

### Core Components

1. **Azure Function App** (`src/function_app.py`)
   - MCP server with tool triggers
   - HTTP endpoints for agent interactions
   - Authentication and token management

2. **Webhook-Driven Planner Sync V5** (`src/planner_sync_service_v5.py`)
   - Real-time bidirectional sync between Redis and MS Planner
   - Webhook-driven architecture (95% reduction in API calls)
   - Intelligent conflict resolution and rate limiting

3. **Redis-First Architecture**
   - Primary storage for agent operations (microsecond response times)
   - MS Planner as human-friendly view with background sync
   - Pub/sub for real-time inter-agent communication

4. **Comprehensive HTTP Endpoints** (`src/http_endpoints.py`)
   - 4000+ lines of MS Graph API wrappers
   - Cached metadata management
   - Delegated and app-only authentication support

### Data Flow

```
Agent → Redis → Other Agents (instant, 0.1ms)
         ↓
    Event-driven → Sync Service → MS Planner (real-time webhook)
                        ↓
                   Webhook ← MS Planner (instant notifications)
```

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Azure Functions Core Tools >= 4.0.7030
- Docker Desktop (for Redis)
- ngrok (permanently installed at `C:\Tools\ngrok\ngrok.exe`)

### 1. Environment Setup

Create `.env` file in `src/` directory:
```env
# Azure AD App Registration
AZURE_CLIENT_ID=your-client-id
AZURE_CLIENT_SECRET=your-client-secret
AZURE_TENANT_ID=your-tenant-id

# Agent Authentication
AGENT_USER_NAME=your-username
AGENT_PASSWORD=your-password
AGENT_USER_ID=your-user-id

# Planner Configuration
DEFAULT_PLANNER_PLAN_ID=your-default-plan-id

# Redis Configuration
REDIS_PASSWORD=password
REDIS_HOST=localhost
REDIS_PORT=6379

# Webhook Configuration
WEBHOOK_DOMAIN=agency-swarm.ngrok.app
```

### 2. Start Services

```bash
# Option 1: Start all services automatically
cd src
python start_all_services.py

# Option 2: Manual startup
# Terminal 1 - Start ngrok
ngrok http --domain=agency-swarm.ngrok.app 7071

# Terminal 2 - Start Function App
cd src
func start

# Terminal 3 - Start sync service
cd src
python planner_sync_service_v5.py
```

### 3. Test Integration

```python
import requests

# Create a task via agent API
task = {
    "title": "Test Agent Task",
    "planId": "your-plan-id"
}

response = requests.post(
    "http://localhost:7071/api/agent/tasks",
    json=task
)
print(response.json())
```

## 🔧 Configuration

### Redis Keys Structure

```
# Task Management
annika:tasks:{id}                    # Primary task storage
annika:planner:id_map:{id}          # Bidirectional ID mappings
annika:planner:etag:{id}            # ETag storage for updates

# Metadata Caching (24-hour TTL)
annika:graph:users:{id}             # User metadata
annika:graph:groups:{id}            # Group metadata  
annika:graph:plans:{id}             # Plan metadata

# Sync Service
annika:sync:log                     # Transaction log
annika:sync:pending                 # Pending operations
annika:sync:webhook_status          # Webhook subscription status

# Pub/Sub Channels
annika:tasks:updates                # Real-time task notifications
```

### Authentication Modes

1. **App-Only Authentication** (MCP Tools)
   - Uses `ClientSecretCredential`
   - For autonomous agent operations
   - Configured via `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `AZURE_TENANT_ID`

2. **Delegated Authentication** (HTTP Endpoints)
   - Uses `OnBehalfOfCredential` 
   - For user-context operations
   - Requires built-in authentication enabled

## 📡 API Endpoints

### Agent Task Management

```bash
# Create task
POST /api/agent/tasks
{
  "title": "Task title",
  "planId": "plan-id",
  "bucketId": "bucket-id" # optional
}

# Get task
GET /api/agent/tasks/{taskId}

# Update task
PATCH /api/agent/tasks/{taskId}
{
  "title": "Updated title",
  "percentComplete": 50
}

# Delete task
DELETE /api/agent/tasks/{taskId}
```

### Metadata Access

```bash
# Get cached metadata (2000-4000x faster than direct API)
GET /api/metadata?type=user&id={userId}
GET /api/metadata?type=group&id={groupId}
GET /api/metadata?type=plan&id={planId}
GET /api/metadata?type=task&id={taskId}
```

### Health Monitoring

```bash
# Sync service health
GET /api/sync/health

# Webhook handler health
GET /api/webhook/health

# Token status
GET /api/tokens/status
```

## 🔄 Sync Service V5 Features

### Webhook-Driven Architecture
- **Real-time sync**: Instant notifications from MS Graph
- **95% API reduction**: Only calls on actual changes
- **Intelligent batching**: Groups operations for efficiency

### Conflict Resolution
- **Timestamp-based**: Last-write-wins with 30-second grace period
- **Human preference**: Planner changes preferred in ties
- **Transaction logging**: All conflicts logged for review

### Rate Limiting & Reliability
- **Exponential backoff**: 2^failures seconds (max 5 minutes)
- **Circuit breaker**: Automatic failure recovery
- **Health monitoring**: Comprehensive metrics and alerts

### Performance Metrics

| Metric | V4 (Polling) | V5 (Webhook) | Improvement |
|--------|--------------|--------------|-------------|
| API Calls | 100s every 30s | Only on changes | 95%+ reduction |
| Sync Latency | 0-30 seconds | Near real-time | ~30x faster |
| Rate Limit Risk | Very High | Very Low | Eliminated |
| Resource Usage | High | Low | 90%+ reduction |

## 🛠️ Development

### Local Development Setup

1. **Start Redis Container**
   ```bash
   docker run -d --name redis -p 6379:6379 redis:latest redis-server --requirepass password
   ```

2. **Install Dependencies**
   ```bash
   cd src
   pip install -r requirements.txt
   ```

3. **Configure Environment**
   - Copy `.env.example` to `.env`
   - Update with your Azure AD app details
   - Set agent credentials

4. **Start Development Services**
   ```bash
   python start_all_services.py
   ```

### Testing

```bash
# Run all tests
cd src
python -m pytest Tests/

# Test specific components
python test_v5_sync.py
python Tests/test_agent_auth.py
python Tests/test_delegated_access.py
```

### Debugging

```bash
# Enable debug logging
export PYTHONPATH=src
export AZURE_FUNCTIONS_ENVIRONMENT=Development

# View sync logs
redis-cli -a password LRANGE annika:sync:log 0 10

# View webhook logs  
redis-cli -a password LRANGE annika:webhook:log 0 10

# Monitor task updates
redis-cli -a password SUBSCRIBE annika:tasks:updates
```

## 🔐 Security

### Authentication Flow
1. Agent authenticates with username/password
2. Token stored securely in Redis with TTL
3. Automatic token refresh before expiration
4. All API calls use cached tokens

### Webhook Security
- HTTPS-only webhook endpoints
- Microsoft Graph signature validation
- Domain validation via ngrok

### Redis Security
- Password-protected Redis instance
- Encrypted token storage
- TTL-based token expiration

## 📊 Monitoring & Observability

### Health Checks
- Sync service status and metrics
- Webhook subscription health
- Redis connection status
- Token validity and refresh status

### Logging
- Structured logging with correlation IDs
- Transaction logs for all sync operations
- Webhook activity logs
- Performance metrics

### Alerts
- Failed sync operations
- Rate limiting events
- Authentication failures
- Webhook subscription failures

## 🚀 Deployment

### Azure Deployment

```bash
# Deploy to Azure
azd up

# Optional: Enable VNet
azd env set VNET_ENABLED true
azd up
```

### Production Configuration

1. **Environment Variables**
   - Set all required environment variables in Azure Function App settings
   - Configure Redis connection string
   - Set webhook domain to production URL

2. **Scaling**
   - Configure Function App scaling rules
   - Set up Redis cluster for high availability
   - Configure load balancing for webhook endpoints

3. **Monitoring**
   - Enable Application Insights
   - Set up alerts for critical failures
   - Configure log retention policies

## 🔧 Troubleshooting

### Common Issues

#### Function App Won't Start
- Ensure running from `src` directory
- Check port 7071 is available
- Verify all dependencies installed

#### Authentication Failures
- Verify Azure AD app configuration
- Check "Allow public client flows" is enabled
- Confirm user has necessary permissions

#### Sync Service Issues
- Check Redis connection
- Verify webhook subscriptions are active
- Monitor rate limiting status

#### Webhook Problems
- Ensure ngrok is running with correct domain
- Verify Function App is accessible
- Check webhook subscription validation

### Debug Commands

```bash
# Test authentication
python -c "from agent_auth_manager import get_agent_token; print(get_agent_token())"

# Test Redis connection
redis-cli -h localhost -p 6379 -a password ping

# Test Function App
curl http://localhost:7071/api/hello

# Test webhook endpoint
curl -X POST http://localhost:7071/api/graph_webhook?validationToken=test
```

## 📚 Additional Resources

### Microsoft Graph Documentation
- [Graph API Reference](https://docs.microsoft.com/en-us/graph/api/overview)
- [Planner API](https://docs.microsoft.com/en-us/graph/api/resources/planner-overview)
- [Webhook Subscriptions](https://docs.microsoft.com/en-us/graph/webhooks)

### Azure Functions
- [Functions Documentation](https://docs.microsoft.com/en-us/azure/azure-functions/)
- [MCP Extension](https://github.com/microsoft/mcp)

### Redis
- [Redis Documentation](https://redis.io/documentation)
- [Redis JSON](https://redis.io/docs/stack/json/)

## 🎯 Best Practices

### For Agents
1. **Use Redis-first**: Always read/write to Redis, never call MS Graph directly
2. **Subscribe to pub/sub**: Listen for real-time task updates
3. **Handle errors gracefully**: Implement retry logic with exponential backoff
4. **Cache metadata**: Use cached user/group/plan data for performance

### For Development
1. **Test locally first**: Use local development setup before deploying
2. **Monitor health endpoints**: Regularly check service health
3. **Review logs**: Monitor sync and webhook logs for issues
4. **Update documentation**: Keep this file updated with changes

### For Production
1. **Monitor rate limits**: Watch for Graph API throttling
2. **Scale appropriately**: Configure Function App scaling rules
3. **Backup Redis data**: Regular backups of task and mapping data
4. **Security updates**: Keep all dependencies updated

---

*This documentation consolidates information from multiple sources and represents the current state of the Remote MCP Functions project with Microsoft Graph integration.* 