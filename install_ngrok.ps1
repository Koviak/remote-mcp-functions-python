# Install ngrok permanently on Windows
# This script downloads ngrok and adds it to the system PATH

$ngrokUrl = "https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-windows-amd64.zip"
$installPath = "C:\Tools\ngrok"
$zipPath = "$env:TEMP\ngrok.zip"

Write-Host "Installing ngrok permanently..." -ForegroundColor Blue

# Create installation directory
Write-Host "Creating installation directory: $installPath"
if (!(Test-Path -Path $installPath)) {
    New-Item -ItemType Directory -Path $installPath -Force | Out-Null
}

# Download ngrok
Write-Host "Downloading ngrok..."
try {
    Invoke-WebRequest -Uri $ngrokUrl -OutFile $zipPath -UseBasicParsing
    Write-Host "Download complete" -ForegroundColor Green
} catch {
    Write-Host "Failed to download ngrok: $_" -ForegroundColor Red
    exit 1
}

# Extract ngrok
Write-Host "Extracting ngrok..."
try {
    Expand-Archive -Path $zipPath -DestinationPath $installPath -Force
    Write-Host "Extraction complete" -ForegroundColor Green
} catch {
    Write-Host "Failed to extract ngrok: $_" -ForegroundColor Red
    exit 1
}

# Clean up zip file
Remove-Item -Path $zipPath -Force

# Add to PATH
Write-Host "Adding ngrok to system PATH..."
$currentPath = [Environment]::GetEnvironmentVariable("Path", [EnvironmentVariableTarget]::Machine)
if ($currentPath -notlike "*$installPath*") {
    try {
        $newPath = "$currentPath;$installPath"
        [Environment]::SetEnvironmentVariable("Path", $newPath, [EnvironmentVariableTarget]::Machine)
        Write-Host "Added to system PATH" -ForegroundColor Green
        Write-Host "You need to restart your terminal for PATH changes to take effect!" -ForegroundColor Yellow
    } catch {
        Write-Host "Failed to update PATH. Running as Administrator?" -ForegroundColor Red
        Write-Host "You can manually add this to your PATH: $installPath" -ForegroundColor Yellow
    }
} else {
    Write-Host "ngrok already in PATH" -ForegroundColor Green
}

# Update current session PATH
$env:Path = "$env:Path;$installPath"

# Test ngrok
Write-Host ""
Write-Host "Testing ngrok installation..."
try {
    & "$installPath\ngrok.exe" version
    Write-Host "ngrok installed successfully!" -ForegroundColor Green
} catch {
    Write-Host "ngrok test failed: $_" -ForegroundColor Red
}

Write-Host ""
Write-Host "Installation Summary:" -ForegroundColor Cyan
Write-Host "  - ngrok installed to: $installPath"
Write-Host "  - Added to system PATH"
Write-Host "  - Restart your terminal to use 'ngrok' command globally"
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Close and reopen your terminal"
Write-Host "  2. Run: ngrok config add-authtoken YOUR_AUTH_TOKEN"
Write-Host "  3. Run: ngrok http --domain=agency-swarm.ngrok.app 7071" 