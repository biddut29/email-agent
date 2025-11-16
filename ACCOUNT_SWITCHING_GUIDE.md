# Account Switching Guide

## ✅ How It Works Now

### **Logout Process:**
1. Backend deletes session from MongoDB
2. Backend deletes session from memory
3. Backend clears browser cookie
4. Frontend clears ALL localStorage
5. Frontend clears ALL sessionStorage
6. Frontend clears ALL cookies
7. Frontend forces full page reload

### **Login Process:**
1. Google OAuth shows account picker (prompt='select_account consent')
2. User selects account
3. Backend creates NEW session token for that account
4. Session saved to MongoDB and memory
5. Cookie set in browser
6. Frontend stores token in localStorage

### **Data Access:**
- All data endpoints use **session-based account** (from your login session)
- Each session is completely isolated
- No account switching affects other users' sessions

## 🧪 Testing Steps

1. **Log out** - Check backend logs for:
   ```
   🚪 Logging out - Deleting session: ...
      Removing from memory for account: ...
      Session deleted from MongoDB
   ✅ Logout complete - Session cleared
   ```

2. **Log in with different account** - Check backend logs for:
   ```
   🔑 OAuth login - Creating new session for newemail@gmail.com (account_id=X)
      Session token: ...
   ✅ OAuth login successful for newemail@gmail.com
      Total active sessions: X
   ```

3. **Verify data** - Should see ONLY the logged-in account's emails

## 🔍 Troubleshooting

If you still see wrong account data:
1. Hard refresh browser (Ctrl+Shift+R / Cmd+Shift+R)
2. Clear browser cache completely
3. Check backend logs to confirm which account you're logged in as
4. Verify `/api/auth/me` returns the correct account

