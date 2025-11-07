# OAuth Setup Guide - Fix "n8n" Error

## Problem
You're seeing: "n8n has not completed the Google verification process" or "Error 403: access_denied"

This happens because the OAuth consent screen in Google Cloud Console is configured with "n8n" as the app name, or the Client ID belongs to an n8n project.

## Solution: Update Google Cloud Console Settings

### Step 1: Open Google Cloud Console
1. Go to: https://console.cloud.google.com/
2. Select the project that contains your Client ID: `952028609923-dlflja9tt3jhrrd1bl6jupffoktrpfri.apps.googleusercontent.com`

### Step 2: Update OAuth Consent Screen
1. Navigate to: **APIs & Services** → **OAuth consent screen**
2. Click **"EDIT APP"** (if in editing mode) or **"PUBLISH APP"** → **"BACK TO EDITING"**
3. Update the following fields:
   - **App name**: Change from "n8n" to **"Email Agent"** (or your preferred name)
   - **User support email**: Your email address
   - **Developer contact information**: Your email address
4. Click **"SAVE AND CONTINUE"**

### Step 3: Add Scopes
1. In the OAuth consent screen, go to **"Scopes"** section
2. Click **"+ ADD OR REMOVE SCOPES"**
3. Search for and add these scopes:
   - `https://www.googleapis.com/auth/gmail.readonly` (Gmail Read Only)
   - `https://www.googleapis.com/auth/gmail.send` (Gmail Send)
   - `https://www.googleapis.com/auth/userinfo.email` (User Email)
   - `https://www.googleapis.com/auth/userinfo.profile` (User Profile)
4. Click **"UPDATE"** then **"SAVE AND CONTINUE"**

### Step 4: Add Test Users
1. Go to **"Test users"** section
2. Click **"+ ADD USERS"**
3. Add your email addresses (one per line):
   - `bidduttest@gmail.com`
   - Any other emails you want to test with
4. Click **"ADD"** then **"SAVE AND CONTINUE"**

### Step 5: Verify Redirect URI
1. Go to: **APIs & Services** → **Credentials**
2. Click on your OAuth 2.0 Client ID: `952028609923-dlflja9tt3jhrrd1bl6jupffoktrpfri`
3. Under **"Authorized redirect URIs"**, ensure this is listed:
   ```
   http://localhost:8000/api/auth/callback
   ```
4. If not present, click **"+ ADD URI"** and add it
5. Click **"SAVE"**

### Step 6: Enable Required APIs
1. Go to: **APIs & Services** → **Library**
2. Search for and enable:
   - **Gmail API**
   - **Google+ API** (for user info)
3. Wait for APIs to enable (usually instant)

### Step 7: Test
1. Restart your backend server (if needed)
2. Visit: http://localhost:3000
3. Click "Sign in with Google"
4. You should now see "Email Agent" (or your app name) instead of "n8n"
5. Complete the OAuth flow

## Quick Checklist
- [ ] OAuth consent screen app name is NOT "n8n"
- [ ] All 4 scopes are added
- [ ] Test users are added (your email addresses)
- [ ] Redirect URI is `http://localhost:8000/api/auth/callback`
- [ ] Gmail API and Google+ API are enabled
- [ ] Backend is using the correct Client ID and Secret

## If Still Not Working

### Option 1: Create New OAuth Client (Recommended)
If the current Client ID is still associated with n8n, create a new one:

1. **APIs & Services** → **Credentials**
2. Click **"+ CREATE CREDENTIALS"** → **"OAuth client ID"**
3. Application type: **"Web application"**
4. Name: **"Email Agent Web Client"**
5. Authorized redirect URIs: `http://localhost:8000/api/auth/callback`
6. Click **"CREATE"**
7. Copy the new Client ID and Secret
8. Update your `.env` file with the new credentials

### Option 2: Check Project
Make sure you're editing the correct Google Cloud project that contains your Client ID.

## Current Configuration
- **Client ID**: `952028609923-dlflja9tt3jhrrd1bl6jupffoktrpfri.apps.googleusercontent.com`
- **Redirect URI**: `http://localhost:8000/api/auth/callback`
- **Scopes**: Gmail readonly, Gmail send, userinfo email, userinfo profile

## Need Help?
Check the backend logs for detailed error messages. The OAuth flow will log any configuration issues.

