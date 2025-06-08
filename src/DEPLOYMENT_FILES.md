# Deployment Files for Annika-Planner Integration

## New Files to Deploy

These are the new files created for the integration:

### Core Integration Files
1. **`annika_task_adapter.py`** - Task format converter (REQUIRED)
2. **`planner_sync_service_v2.py`** - New sync service (REQUIRED)  
3. **`function_app_updated.py`** → rename to `function_app.py` (REQUIRED)

### Testing & Documentation
4. `test_task_conversion.py` - Testing utility (optional)
5. `inspect_redis_keys.py` - Debugging tool (optional)
6. `REDIS_KEY_CHANGES_SUMMARY.md` - Technical documentation
7. `QUICK_START_GUIDE.md` - Setup guide
8. `AUTOMATION_COMPLETE_GUIDE.md` - Full automation guide
9. `FINAL_SETUP_CHECKLIST.md` - Quick reference

## Modified Files

1. **`function_app.py`** - Replace with `function_app_updated.py`

## Configuration Updates

1. **`local.settings.json`** or **`.env`**:
   ```json
   "DEFAULT_PLANNER_PLAN_ID": "your-plan-id"
   ```

2. **`annika_task_adapter.py`** line 31:
   ```python
   USER_ID_MAP = {
       "your-microsoft-id": "Your Name",
   }
   ```

## Deployment Steps

### For Local Development:
```bash
# Copy new files to src directory
cp annika_task_adapter.py src/
cp planner_sync_service_v2.py src/
cp function_app_updated.py src/function_app.py

# Start the server
cd src
func start
```

### For Azure Deployment:
```bash
# Ensure all files are in src directory
# Deploy to Azure
func azure functionapp publish YOUR-FUNCTION-APP-NAME
```

## Files NOT Needed for Production

These can be excluded from production deployment:
- `test_task_conversion.py`
- `inspect_redis_keys.py`
- `planner_sync_service.py` (old version)
- All `.md` documentation files

## Environment Variables Required

For production, set these in Azure Function App settings:
- `DEFAULT_PLANNER_PLAN_ID`
- `REDIS_HOST` (if not localhost)
- `REDIS_PORT` (if not 6379)
- `REDIS_PASSWORD`
- All existing Azure AD credentials

That's all! Just these files and settings for full automation. 