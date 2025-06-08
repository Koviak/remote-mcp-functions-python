# Planner Sync Setup Guide

## Current Status

✅ **Authentication is working** - Token acquired for user "Annika Hansen"  
❌ **Plan ID not configured** - Sync service needs to know which Planner plan to use

## Quick Fix

### Step 1: Find Your Plan ID

Run this command to list your available Planner plans:

```powershell
python get_planner_plans.py
```

This will:
- Show all your Microsoft Planner plans
- Display their IDs
- Let you select one as default

### Step 2: Configure Plan ID

You have three options:

**Option A: Use the script's interactive setup** (Recommended)
- When prompted, type `y` and select your plan
- The script will save it to Redis automatically

**Option B: Add to local.settings.json**
```json
{
  "Values": {
    "DEFAULT_PLANNER_PLAN_ID": "your-plan-id-here",
    // ... other settings
  }
}
```

**Option C: Set environment variable**
```powershell
$env:DEFAULT_PLANNER_PLAN_ID = "your-plan-id-here"
```

### Step 3: Restart Services

```powershell
# Stop current services (Ctrl+C)
# Then restart:
python src/start_all_services.py
```

## Troubleshooting

### No Plans Found?
1. Go to https://planner.cloud.microsoft
2. Create a new plan (e.g., "Annika Tasks")
3. Run `get_planner_plans.py` again

### Still Getting Errors?
1. Run `python test_auth_config.py` to verify authentication
2. Check that the user has access to Planner
3. Ensure the Azure AD app has `Tasks.ReadWrite` permission

## What Happens After Setup

Once configured, the sync service will:
- Create all 88 existing Annika tasks in your selected Planner plan
- Keep tasks synchronized bidirectionally
- Update tasks in real-time as changes occur

## Current Error Explanation

The error "No default plan ID configured" occurs because:
- MS Planner requires tasks to belong to a specific plan
- The sync service doesn't know which plan to use
- This is a one-time configuration requirement 