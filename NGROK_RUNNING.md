# ✅ ngrok is Running!

## Current Status

- **ngrok Process**: Running (PID: 89764)
- **Tunnel URL**: https://agency-swarm.ngrok.app
- **Forwarding to**: http://localhost:7071
- **Webhook Endpoint**: https://agency-swarm.ngrok.app/api/graph_webhook
- **Status**: ✅ WORKING (tested and confirmed)

## Quick Commands

### Check ngrok status
```bash
Get-Process -Name ngrok
```

### Test webhook endpoint
```bash
curl https://agency-swarm.ngrok.app/api/graph_webhook?validationToken=test
```

### Stop ngrok
```bash
Stop-Process -Name ngrok
```

### Restart ngrok (after terminal restart)
```bash
ngrok http --domain=agency-swarm.ngrok.app 7071
```

### View ngrok web interface
Open in browser: http://localhost:4040

## Important Notes

- ngrok is currently running in the background
- The tunnel will remain active until you stop it or close the terminal
- After restarting your terminal, you can use `ngrok` command directly (PATH is updated)
- Your auth token is saved in: `C:\Users\JoshuaKoviak\AppData\Local\ngrok\ngrok.yml`

## Your Services Are Ready! 🚀

1. **Redis**: Running on port 6379
2. **Function App**: Running on port 7071
3. **ngrok**: Tunneling to agency-swarm.ngrok.app
4. **Webhooks**: Accessible at https://agency-swarm.ngrok.app/api/graph_webhook

Everything is set up for MS Graph webhook integration! 