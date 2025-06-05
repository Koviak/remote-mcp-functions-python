# Add ngrok to PowerShell profile for permanent access
# This ensures ngrok works in all future PowerShell sessions

$profileContent = @'

# ngrok path
$env:Path = "$env:Path;C:\Tools\ngrok"

'@

# Check if profile exists
if (!(Test-Path -Path $PROFILE)) {
    # Create profile if it doesn't exist
    New-Item -ItemType File -Path $PROFILE -Force | Out-Null
    Write-Host "Created PowerShell profile at: $PROFILE" -ForegroundColor Green
}

# Check if ngrok is already in profile
$currentProfile = Get-Content $PROFILE -Raw
if ($currentProfile -notlike "*ngrok*") {
    # Add ngrok to profile
    Add-Content -Path $PROFILE -Value $profileContent
    Write-Host "✅ Added ngrok to PowerShell profile!" -ForegroundColor Green
    Write-Host "ngrok will be available in all future PowerShell sessions." -ForegroundColor Yellow
} else {
    Write-Host "ngrok is already in your PowerShell profile." -ForegroundColor Cyan
}

Write-Host ""
Write-Host "To use ngrok immediately in this session, run:" -ForegroundColor Yellow
Write-Host "  . .\ngrok-alias.ps1" -ForegroundColor White
Write-Host ""
Write-Host "Or simply close ALL PowerShell/Terminal windows and reopen." -ForegroundColor Yellow 