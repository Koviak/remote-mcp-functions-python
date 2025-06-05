# Add ngrok to user PATH (doesn't require Administrator)

$installPath = "C:\Tools\ngrok"

Write-Host "Adding ngrok to USER PATH..." -ForegroundColor Blue

# Get current user PATH
$currentUserPath = [Environment]::GetEnvironmentVariable("Path", [EnvironmentVariableTarget]::User)

# Check if already in PATH
if ($currentUserPath -notlike "*$installPath*") {
    try {
        # Add to user PATH
        $newUserPath = "$currentUserPath;$installPath"
        [Environment]::SetEnvironmentVariable("Path", $newUserPath, [EnvironmentVariableTarget]::User)
        
        Write-Host "Successfully added ngrok to user PATH!" -ForegroundColor Green
        Write-Host "Please restart your terminal for the change to take effect." -ForegroundColor Yellow
    } catch {
        Write-Host "Failed to update user PATH: $_" -ForegroundColor Red
    }
} else {
    Write-Host "ngrok is already in your user PATH" -ForegroundColor Green
}

Write-Host ""
Write-Host "You can now use ngrok from any directory after restarting your terminal." -ForegroundColor Cyan
Write-Host "To start ngrok tunnel, run:" -ForegroundColor Yellow
Write-Host "  ngrok http --domain=agency-swarm.ngrok.app 7071" 