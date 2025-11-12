# VM Environment Configuration Guide

## Overview
The deployment workflow automatically creates and updates `.env` files on the VM. However, you may need to verify or manually set some values.

## Required .env Files on VM

### Backend/.env (Primary Config)
This file is created/updated automatically by the deployment workflow. Required variables:

```bash
# MongoDB
MONGODB_URI=mongodb://mongodb:27017/email_agent

# Azure OpenAI (from GitHub secrets)
AZURE_OPENAI_ENDPOINT=<your-endpoint>
AZURE_OPENAI_KEY=<your-key>
AZURE_OPENAI_DEPLOYMENT=gpt-4.1-mini
AZURE_OPENAI_API_VERSION=2025-01-01-preview
AI_PROVIDER=azure

# Google OAuth (from GitHub secrets)
GOOGLE_CLIENT_ID=<your-client-id>
GOOGLE_CLIENT_SECRET=<your-client-secret>
GOOGLE_REDIRECT_URI=https://emailagent.duckdns.org/api/auth/callback

# Session & URLs
SESSION_SECRET=<random-secret>
FRONTEND_URL=https://emailagent.duckdns.org
CORS_ORIGINS=http://localhost:3000,http://localhost:3001,https://emailagent.duckdns.org

# Auto-reply
AUTO_REPLY_ENABLED=true
```

### Backend/.env.dev (Override Config)
Same structure as `.env`, used for overrides. Created automatically.

### Frontend/.env.dev.local
```bash
NEXT_PUBLIC_API_URL=https://emailagent.duckdns.org
NODE_ENV=development
```

### Frontend/.env.local (Fallback)
Same as `.env.dev.local`, used as fallback.

## GitHub Secrets Required

Ensure these secrets are set in your GitHub repository:

- `DEV_AZURE_OPENAI_ENDPOINT`
- `DEV_AZURE_OPENAI_API_KEY`
- `DEV_AZURE_OPENAI_DEPLOYMENT_NAME`
- `DEV_GOOGLE_CLIENT_ID`
- `DEV_GOOGLE_CLIENT_SECRET`
- `DEV_SESSION_SECRET`

## Manual Verification on VM

After deployment, you can verify the .env files exist:

```bash
# Check Backend .env files
ls -la /opt/email-agent/Backend/.env*
cat /opt/email-agent/Backend/.env

# Check Frontend .env files
ls -la /opt/email-agent/Frontend/.env*
cat /opt/email-agent/Frontend/.env.dev.local
```

## Manual Setup (if needed)

If you need to manually create/update .env files on the VM:

1. SSH into the VM
2. Navigate to `/opt/email-agent`
3. Copy templates:
   ```bash
   cp Backend/env.dev.template Backend/.env
   cp Frontend/env.dev.template Frontend/.env.dev.local
   ```
4. Edit the files with your values
5. Restart containers:
   ```bash
   sudo docker-compose -f docker-compose.dev.yml restart backend frontend
   ```

## Important Notes

### What Persists vs. What Gets Overwritten

**⚠️ Code Changes on VM:**
- **Will be LOST** on next deployment
- The workflow runs `git reset --hard origin/dev` which overwrites all local changes
- Always commit code changes to git and push before deploying

**✅ .env File Changes:**
- **Will PERSIST** (workflow only updates specific variables)
- Manual edits to `.env` files remain unless the workflow overwrites that specific variable

**✅ Database & Data:**
- **Will PERSIST** (MongoDB and ChromaDB use Docker volumes)
- Account data, emails, and vector store data are preserved

**⚠️ Frontend Changes:**
- **Will be LOST** (frontend uses built image, no volume mounts)
- Requires code commit and rebuild

### Best Practice
Always commit and push code changes to git before deploying. The deployment workflow pulls fresh code from the repository, so any uncommitted changes on the VM will be lost.

### Other Notes

- The deployment workflow automatically sets production URLs
- `.env` is loaded first, then `.env.dev` overrides it
- All sensitive values should come from GitHub secrets
- The workflow recreates containers after updating .env files

