# ngrok Installation Summary

## ✅ Installation Complete!

ngrok has been successfully installed on your system:

- **Location**: `C:\Tools\ngrok\ngrok.exe`
- **Version**: 3.22.1
- **Added to PATH**: User PATH (will work after terminal restart)

## 🚀 Using ngrok

### For Current Session
ngrok is available immediately in this terminal:
```bash
ngrok version
ngrok http --domain=agency-swarm.ngrok.app 7071
```

### For Future Sessions
After restarting your terminal, ngrok will be available globally from any directory.

## 🔑 Important: Authentication

If you see an error about authentication when running ngrok, you may need to:

1. **Sign up for a free ngrok account** at https://ngrok.com
2. **Get your auth token** from https://dashboard.ngrok.com/auth
3. **Add the auth token**:
   ```bash
   ngrok config add-authtoken YOUR_AUTH_TOKEN_HERE
   ```

## 📋 Quick Start Commands

1. **Start Function App** (in src directory):
   ```bash
   cd src
   func start
   ```

2. **Start ngrok tunnel** (in another terminal):
   ```bash
   ngrok http --domain=agency-swarm.ngrok.app 7071
   ```

3. **Verify webhook endpoint**:
   - Your webhook URL: `https://agency-swarm.ngrok.app/api/graph_webhook`
   - Test it: `curl https://agency-swarm.ngrok.app/api/graph_webhook?validationToken=test`

## 🛠️ Troubleshooting

### "Failed to add to system PATH"
- This is normal - system PATH requires admin privileges
- User PATH was successfully updated (no admin needed)
- Just restart your terminal

### "ngrok not found" after restart
- The user PATH update should persist
- If not, manually add `C:\Tools\ngrok` to your PATH in System Settings

### Domain errors
- Make sure you're using the exact domain: `agency-swarm.ngrok.app`
- This is a reserved domain that should work with your account

## 📁 Installation Files

- `install_ngrok.ps1` - Main installation script
- `add_ngrok_to_user_path.ps1` - PATH update script (no admin needed)
- `C:\Tools\ngrok\` - ngrok installation directory

ngrok is now ready to use for exposing your local Function App to the internet! 