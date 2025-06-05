# Quick fix: Add ngrok alias to current session
# Run this in any terminal where ngrok isn't recognized

# Add ngrok to current session PATH
$env:Path = "$env:Path;C:\Tools\ngrok"

# Create an alias as backup
Set-Alias -Name ngrok -Value "C:\Tools\ngrok\ngrok.exe"

Write-Host "✅ ngrok is now available in this terminal!" -ForegroundColor Green
Write-Host "You can now run: ngrok http --domain=agency-swarm.ngrok.app 7071" -ForegroundColor Yellow 