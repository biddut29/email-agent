# 🔐 Email Agent Configuration Guide

Your Email Agent now uses a **`.env` file** for secure credential management!

## ✅ What Was Changed

1. ✅ Created `Backend/.env` - Your private credentials (DO NOT COMMIT)
2. ✅ Created `Backend/.env.example` - Template for others
3. ✅ Updated `Backend/config.py` - Now reads from `.env` file
4. ✅ Updated `.gitignore` - Protects your `.env` file

## 📝 How to Configure

### Option 1: Edit .env File Directly (Recommended)

Open `Backend/.env` and update your credentials:

```bash
# Backend/.env
EMAIL_ADDRESS=your-email@gmail.com
EMAIL_PASSWORD=your-16-char-app-password

AZURE_OPENAI_KEY=your-azure-key-here
```

### Option 2: Use Terminal

```bash
cd "Backend"
nano .env
# or
code .env
```

## 🔑 Getting Gmail App Password

### Step-by-Step:

1. **Enable 2FA**
   - Go to: https://myaccount.google.com/security
   - Enable 2-Step Verification

2. **Create App Password**
   - Go to: https://myaccount.google.com/apppasswords
   - App: Mail
   - Device: Other (Email Agent)
   - Copy the 16-character password

3. **Update .env**
   ```bash
   EMAIL_ADDRESS=yourname@gmail.com
   EMAIL_PASSWORD=abcdefghijklmnop  # paste here, remove spaces
   ```

## 📁 File Structure

```
Backend/
├── .env              ← Your PRIVATE credentials (gitignored)
├── .env.example      ← Template for sharing
├── config.py         ← Reads from .env
└── .gitignore        ← Excludes .env from git
```

## 🛡️ Security Benefits

### Before (❌ Not Secure):
- Credentials hardcoded in `config.py`
- Could accidentally commit to git
- Difficult to share with team

### After (✅ Secure):
- Credentials in `.env` (never committed)
- Easy to change without touching code
- `.env.example` for sharing configuration structure
- Protected by `.gitignore`

## 🔄 How It Works

```python
# config.py now does this:
from dotenv import load_dotenv
import os

load_dotenv()  # Loads .env file

EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS", "default@gmail.com")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
```

## 📋 Available Settings

| Variable | Description | Example |
|----------|-------------|---------|
| `EMAIL_ADDRESS` | Your Gmail address | `yourname@gmail.com` |
| `EMAIL_PASSWORD` | Gmail App Password | `abcdefghijklmnop` |
| `AZURE_OPENAI_KEY` | Azure OpenAI API Key | `EU8IZTMx...` |
| `AZURE_OPENAI_ENDPOINT` | Azure endpoint URL | `https://...` |
| `AUTO_RESPOND` | Enable auto-replies | `True` or `False` |
| `DRAFT_MODE` | Create drafts only | `True` or `False` |
| `MAX_EMAILS_TO_PROCESS` | Email batch size | `10` |

## 🚀 Testing Your Configuration

1. **Update .env** with your credentials
2. **Restart the backend** (it auto-reloads)
3. **Check terminal** for connection status:
   ```
   ✓ Connected to your-email@gmail.com
   ✓ Azure OpenAI client initialized
   ```

## 🆘 Troubleshooting

### Problem: "Connection Failed"
**Solution:** Check your App Password in `.env`
```bash
cd Backend
cat .env | grep EMAIL_PASSWORD
```

### Problem: "Azure OpenAI Error"
**Solution:** Verify Azure credentials in `.env`
```bash
cd Backend
cat .env | grep AZURE_OPENAI_KEY
```

### Problem: "Module not found: dotenv"
**Solution:** Install python-dotenv
```bash
cd Backend
pip install python-dotenv
```

## 🔄 Updating Configuration

### Update Email Account:
```bash
cd Backend
nano .env
# Change EMAIL_ADDRESS and EMAIL_PASSWORD
# Save and exit (Ctrl+X, Y, Enter)
```

### Update AI Settings:
```bash
cd Backend
nano .env
# Change AZURE_OPENAI_* settings
# Save and exit
```

**Note:** Server auto-reloads when you save `.env`!

## 📤 Sharing with Team

When sharing this project:

1. ✅ **Include:** `.env.example`
2. ❌ **Never include:** `.env`

Team members should:
```bash
cd Backend
cp .env.example .env
nano .env  # Add their credentials
```

## 🔒 Security Checklist

- [x] `.env` file is in `.gitignore`
- [x] Never commit `.env` to git
- [x] Use App Password, not Gmail password
- [x] Keep `.env.example` updated (without real credentials)
- [x] Rotate credentials if accidentally exposed

## 🎉 You're All Set!

Your configuration is now secure and easy to manage! Just edit `Backend/.env` whenever you need to update credentials.

**Current Status:**
- ✅ `.env` file created
- ✅ `config.py` updated to use environment variables
- ✅ `.gitignore` configured
- ✅ Your credentials are secure

Need help? Check the terminal output for connection status!

