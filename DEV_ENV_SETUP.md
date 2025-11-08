# Development Environment Setup Guide

This guide explains how to set up separate environment configuration for the `dev` branch deployment.

## Overview

The dev environment uses separate `.env.dev` files that are automatically created during CI/CD deployment. This allows you to have different configurations for development and production environments.

## Files Structure

### Backend
- **Template**: `Backend/env.dev.template` - Template file with dev defaults
- **Runtime**: `Backend/.env.dev` - Created automatically during deployment (not in git)
- **Fallback**: `Backend/.env` - Used if `.env.dev` doesn't exist

### Frontend
- **Template**: `Frontend/env.dev.template` - Template file with dev defaults
- **Runtime**: `Frontend/.env.dev.local` - Created automatically during deployment (not in git)
- **Fallback**: `Frontend/.env.local` - Used if `.env.dev.local` doesn't exist

## CI/CD Configuration

The GitHub Actions workflow (`.github/workflows/deploy-dev.yml`) automatically:

1. Creates `.env.dev` files from templates if they don't exist
2. Updates them with secrets from GitHub Actions secrets (if provided)
3. Uses these files in `docker-compose.dev.yml`

## GitHub Secrets for Dev Environment

You can optionally set these secrets in GitHub Actions to automatically configure the dev environment:

- `DEV_AZURE_OPENAI_ENDPOINT` - Azure OpenAI endpoint for dev
- `DEV_AZURE_OPENAI_API_KEY` - Azure OpenAI API key for dev
- `DEV_AZURE_OPENAI_DEPLOYMENT_NAME` - Azure OpenAI deployment name for dev
- `DEV_GOOGLE_CLIENT_ID` - Google OAuth Client ID for dev
- `DEV_GOOGLE_CLIENT_SECRET` - Google OAuth Client Secret for dev
- `DEV_SESSION_SECRET` - Session secret for dev (should be different from production)

## Manual Setup on VM

If you need to manually configure the dev environment on the VM:

1. SSH into the VM
2. Navigate to `/opt/email-agent`
3. Copy the template files:
   ```bash
   cp Backend/env.dev.template Backend/.env.dev
   cp Frontend/env.dev.template Frontend/.env.dev.local
   ```
4. Edit the files with your dev-specific values:
   ```bash
   nano Backend/.env.dev
   nano Frontend/.env.dev.local
   ```
5. Restart the containers:
   ```bash
   sudo docker-compose -f docker-compose.dev.yml down
   sudo docker-compose -f docker-compose.dev.yml up -d
   ```

## Default Dev Configuration

The dev environment is configured with:
- **Backend URL**: `http://74.242.217.91:8000`
- **Frontend URL**: `http://74.242.217.91:3000`
- **CORS Origins**: Includes localhost and the dev VM IP
- **OAuth Redirect URI**: `http://74.242.217.91:8000/api/auth/callback`

## Environment Variables Priority

1. **Docker Compose environment section** (highest priority)
2. **`.env.dev` files** (dev-specific)
3. **`.env` files** (fallback)
4. **Default values in config.py** (lowest priority)

## Notes

- `.env.dev` files are **not** committed to git (they're in `.gitignore`)
- Template files (`env.dev.template`) **are** committed to git
- The CI/CD workflow automatically creates and updates `.env.dev` files during deployment
- You can override any value by setting it in the GitHub Actions secrets

