# Gmail API Setup Guide

This guide will help you set up Gmail API for real-time email push notifications.

## 🚀 Quick Start (History-Based - No Pub/Sub Required)

This is the **simplest approach** that works immediately without Google Cloud Pub/Sub setup.

### Step 1: Install Dependencies

```bash
cd Backend
pip install -r requirements.txt
```

### Step 2: Add Credentials to .env

Add these lines to your `.env` file:

```env
# Gmail API Settings
GMAIL_CLIENT_ID=71541963261-oi9a4auii7b2lhpbsub7pt3q0rrpfkt7.apps.googleusercontent.com
GMAIL_CLIENT_SECRET=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
GMAIL_USE_API=true
```

### Step 3: First-Time OAuth Authentication

When you start the backend, it will:
1. Open a browser window for Google OAuth
2. Ask you to sign in with your Gmail account
3. Grant permissions to read emails
4. Save the token for future use

**The token is saved in:** `Backend/token_{your_email}.pickle`

### Step 4: Test It

```bash
# Check authentication status
curl http://localhost:8000/api/gmail/auth

# The email agent will automatically use Gmail API if enabled
```

---

## 🔔 Advanced: Full Push Notifications (Pub/Sub)

For **true push notifications** (no polling), you need Google Cloud Pub/Sub:

### Prerequisites

1. **Google Cloud Project** with:
   - Gmail API enabled
   - Pub/Sub API enabled
   - Service account or OAuth 2.0 credentials

### Step 1: Create Pub/Sub Topic

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Navigate to **Pub/Sub** → **Topics**
3. Create a new topic (e.g., `gmail-notifications`)
4. Note the full topic name: `projects/YOUR_PROJECT_ID/topics/gmail-notifications`

### Step 2: Create Pub/Sub Subscription (Webhook)

1. In Pub/Sub, go to **Subscriptions**
2. Create a new subscription
3. Choose **Push** delivery type
4. Set **Endpoint URL** to your webhook:
   ```
   https://your-domain.com/api/gmail/webhook
   ```
   
   **For local testing, use ngrok:**
   ```bash
   ngrok http 8000
   # Copy the HTTPS URL, e.g., https://abc123.ngrok.io
   # Use: https://abc123.ngrok.io/api/gmail/webhook
   ```

### Step 3: Grant Permissions

Grant Gmail permission to publish to your Pub/Sub topic:

```bash
# In Google Cloud Console, go to IAM & Admin
# Add this service account with Pub/Sub Publisher role:
gmail-api-push@system.gserviceaccount.com
```

### Step 4: Configure .env

Add the Pub/Sub topic to `.env`:

```env
GMAIL_PUBSUB_TOPIC=projects/YOUR_PROJECT_ID/topics/gmail-notifications
```

### Step 5: Start Watch

```bash
# Register the watch (valid for 7 days)
curl -X POST http://localhost:8000/api/gmail/watch
```

---

## 📊 How It Works

### History-Based (Current Implementation)

1. **On startup:** Gmail API client authenticates and gets `historyId`
2. **Every check:** Queries Gmail API for changes since last `historyId`
3. **New emails:** Fetches full message details
4. **Advantage:** No Pub/Sub setup needed, works immediately
5. **Latency:** ~1-2 seconds (depends on polling interval)

### Pub/Sub Push (Advanced)

1. **Gmail detects new email**
2. **Gmail publishes to Pub/Sub topic**
3. **Pub/Sub sends webhook to your endpoint**
4. **Your backend receives notification instantly**
5. **Backend fetches email via Gmail API**
6. **Advantage:** True real-time (instant notifications)
7. **Latency:** < 1 second

---

## 🔧 API Endpoints

### Check Authentication Status
```bash
GET /api/gmail/auth
```

### Start Gmail Watch (Pub/Sub)
```bash
POST /api/gmail/watch
```

### Webhook (Pub/Sub notifications)
```bash
POST /api/gmail/webhook
# Called automatically by Google Pub/Sub
```

---

## 🛠️ Troubleshooting

### "Authentication failed"
- Check `GMAIL_CLIENT_ID` and `GMAIL_CLIENT_SECRET` in `.env`
- Delete `token_*.pickle` files and re-authenticate
- Make sure OAuth consent screen is configured in Google Cloud

### "History ID expired"
- This is normal - the client automatically resets
- Emails will be fetched on next check

### "Watch registration failed"
- Check `GMAIL_PUBSUB_TOPIC` is correctly formatted
- Verify Pub/Sub topic exists and has proper permissions
- Topic format: `projects/PROJECT_ID/topics/TOPIC_NAME`

---

## 📝 Notes

- **History-based approach** works without Pub/Sub (simpler)
- **Pub/Sub push** requires HTTPS endpoint (use ngrok for local testing)
- **Watch expires** after 7 days (need to re-register)
- **Token is saved locally** - no need to re-authenticate unless revoked

---

## ✅ Current Status

✅ Gmail API client implemented  
✅ OAuth 2.0 authentication working  
✅ History-based change detection  
✅ Webhook endpoint ready for Pub/Sub  
✅ Integrated with existing email agent  

**Add your credentials to `.env` and restart the backend!** 🚀

