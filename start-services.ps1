# Start all services for remote-mcp-functions-python
Write-Host "🚀 Starting all services..." -ForegroundColor Green

# Change to src directory and run the startup script
Set-Location src
python start_all_services.py

# Note: If you prefer to run services separately:
# 1. In terminal 1: cd src; func start
# 2. In terminal 2: cd src; python planner_sync_service.py 