"""
FastAPI Server for Email Agent
Provides REST API endpoints for the frontend
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, Cookie, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, RedirectResponse, JSONResponse, Response
from pydantic import BaseModel, EmailStr
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import uvicorn
import asyncio
import json as json_lib
import os
import secrets
from itsdangerous import URLSafeTimedSerializer
import base64
import mimetypes

from email_agent import EmailAgent
from email_receiver import EmailReceiver
from email_sender import EmailSender
from ai_agent import AIAgent, DEFAULT_PROMPT_TEMPLATE
from chat_agent import ChatAgent
from account_manager import AccountManager
from vector_store import vector_store
from mongodb_manager import mongodb_manager
from gmail_api_client import GmailAPIClient
from auth_manager import AuthManager
from config_manager import ConfigManager
from attachment_storage import attachment_storage
from __version__ import __version__ as backend_version
import config

# Initialize account manager with MongoDB (will be set up in startup)
account_manager = None

# Initialize auth manager
auth_manager = AuthManager()

# Initialize config manager (will be set up in startup)
config_manager = None

# Session serializer
session_serializer = URLSafeTimedSerializer(config.SESSION_SECRET)

# Store active sessions (loaded from MongoDB on startup, persisted to MongoDB)
active_sessions = {}

def load_sessions_from_db():
    """Load all active sessions from MongoDB on startup"""
    global active_sessions
    try:
        active_sessions = mongodb_manager.load_all_sessions()
        print(f"✓ Loaded {len(active_sessions)} active sessions from MongoDB")
        # Clean up expired sessions
        mongodb_manager.cleanup_expired_sessions()
    except Exception as e:
        print(f"⚠️  Failed to load sessions from MongoDB: {e}")
        active_sessions = {}


# Initialize FastAPI app
app = FastAPI(
    title="Email Agent API",
    description="AI-powered email management system",
    version=backend_version
)

# Add CORS middleware with optimized settings
# CORS origins are configured in config.py and can be overridden via CORS_ORIGINS env var
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,  # Configurable via CORS_ORIGINS env var
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],  # Explicit methods (reduces preflight)
    allow_headers=["Content-Type", "Authorization", "Accept", "Cookie", "X-Requested-With"],  # Explicit headers (reduces preflight)
    expose_headers=["*"],
    max_age=3600,  # Cache preflight response for 1 hour
)


# Authentication Middleware - Validates session tokens on all requests
# Public endpoints that don't require authentication
PUBLIC_ENDPOINTS = {
    "/",
    "/api/health",
    "/api/auth/login",
    "/api/auth/login-password",
    "/api/auth/callback",
    "/api/auth/me",  # Auth check endpoint (validates token internally)
    "/api/notifications/stream",  # SSE endpoint (validates token internally)
    "/docs",
    "/redoc",
    "/openapi.json"
}

@app.middleware("http")
async def authenticate_request(request: Request, call_next):
    """
    Global authentication middleware - validates session token for all protected endpoints
    """
    # Skip authentication for public endpoints and OPTIONS requests
    if request.url.path in PUBLIC_ENDPOINTS or request.method == "OPTIONS":
        return await call_next(request)
    
    # Skip auth for static files and docs
    if request.url.path.startswith(("/static", "/docs", "/redoc")):
        return await call_next(request)
    
    # Extract session token from multiple sources
    session_token = None
    
    # Priority 1: Cookie
    session_token = request.cookies.get('session_token')
    
    # Priority 2: Authorization header
    if not session_token:
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            session_token = auth_header.replace('Bearer ', '').strip()
    
    # Priority 3: Query parameter (for SSE and special cases)
    if not session_token:
        session_token = request.query_params.get('token')
    
    # Reject if no token provided
    if not session_token:
        return JSONResponse(
            status_code=401,
            content={
                "detail": "Not authenticated",
                "error": "No session token provided. Please login."
            }
        )
    
    # Validate token
    try:
        # Verify token signature and expiry
        session_data = session_serializer.loads(session_token, max_age=604800)  # 7 days
        
        # Check if session exists in active_sessions (memory cache)
        session = active_sessions.get(session_token)
        
        # If not in memory, try loading from MongoDB
        if not session:
            session = mongodb_manager.get_session(session_token)
            if session:
                # Restore to memory cache
                active_sessions[session_token] = session
                print(f"🔍 Session restored from MongoDB for {session.get('email')}")
        
        # If still not found but token is valid, recreate it from token data
        # This handles cases where session was deleted from DB but token is still valid
        if not session:
            # Recreate session from token data if token is still valid
            session = {
                'account_id': session_data.get('account_id'),
                'email': session_data.get('email'),
                'name': session_data.get('name', ''),
                'created_at': session_data.get('created_at', datetime.utcnow().isoformat()),
                'expires_at': (datetime.utcnow() + timedelta(days=7)).isoformat()
            }
            # Restore session in memory and save to MongoDB
            active_sessions[session_token] = session
            mongodb_manager.save_session(session_token, session)
            print(f"🔍 Session recreated from token for {session.get('email')}")
        
        # Update last accessed time (async, non-blocking)
        if session:
            session['last_accessed'] = datetime.utcnow().isoformat()
            # Update in background (non-blocking)
            import threading
            threading.Thread(
                target=lambda: mongodb_manager.save_session(session_token, session),
                daemon=True
            ).start()
        
        # Add session info to request state for use in endpoints
        request.state.session = session
        request.state.account_id = session['account_id']
        request.state.email = session['email']
        
        # Token is valid, proceed with request
        return await call_next(request)
        
    except Exception as e:
        # Token is invalid (tampered, expired, or malformed)
        return JSONResponse(
            status_code=401,
            content={
                "detail": "Invalid session",
                "error": f"Your session is invalid. Please login again."
            }
        )


# Helper function to get account from session (session-based, not global)
def get_account_from_session(request: Request) -> Optional[Dict]:
    """
    Get account from session (session-based, not global active account)
    This ensures account isolation - each session uses its own account
    """
    account_id = getattr(request.state, 'account_id', None)
    if account_id:
        return account_manager.get_account(account_id)
    return None

# Initialize email agent and chat agent globally
email_agent = None
chat_agent = None

# Notification queue for SSE
notification_queue = asyncio.Queue()


# Pydantic models for request/response
class EmailSendRequest(BaseModel):
    to: List[EmailStr] | EmailStr
    subject: str
    body: str
    cc: Optional[List[EmailStr]] = None
    bcc: Optional[List[EmailStr]] = None
    html: bool = False


class EmailReplyRequest(BaseModel):
    email_id: str
    body: str
    tone: str = "professional"


class EmailSearchRequest(BaseModel):
    query: Optional[str] = None
    sender: Optional[str] = None
    subject: Optional[str] = None
    limit: int = 20


class AIAnalysisRequest(BaseModel):
    email_id: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    from_email: Optional[str] = None


class ChatRequest(BaseModel):
    message: str
    include_context: bool = True


class ChatContextUpdate(BaseModel):
    emails: List[Dict[str, Any]]


class AccountAddRequest(BaseModel):
    email: EmailStr
    password: str
    imap_server: str = 'imap.gmail.com'
    imap_port: int = 993
    smtp_server: str = 'smtp.gmail.com'
    smtp_port: int = 587


class AccountUpdateRequest(BaseModel):
    email: Optional[str] = None
    password: Optional[str] = None
    imap_server: Optional[str] = None
    imap_port: Optional[int] = None
    smtp_server: Optional[str] = None
    smtp_port: Optional[int] = None


class CustomPromptRequest(BaseModel):
    custom_prompt: str


class AutoReplyToggleRequest(BaseModel):
    enabled: bool


class SemanticSearchRequest(BaseModel):
    query: str
    n_results: int = 10
    filter_metadata: Optional[Dict[str, Any]] = None


# ============================================================================
# ATTACHMENT ENDPOINTS (Hybrid Storage)
# ============================================================================

@app.get("/api/emails/{message_id}/attachments")
async def list_email_attachments(message_id: str, session_token: str = Cookie(None)):
    """List all attachments for an email"""
    try:
        if not session_token or session_token not in active_sessions:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        session_data = active_sessions[session_token]
        account_id = session_data.get('account_id')
        
        email = mongodb_manager.emails_collection.find_one({
            "message_id": message_id,
            "account_id": account_id
        })
        
        if not email:
            raise HTTPException(status_code=404, detail="Email not found")
        
        # Filter attachments to only include those with valid saved_filename
        all_attachments = email.get('attachments', [])
        valid_attachments = [
            att for att in all_attachments 
            if att.get('saved_filename') and att.get('saved_filename') != 'undefined' and att.get('saved_filename').strip() != ''
        ]
        
        return {
            "success": True,
            "message_id": message_id,
            "has_attachments": len(valid_attachments) > 0,
            "count": len(valid_attachments),
            "attachments": valid_attachments
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# DOWNLOAD ATTACHMENT ENDPOINT (must come before regular attachment endpoint)
# ============================================================================

@app.get("/api/attachments/download")
async def download_email_attachment(message_id: str = Query(...),
                                   account_id: int = Query(...),
                                   file_id: str = Query(...),
                                   session_token: str = Cookie(None)):
    """Download attachment (triggers browser download)"""
    import sys
    print(f"🔍 DOWNLOAD ENDPOINT CALLED: message_id={message_id}, account_id={account_id}, file_id={file_id}", flush=True)
    try:
        # URL decode message_id and file_id if needed
        from urllib.parse import unquote
        message_id_decoded = unquote(message_id)
        file_id_decoded = unquote(file_id)
        
        print(f"🔍 After decoding: message_id={message_id_decoded}, file_id={file_id_decoded}", flush=True)
        
        # Use decoded values
        message_id = message_id_decoded
        saved_filename = file_id_decoded
        
        # Validate file_id is not undefined or empty
        if not saved_filename or saved_filename == 'undefined' or saved_filename.strip() == '':
            print(f"❌ Invalid file_id: '{saved_filename}'", flush=True)
            raise HTTPException(status_code=400, detail="Invalid file ID: file_id is required and cannot be undefined")
        
        # Validate message_id
        if not message_id or message_id.strip() == '':
            print(f"❌ Invalid message_id: '{message_id}'", flush=True)
            raise HTTPException(status_code=400, detail="Invalid message ID: message_id is required")
        
        # Validate authentication
        if not session_token or session_token not in active_sessions:
            print(f"❌ Not authenticated: session_token={session_token is not None}")
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        # Verify the account_id in query matches the session (security check)
        session_data = active_sessions[session_token]
        session_account_id = session_data.get('account_id')
        
        if session_account_id != account_id:
            print(f"❌ Account ID mismatch: Query={account_id}, Session={session_account_id}", flush=True)
            raise HTTPException(status_code=403, detail="Account ID mismatch")
        
        print(f"🔍 Looking for attachment: account_id={account_id}, file_id={saved_filename}", flush=True)
        
        # Log the expected file path
        from pathlib import Path
        account_dir = attachment_storage.base_dir / f"account_{account_id}"
        expected_path = account_dir / saved_filename
        
        print(f"🔍 Account directory: {account_dir}", flush=True)
        print(f"🔍 Account directory exists: {account_dir.exists()}", flush=True)
        print(f"🔍 Expected file path: {expected_path}", flush=True)
        print(f"🔍 File exists: {expected_path.exists()}", flush=True)
        
        # List files in account directory for debugging
        if account_dir.exists():
            files = list(account_dir.glob("*"))
            print(f"🔍 Files in account_{account_id}: {[f.name for f in files[:5]]}", flush=True)
        
        binary_data = attachment_storage.get_attachment(
            account_id=account_id,
            message_id=message_id,
            saved_filename=saved_filename
        )
        
        if binary_data is None:
            print(f"❌ Attachment not found: account_id={account_id}, saved_filename={saved_filename}", flush=True)
            print(f"❌ Expected path was: {expected_path}", flush=True)
            raise HTTPException(status_code=404, detail="Attachment not found")
        
        print(f"✅ Found attachment: {len(binary_data)} bytes")
        
        email = mongodb_manager.emails_collection.find_one({
            "message_id": message_id,
            "account_id": account_id
        })
        
        original_filename = saved_filename
        content_type = 'application/octet-stream'
        
        if email and email.get('attachments'):
            att_metadata = next(
                (a for a in email['attachments'] if a.get('saved_filename') == saved_filename),
                None
            )
            if att_metadata:
                original_filename = att_metadata.get('original_filename', saved_filename)
                content_type = att_metadata.get('content_type', content_type)
        
        return Response(
            content=binary_data,
            media_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{original_filename}"'
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# GET ATTACHMENT ENDPOINT (returns base64)
# ============================================================================

@app.get("/api/emails/{message_id}/attachments/{saved_filename:path}")
async def get_email_attachment(message_id: str, saved_filename: str, 
                               session_token: str = Cookie(None)):
    """Get attachment (returns base64)"""
    try:
        if not session_token or session_token not in active_sessions:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        session_data = active_sessions[session_token]
        account_id = session_data.get('account_id')
        
        binary_data = attachment_storage.get_attachment(
            account_id=account_id,
            message_id=message_id,
            saved_filename=saved_filename
        )
        
        if binary_data is None:
            raise HTTPException(status_code=404, detail="Attachment not found")
        
        email = mongodb_manager.emails_collection.find_one({
            "message_id": message_id,
            "account_id": account_id
        })
        
        att_metadata = None
        if email and email.get('attachments'):
            att_metadata = next(
                (a for a in email['attachments'] if a.get('saved_filename') == saved_filename),
                None
            )
        
        content_type = att_metadata.get('content_type') if att_metadata else None
        if not content_type:
            content_type, _ = mimetypes.guess_type(saved_filename)
            if content_type is None:
                content_type = 'application/octet-stream'
        
        return {
            "success": True,
            "original_filename": att_metadata.get('original_filename', saved_filename) if att_metadata else saved_filename,
            "saved_filename": saved_filename,
            "content_type": content_type,
            "size": len(binary_data),
            "data": base64.b64encode(binary_data).decode('utf-8')
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/storage/stats")
async def get_storage_statistics():
    """Get attachment storage statistics"""
    try:
        return attachment_storage.get_storage_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Startup event
@app.on_event("startup")
async def startup_event():
    global email_agent, chat_agent, account_manager, config_manager
    
    # Initialize account manager with MongoDB
    account_manager = AccountManager(mongodb_manager=mongodb_manager)
    
    # Load sessions from MongoDB (persist across restarts)
    load_sessions_from_db()
    
    # Initialize config manager (DO NOT auto-load from .env)
    try:
        config_manager = ConfigManager()
        if config_manager is None:
            print("⚠️  Config manager could not be initialized - MongoDB may not be connected")
        elif config_manager.config_collection is None:
            print("❌ ERROR: MongoDB is not connected or database is not accessible.")
            print("   Please ensure MongoDB is running and MONGODB_URI is correct.")
        elif not config_manager.collection_exists():
            frontend_url = config.FRONTEND_URL or "http://localhost:3000"
            print("❌ ERROR: Configuration collection 'app_config' does not exist in database.")
            print("   Please use the admin panel to initialize configuration:")
            print(f"   1. Go to {frontend_url}/admin")
            print("   2. Click 'Load from .env' button to initialize configuration")
            print("   3. Or manually configure settings in the Application Configuration section")
        else:
            # Collection exists - skip count check for faster startup
            # Just verify it's accessible by trying to read one config
            try:
                test_config = config_manager.get_config("ai_provider", "")
                if test_config:
                    print(f"✓ Configuration loaded from database")
                else:
                    print("⚠️  Configuration collection exists but is empty. You can configure via admin panel.")
            except Exception as e:
                print(f"⚠️  Could not verify configuration: {e}")
    except Exception as e:
        print(f"⚠️  Could not initialize config manager: {e}")
        config_manager = None
    
    # Add default account from config if not exists, or ensure it's active
    if config.EMAIL_ADDRESS and config.EMAIL_PASSWORD:
        # Check if account already exists
        existing_account = account_manager.get_account_by_email(config.EMAIL_ADDRESS)
        
        if existing_account:
            # Account exists - update password if changed and ensure it's active
            if existing_account.get('password') != config.EMAIL_PASSWORD:
                # Update password using update_account method
                account_manager.update_account(
                    existing_account['id'],
                    password=config.EMAIL_PASSWORD
                )
                print(f"✓ Updated password for existing account: {config.EMAIL_ADDRESS}")
            
            # Security: Never automatically switch accounts
            # The .env account will not be activated automatically
            # User must explicitly activate accounts via the admin panel or API
            print(f"ℹ️  Account from .env exists: {config.EMAIL_ADDRESS} (not auto-activated for security)")
        else:
            # Account doesn't exist - add it
            result = account_manager.add_account(
                email=config.EMAIL_ADDRESS,
                password=config.EMAIL_PASSWORD,
                imap_server=config.IMAP_SERVER,
                imap_port=config.IMAP_PORT,
                smtp_server=config.SMTP_SERVER,
                smtp_port=config.SMTP_PORT
            )
            if 'error' in result:
                print(f"⚠️  Could not add account from .env: {result['error']}")
            else:
                print(f"✓ Added account from .env: {config.EMAIL_ADDRESS}")
    
    # Set vector store to active account (skip count for faster startup)
    active_account = account_manager.get_active_account()
    if active_account:
        vector_store.set_account(
            account_id=active_account['id'],
            account_email=active_account['email'],
            skip_count=True  # Skip expensive count on startup
        )
    
    # Read auto-reply enabled and AI provider from .env files
    auto_reply_enabled = config.AUTO_REPLY_ENABLED
    ai_provider = config.AI_PROVIDER
    
    email_agent = EmailAgent(
        ai_enabled=True, 
        ai_provider=ai_provider,
        account_manager=account_manager,
        mongodb_manager=mongodb_manager,
        notification_callback=broadcast_notification,
        auto_reply_enabled=auto_reply_enabled
    )
    # Start email agent in background to avoid blocking startup
    import threading
    def start_email_agent_async():
        email_agent.start()
        # Start real-time email monitoring (checks every 2 seconds)
        email_agent.start_monitoring(check_interval=2)
    
    thread = threading.Thread(target=start_email_agent_async, daemon=True)
    thread.start()
    
    chat_agent = ChatAgent()
    print("✓ Email Agent API Server started")


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    global email_agent
    if email_agent:
        email_agent.stop()
    print("✓ Email Agent API Server stopped")


# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "Email Agent API",
        "version": backend_version,
        "status": "running",
        "docs": "/docs"
    }


# Health check
@app.get("/api/health")
async def health_check():
    active_account = account_manager.get_active_account()
    return {
        "status": "healthy",
        "email": active_account['email'] if active_account else config.EMAIL_ADDRESS,
        "ai_enabled": email_agent.ai_enabled if email_agent else False,
        "accounts_count": account_manager.get_account_count(),
        "version": backend_version
    }


# ============================================================================
# AUTHENTICATION ENDPOINTS
# ============================================================================

@app.get("/api/auth/login")
async def login():
    """Initiate Google OAuth login"""
    try:
        # Validate OAuth configuration
        if not auth_manager.client_id or not auth_manager.client_secret:
            # Return a clear error that OAuth is not configured, but don't use 500
            return {
                "success": False,
                "error": "OAuth not configured",
                "message": "Google OAuth credentials are not configured. Please use App Password login instead, or configure GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env",
                "oauth_available": False
            }
        
        state = secrets.token_urlsafe(32)
        auth_url, _ = auth_manager.get_authorization_url(state=state)
        print(f"✓ OAuth login initiated - Client ID: {auth_manager.client_id[:20]}...")
        return {"success": True, "auth_url": auth_url, "state": state, "oauth_available": True}
    except ValueError as e:
        print(f"❌ OAuth configuration error: {e}")
        return {
            "success": False,
            "error": "OAuth configuration error",
            "message": str(e),
            "oauth_available": False
        }
    except Exception as e:
        print(f"❌ Login error: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": "Failed to initiate login",
            "message": str(e),
            "oauth_available": False
        }


@app.post("/api/auth/login-password")
async def login_with_password(request: Request):
    """Login with email and app password"""
    try:
        data = await request.json()
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            raise HTTPException(status_code=400, detail="Email and password are required")
        
        # Check if account exists
        account = account_manager.find_account_by_email(email)
        
        if account:
            # Update account with new password
            account_id = account['id']
            account_manager.update_account(
                account_id=account_id,
                password=password
            )
        else:
            # Create new account
            result = account_manager.add_account(
                email=email,
                password=password,
                imap_server="imap.gmail.com",
                imap_port=993,
                smtp_server="smtp.gmail.com",
                smtp_port=587
            )
            if 'error' in result:
                raise HTTPException(status_code=400, detail=result['error'])
            account_id = result.get('account_id')
            if not account_id:
                # Get account to find ID
                account = account_manager.find_account_by_email(email)
                account_id = account['id'] if account else None
        
        if not account_id:
            raise HTTPException(status_code=500, detail="Failed to create or update account")
        
        # Security: Do NOT automatically activate account globally
        # Each session uses its own account_id - no global switching
        # Get account details
        account = account_manager.get_account(account_id)
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        # Create session token
        session_data = {
            'account_id': account_id,
            'email': email,
            'name': email.split('@')[0],
            'created_at': datetime.utcnow().isoformat()
        }
        session_token = session_serializer.dumps(session_data)
        
        # Store session in memory and MongoDB
        session_data_dict = {
            'account_id': account_id,
            'email': email,
            'name': email.split('@')[0],
            'created_at': datetime.utcnow().isoformat(),
            'expires_at': (datetime.utcnow() + timedelta(days=7)).isoformat()
        }
        active_sessions[session_token] = session_data_dict
        # Save to MongoDB
        mongodb_manager.save_session(session_token, session_data_dict)
        
        print(f"✓ Password login successful for {email}")
        return {
            "success": True,
            "session_token": session_token,
            "user": {
                "account_id": account_id,
                "email": email
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Password login error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Login failed: {str(e)}")


@app.get("/api/auth/callback")
async def oauth_callback(code: str, state: Optional[str] = None):
    """Handle OAuth callback and create session"""
    try:
        # Exchange code for credentials
        credentials = auth_manager.exchange_code_for_credentials(code)
        
        # Get user info
        user_info = auth_manager.get_user_info(credentials)
        email = user_info.get('email')
        
        if not email:
            raise HTTPException(status_code=400, detail="Failed to get user email")
        
        # Convert credentials to dict for storage
        credentials_dict = auth_manager.credentials_to_dict(credentials)
        
        # Create or update account
        account = account_manager.find_account_by_email(email)
        if not account:
            # Create new account from OAuth
            account_id = account_manager.create_account_from_oauth(
                email=email,
                name=user_info.get('name', ''),
                credentials_dict=credentials_dict
            )
        else:
            # Update existing account with OAuth credentials
            account_id = account['id']
            account_manager.update_account_oauth_credentials(
                account_id=account_id,
                credentials_dict=credentials_dict
            )
        
        # Security: Do NOT automatically activate account globally
        # Each session uses its own account_id - no global switching
        
        # Create session token
        session_data = {
            'account_id': account_id,
            'email': email,
            'name': user_info.get('name', ''),
            'created_at': datetime.utcnow().isoformat()
        }
        session_token = session_serializer.dumps(session_data)
        
        # Store session in memory and MongoDB
        session_data_dict = {
            'account_id': account_id,
            'email': email,
            'name': user_info.get('name', ''),
            'created_at': datetime.utcnow().isoformat(),
            'credentials': credentials_dict,
            'expires_at': (datetime.utcnow() + timedelta(days=7)).isoformat()
        }
        active_sessions[session_token] = session_data_dict
        # Save to MongoDB
        mongodb_manager.save_session(session_token, session_data_dict)
        
        # Redirect to frontend with token
        # Force reload config to ensure we have the latest value
        import importlib
        importlib.reload(config)
        frontend_url = config.FRONTEND_URL
        redirect_url = f"{frontend_url}/auth/callback?token={session_token}"
        print(f"🔗 OAuth callback redirecting to: {redirect_url}")
        print(f"📋 Using FRONTEND_URL from config: {frontend_url}")
        
        # Use the FRONTEND_URL from config - it's already loaded from the correct .env file
        # .env.dev takes precedence if it exists (dev environment)
        # .env is used if .env.dev doesn't exist (local environment)
        # No need to override - trust the environment configuration
        
        return RedirectResponse(
            url=redirect_url,
            status_code=302
        )
    except Exception as e:
        print(f"❌ OAuth callback error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Authentication failed: {str(e)}")


@app.get("/api/auth/me")
async def get_current_user(request: Request, session_token: Optional[str] = Cookie(None)):
    """Get current authenticated user"""
    print(f"🔍 Auth check - Cookie token: {session_token[:50] if session_token else 'None'}...")
    
    # Also check Authorization header as fallback
    if not session_token:
        # Try to get from Authorization header
        auth_header = request.headers.get('Authorization', '')
        print(f"🔍 Auth check - Authorization header: {auth_header[:50] if auth_header else 'None'}...")
        if auth_header and auth_header.startswith('Bearer '):
            session_token = auth_header.replace('Bearer ', '')
            print(f"🔍 Auth check - Extracted token from Bearer header")
        # Also try query parameter
        if not session_token:
            session_token = request.query_params.get('token')
            print(f"🔍 Auth check - Query param token: {session_token[:50] if session_token else 'None'}...")
    
    if not session_token:
        print(f"❌ Auth check - No token found")
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        print(f"🔍 Auth check - Attempting to load session token...")
        session_data = session_serializer.loads(session_token, max_age=604800)  # 7 days
        print(f"🔍 Auth check - Session data loaded: account_id={session_data.get('account_id')}")
        
        session = active_sessions.get(session_token)
        print(f"🔍 Auth check - Active sessions count: {len(active_sessions)}")
        print(f"🔍 Auth check - Session found in active_sessions: {session is not None}")
        
        # If not in memory, try loading from MongoDB (same logic as middleware)
        if not session:
            print(f"🔍 Auth check - Session not in memory, checking MongoDB...")
            session = mongodb_manager.get_session(session_token)
            if session:
                # Restore to memory cache
                active_sessions[session_token] = session
                print(f"🔍 Auth check - Session restored from MongoDB for {session.get('email')}")
            else:
                # If still not found but token is valid, recreate it from token data
                print(f"🔍 Auth check - Session not in MongoDB, recreating from token data...")
                session = {
                    'account_id': session_data.get('account_id'),
                    'email': session_data.get('email'),
                    'name': session_data.get('name', ''),
                    'created_at': session_data.get('created_at', datetime.utcnow().isoformat()),
                    'expires_at': (datetime.utcnow() + timedelta(days=7)).isoformat()
                }
                # Restore session in memory and save to MongoDB
                active_sessions[session_token] = session
                mongodb_manager.save_session(session_token, session)
                print(f"🔍 Auth check - Session recreated from token for {session.get('email')}")
        
        if not session:
            print(f"❌ Auth check - Could not restore session")
            raise HTTPException(status_code=401, detail="Session expired")
        
        print(f"✅ Auth check - Success for account_id={session['account_id']}, email={session['email']}")
        return {
            "success": True,
            "user": {
                "account_id": session['account_id'],
                "email": session['email'],
                "name": session.get('name', '')
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Auth check error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=401, detail="Invalid session")


@app.post("/api/auth/logout")
async def logout(session_token: Optional[str] = Cookie(None)):
    """Logout user"""
    if session_token:
        # Delete from memory
        if session_token in active_sessions:
            del active_sessions[session_token]
        # Delete from MongoDB
        mongodb_manager.delete_session(session_token)
    
    return {"success": True, "message": "Logged out successfully"}


# Helper function to get current user from session
def get_current_account_id(session_token: Optional[str] = Cookie(None)) -> Optional[int]:
    """Get account ID from session token"""
    if not session_token:
        return None
    
    try:
        session = active_sessions.get(session_token)
        if session:
            return session['account_id']
    except:
        pass
    
    return None


def extract_attachment_binary_data(emails: List[Dict], receiver, account_id: int) -> None:
    """
    Extract binary data for attachments in emails and add it for filesystem storage.
    Modifies emails in-place to add binary_data to attachment dicts.
    
    Args:
        emails: List of email dictionaries
        receiver: EmailReceiver instance with connection to mail server
        account_id: Account ID for logging
    """
    if not emails or not receiver:
        print(f"⚠️  Skipping attachment extraction: emails={len(emails) if emails else 0}, receiver={receiver is not None}")
        return
    
    import base64
    
    print(f"🔍 Starting attachment extraction for {len(emails)} emails (account {account_id})")
    
    for email_data in emails:
        if email_data.get('has_attachments') and email_data.get('attachments'):
            message_id = email_data.get('message_id')
            gmail_id = email_data.get('gmail_id')  # Use Gmail ID for Gmail API attachments
            print(f"📧 Email {message_id} has {len(email_data['attachments'])} attachment(s)")
            
            for att in email_data['attachments']:
                # Skip if binary data already present
                if 'data' in att or 'binary_data' in att:
                    print(f"⏭️  Skipping {att.get('filename')} - binary data already present")
                    continue
                
                filename = att.get('filename')
                print(f"🔄 Processing attachment: {filename} (content_type: {att.get('content_type', 'N/A')})")
                
                # Use gmail_id if available (Gmail API), otherwise use message_id (IMAP)
                msg_id_for_attachment = gmail_id if gmail_id else message_id
                
                if filename and msg_id_for_attachment:
                    try:
                        # Extract attachment binary data from email
                        print(f"   Calling receiver.get_attachment('{msg_id_for_attachment}', '{filename}')")
                        attachment_data = receiver.get_attachment(msg_id_for_attachment, filename)
                        
                        if attachment_data and 'data' in attachment_data:
                            # Decode base64 and store as binary_data
                            # Gmail API uses URL-safe base64, need to convert or use urlsafe_b64decode
                            att['binary_data'] = base64.urlsafe_b64decode(attachment_data['data'])
                            
                            # Update content type if available
                            if 'content_type' not in att or not att['content_type']:
                                att['content_type'] = attachment_data.get('content_type', 'application/octet-stream')
                            
                            # Extract text content from images (OCR) and PDFs
                            # This will be included in vector store for semantic search
                            if 'text_content' not in att or not att.get('text_content'):
                                try:
                                    from text_extraction import extract_text_from_attachment
                                    extracted_text = extract_text_from_attachment(att, att['binary_data'])
                                    if extracted_text:
                                        att['text_content'] = extracted_text
                                        print(f"📝 Extracted text content: {len(extracted_text)} characters from {filename}")
                                except Exception as text_extract_error:
                                    # Don't fail if text extraction fails, just log it
                                    print(f"⚠️  Text extraction failed for {filename}: {text_extract_error}")
                            
                            print(f"✅ Extracted attachment: {filename} ({len(att['binary_data'])} bytes) for account {account_id}")
                        else:
                            print(f"⚠️  No data returned for {filename}: attachment_data={attachment_data}")
                    except Exception as e:
                        print(f"❌ Failed to extract attachment {filename}: {e}")
                        import traceback
                        traceback.print_exc()
                else:
                    print(f"⚠️  Missing filename or message_id: filename={filename}, message_id={message_id}")


# Get emails with automatic batch loading
@app.get("/api/emails")
async def get_emails(
    request: Request,
    limit: int = 1000,  # Max total emails to fetch across all batches
    unread_only: bool = False,
    folder: str = "INBOX",
    date_from: Optional[str] = None,  # Format: YYYY-MM-DD
    date_to: Optional[str] = None      # Format: YYYY-MM-DD
):
    """
    Get emails from inbox with optional date range filter.
    Automatically handles batch loading to fetch ALL emails within the date range.
    """
    try:
        if not email_agent:
            raise HTTPException(status_code=500, detail="Email agent not initialized")
        
        # Get account from session (session-based, not global)
        active_account = get_account_from_session(request)
        if not active_account:
            return {
                "success": False,
                "count": 0,
                "emails": [],
                "error": "No active email account. Please add an account first."
            }
        
        # Check if account has password (required for IMAP) or OAuth credentials (for Gmail API)
        if 'password' not in active_account or not active_account.get('password'):
            # Check if account has OAuth credentials - use Gmail API
            if 'oauth_credentials' in active_account and active_account.get('oauth_credentials'):
                try:
                    from auth_manager import AuthManager
                    from google.oauth2.credentials import Credentials
                    from googleapiclient.discovery import build
                    from google.auth.transport.requests import Request
                    from gmail_api_client import GmailAPIClient
                    from datetime import datetime
                    
                    # Convert OAuth credentials dict to Credentials object
                    auth_mgr = AuthManager()
                    creds = auth_mgr.dict_to_credentials(active_account['oauth_credentials'])
                    
                    # Refresh if expired
                    if creds.expired and creds.refresh_token:
                        try:
                            creds.refresh(Request())
                            # Update stored credentials
                            updated_creds_dict = auth_mgr.credentials_to_dict(creds)
                            account_manager.update_account_oauth_credentials(active_account['id'], updated_creds_dict)
                        except Exception as refresh_e:
                            print(f"⚠ Failed to refresh OAuth token: {refresh_e}")
                            return {
                                "success": False,
                                "count": 0,
                                "emails": [],
                                "error": f"OAuth token expired and refresh failed: {str(refresh_e)}"
                            }
                    
                    # Build Gmail service
                    gmail_service = build('gmail', 'v1', credentials=creds)
                    
                    # Create Gmail client
                    gmail_client = GmailAPIClient(active_account['email'])
                    gmail_client.service = gmail_service
                    gmail_client.creds = creds
                    
                    # Build Gmail search query
                    query_parts = ['in:inbox']  # Always search inbox
                    if unread_only:
                        query_parts.append('is:unread')
                    if date_from:
                        # Gmail date format: after:YYYY/MM/DD
                        date_obj = datetime.strptime(date_from, "%Y-%m-%d")
                        query_parts.append(f"after:{date_obj.strftime('%Y/%m/%d')}")
                    if date_to:
                        # Gmail date format: before:YYYY/MM/DD (add 1 day to include the end date)
                        date_obj = datetime.strptime(date_to, "%Y-%m-%d")
                        from datetime import timedelta
                        date_obj = date_obj + timedelta(days=1)  # Include the end date
                        query_parts.append(f"before:{date_obj.strftime('%Y/%m/%d')}")
                    
                    gmail_query = ' '.join(query_parts)
                    
                    # Fetch emails via Gmail API with batch loading
                    print(f"📧 Starting Gmail API batch loading (max {limit} emails)")
                    print(f"📧 Query: {gmail_query}")
                    
                    all_emails = []
                    batch_size = min(500, limit)  # Gmail API max is 500 per request
                    batch_num = 1
                    skip = 0
                    
                    while len(all_emails) < limit:
                        remaining = limit - len(all_emails)
                        fetch_count = min(batch_size, remaining)
                        
                        print(f"📧 Gmail API Batch {batch_num}: Fetching up to {fetch_count} emails (skip {skip})...")
                        
                        batch_emails = gmail_client.get_emails(limit=fetch_count, query=gmail_query, skip=skip)
                        
                        if not batch_emails:
                            print(f"📭 No more emails found. Total: {len(all_emails)}")
                            break
                        
                        all_emails.extend(batch_emails)
                        skip += len(batch_emails)
                        print(f"✅ Batch {batch_num}: Got {len(batch_emails)} emails (Total: {len(all_emails)}, Skip: {skip})")
                        
                        # If we got fewer than requested, we've reached the end
                        if len(batch_emails) < fetch_count:
                            print(f"📭 Reached end of results. Total: {len(all_emails)}")
                            break
                        
                        batch_num += 1
                        
                        # Safety limit: max 10 batches (5000 emails)
                        if batch_num > 10:
                            print(f"⚠️ Stopped at batch limit. Total: {len(all_emails)}")
                            break
                    
                    emails = all_emails
                    print(f"📧 Gmail API batch loading complete: {len(emails)} total emails")
                    
                    # Extract attachment binary data for filesystem storage
                    if emails:
                        try:
                            print(f"📎 Extracting attachment binary data for {len(emails)} emails...")
                            extract_attachment_binary_data(emails, gmail_client, active_account['id'])
                        except Exception as extract_error:
                            print(f"⚠️  Error extracting attachments: {extract_error}")
                    
                    # Save emails to MongoDB (synchronously to ensure they're saved before response)
                    mongo_result = {"saved": 0}
                    if emails and mongodb_manager.emails_collection is not None:
                        try:
                            result = mongodb_manager.save_emails(emails, active_account['id'])
                            print(f"✓ Saved {result.get('total', 0)} emails to MongoDB via Gmail API (Inserted: {result.get('inserted', 0)}, Updated: {result.get('updated', 0)})")
                            mongo_result = {"saved": result.get('total', 0), "inserted": result.get('inserted', 0), "updated": result.get('updated', 0)}
                        except Exception as e:
                            print(f"⚠ Error saving emails to MongoDB: {e}")
                            mongo_result = {"saved": 0, "error": str(e)}
                    
                    # Add emails to vector store for semantic search (async, don't block)
                    if emails and vector_store.collection:
                        import threading
                        account_email_for_vector = active_account.get('email', '')
                        account_id_for_vector = active_account['id']
                        
                        # Ensure vector store is set to the correct account
                        vector_store.set_account(account_id_for_vector, account_email_for_vector, skip_count=True)
                        
                        def add_to_vector_async():
                            try:
                                print(f"🔄 Starting async vector store update for {len(emails)} emails...")
                                result = vector_store.add_emails(emails, account_email=account_email_for_vector)
                                added = result.get('added', 0)
                                skipped = result.get('skipped', 0)
                                total = result.get('total', 0)
                                print(f"✅ Vector store update complete: Added {added} emails, Skipped {skipped} sent emails, Total in store: {total} (account_id: {account_id_for_vector})")
                            except Exception as e:
                                print(f"❌ Error adding emails to vector store: {e}")
                                import traceback
                                traceback.print_exc()
                        
                        # Start async vector store update
                        thread = threading.Thread(target=add_to_vector_async, daemon=True)
                        thread.start()
                    
                    return {
                        "success": True,
                        "count": len(emails),
                        "emails": emails,
                        "account": active_account['email'],
                        "mongo_saved": mongo_result.get('saved', 0),
                        "method": "gmail_api",
                        "date_range": {
                            "from": date_from,
                            "to": date_to
                        } if (date_from or date_to) else None
                    }
                    
                except Exception as gmail_error:
                    print(f"❌ Error fetching emails via Gmail API: {gmail_error}")
                    import traceback
                    traceback.print_exc()
                    return {
                        "success": False,
                        "count": 0,
                        "emails": [],
                        "error": f"Failed to fetch emails via Gmail API: {str(gmail_error)}"
                    }
            else:
                return {
                    "success": False,
                    "count": 0,
                    "emails": [],
                    "error": "Account password is missing. Please update the account with an App Password to enable IMAP access."
                }
        
        # Use IMAP for accounts with password
        # Update receiver with active account credentials
        receiver = email_agent.receiver
        receiver.email_address = active_account['email']
        receiver.password = active_account['password']
        receiver.imap_server = active_account.get('imap_server', 'imap.gmail.com')
        receiver.imap_port = active_account.get('imap_port', 993)
        
        # Ensure connection is established
        if not receiver.mail:
            receiver.connect()
        
        # Build search criteria with date range
        search_criteria = []
        
        if unread_only:
            search_criteria.append("UNSEEN")
        
        if date_from:
            from datetime import datetime
            date_obj = datetime.strptime(date_from, "%Y-%m-%d")
            search_criteria.append(f'SINCE {date_obj.strftime("%d-%b-%Y")}')
        
        if date_to:
            from datetime import datetime
            date_obj = datetime.strptime(date_to, "%Y-%m-%d")
            search_criteria.append(f'BEFORE {date_obj.strftime("%d-%b-%Y")}')
        
        # Get emails with date filter - IMAP batch loading
        search_query = " ".join(search_criteria) if search_criteria else None
        print(f"📧 Starting IMAP batch loading (max {limit} emails)")
        print(f"📧 Search criteria: {search_query if search_query else 'None (recent emails)'}")
        
        all_emails = []
        batch_size = 200  # IMAP can handle batches of 200 well
        batch_num = 1
        
        # For IMAP, we'll fetch in batches by using skip/limit approach
        while len(all_emails) < limit:
            remaining = limit - len(all_emails)
            fetch_count = min(batch_size, remaining)
            skip = len(all_emails)  # Skip emails we've already fetched
            
            print(f"📧 IMAP Batch {batch_num}: Fetching {fetch_count} emails (skip {skip})...")
            
            if search_criteria:
                batch_emails = receiver.search_emails(
                    " ".join(search_criteria), 
                    folder=folder, 
                    limit=fetch_count,
                    skip=skip
                )
            else:
                batch_emails = receiver.get_emails(
                    folder=folder, 
                    limit=fetch_count, 
                    unread_only=unread_only,
                    skip=skip
                )
            
            if not batch_emails:
                print(f"📭 No more emails found. Total: {len(all_emails)}")
                break
            
            all_emails.extend(batch_emails)
            print(f"✅ Batch {batch_num}: Got {len(batch_emails)} emails (Total: {len(all_emails)})")
            
            # If we got fewer than requested, we've reached the end
            if len(batch_emails) < fetch_count:
                print(f"📭 Reached end of results. Total: {len(all_emails)}")
                break
            
            batch_num += 1
            
            # Safety limit: max 10 batches (2000 emails)
            if batch_num > 10:
                print(f"⚠️ Stopped at batch limit. Total: {len(all_emails)}")
                break
        
        emails = all_emails
        print(f"📧 IMAP batch loading complete: {len(emails)} total emails")
        
        # Extract attachment binary data for filesystem storage
        if emails:
            try:
                print(f"📎 Extracting attachment binary data for {len(emails)} emails...")
                extract_attachment_binary_data(emails, receiver, active_account['id'])
            except Exception as extract_error:
                print(f"⚠️  Error extracting attachments: {extract_error}")
        
        # Save emails to MongoDB (synchronously to ensure they're saved before response)
        mongo_result = {"saved": 0}
        if emails and mongodb_manager.emails_collection is not None:
            try:
                result = mongodb_manager.save_emails(emails, active_account['id'])
                print(f"✓ Saved {result.get('total', 0)} emails to MongoDB (Inserted: {result.get('inserted', 0)}, Updated: {result.get('updated', 0)})")
                mongo_result = {"saved": result.get('total', 0), "inserted": result.get('inserted', 0), "updated": result.get('updated', 0)}
            except Exception as e:
                print(f"⚠ Error saving emails to MongoDB: {e}")
                mongo_result = {"saved": 0, "error": str(e)}
        
        # Add emails to vector store for semantic search (async, don't block)
        if emails and vector_store.collection:
            import threading
            account_email_for_vector = active_account.get('email', '')
            account_id_for_vector = active_account['id']
            
            # Ensure vector store is set to the correct account
            vector_store.set_account(account_id_for_vector, account_email_for_vector, skip_count=True)
            
            def add_to_vector_async():
                try:
                    print(f"🔄 Starting async vector store update for {len(emails)} emails...")
                    result = vector_store.add_emails(emails, account_email=account_email_for_vector)
                    added = result.get('added', 0)
                    skipped = result.get('skipped', 0)
                    total = result.get('total', 0)
                    print(f"✅ Vector store update complete: Added {added} emails, Skipped {skipped} sent emails, Total in store: {total} (account_id: {account_id_for_vector})")
                except Exception as e:
                    print(f"❌ Error adding emails to vector store: {e}")
                    import traceback
                    traceback.print_exc()
            
            # Start async vector store update
            thread = threading.Thread(target=add_to_vector_async, daemon=True)
            thread.start()
        
        return {
            "success": True,
            "count": len(emails),
            "emails": emails,
            "account": active_account['email'],
            "mongo_saved": mongo_result.get('saved', 0),
            "method": "imap",
            "date_range": {
                "from": date_from,
                "to": date_to
            } if (date_from or date_to) else None
        }
    except Exception as e:
        # Log the error but return empty list instead of failing
        print(f"Error in get_emails endpoint: {str(e)}")
        return {
            "success": True,
            "count": 0,
            "emails": [],
            "error": str(e)
        }


# Get unread emails
@app.get("/api/emails/unread")
async def get_unread_emails(request: Request, limit: int = 10):
    """Get unread emails"""
    return await get_emails(request=request, limit=limit, unread_only=True)


# Load emails from MongoDB to Vector DB
@app.post("/api/emails/load-to-vector")
async def load_emails_to_vector(
    request: Request,
    limit: int = 1000,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
):
    """
    Load emails from MongoDB to Vector DB for semantic search
    
    Args:
        limit: Maximum number of emails to load
        date_from: Optional start date filter (YYYY-MM-DD)
        date_to: Optional end date filter (YYYY-MM-DD)
    """
    try:
        # Get account from session (session-based, not global)
        active_account = get_account_from_session(request)
        if not active_account:
            raise HTTPException(status_code=400, detail="No active account")
        
        # Get MongoDB stats
        mongo_stats = mongodb_manager.get_stats(active_account['id'])
        total_in_mongo = mongo_stats.get('total_emails', 0)
        
        if total_in_mongo == 0:
            return {
                "success": False,
                "message": "No emails found in MongoDB. Load emails first.",
                "mongo_count": 0,
                "vector_count": 0
            }
        
        # Clear vector store for this account first
        if vector_store.collection:
            clear_result = vector_store.clear()
            print(f"✓ {clear_result.get('message', 'Cleared vector store')}")
        
        # Get emails from MongoDB (with optional date filter)
        if date_from or date_to:
            # For filtered queries, use regular get_emails with date filter
            emails = mongodb_manager.get_emails(
                account_id=active_account['id'],
                limit=limit,
                date_from=date_from,
                date_to=date_to
            )
        else:
            # For full load, use optimized query
            emails = mongodb_manager.get_emails_for_vector(
                account_id=active_account['id'],
                limit=limit
            )
        
        if not emails:
            return {
                "success": False,
                "message": "No emails found matching criteria",
                "mongo_count": total_in_mongo,
                "vector_count": 0
            }
        
        # Index to vector store
        if vector_store.collection:
            account_email_for_vector = active_account.get('email', '')
            result = vector_store.add_emails(emails, account_email=account_email_for_vector)
            vector_count = result.get('added', 0)
            print(f"✓ Loaded {vector_count} emails from MongoDB to Vector Store")
        else:
            vector_count = 0
        
        return {
            "success": True,
            "message": f"Successfully loaded {vector_count} emails to vector database",
            "mongo_count": total_in_mongo,
            "vector_count": vector_count,
            "date_range": {
                "from": date_from,
                "to": date_to
            } if (date_from or date_to) else None
        }
    
    except Exception as e:
        print(f"Error loading emails to vector: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Get single email
@app.get("/api/emails/{email_id}")
async def get_email(email_id: str):
    """Get a specific email by ID"""
    try:
        if not email_agent:
            raise HTTPException(status_code=500, detail="Email agent not initialized")
        
        receiver = email_agent.receiver
        email_data = receiver._fetch_email(email_id.encode())
        
        if not email_data:
            raise HTTPException(status_code=404, detail="Email not found")
        
        return {
            "success": True,
            "email": email_data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Send email
@app.post("/api/emails/send")
async def send_email(request: EmailSendRequest):
    """Send a new email"""
    try:
        if not email_agent:
            raise HTTPException(status_code=500, detail="Email agent not initialized")
        
        sender = email_agent.sender
        success = sender.send_email(
            to=request.to,
            subject=request.subject,
            body=request.body,
            cc=request.cc,
            bcc=request.bcc,
            html=request.html
        )
        
        if success:
            return {
                "success": True,
                "message": "Email sent successfully"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to send email")
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Reply to email
@app.post("/api/emails/reply")
async def reply_to_email(request: EmailReplyRequest):
    """Reply to an email"""
    try:
        if not email_agent:
            raise HTTPException(status_code=500, detail="Email agent not initialized")
        
        # Fetch original email
        receiver = email_agent.receiver
        email_data = receiver._fetch_email(request.email_id.encode())
        
        if not email_data:
            raise HTTPException(status_code=404, detail="Original email not found")
        
        # Send reply
        sender = email_agent.sender
        success = sender.reply_to_email(
            original_email=email_data,
            body=request.body
        )
        
        if success:
            return {
                "success": True,
                "message": "Reply sent successfully"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to send reply")
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Reply to email using MongoDB data (for AI-suggested replies)
@app.post("/api/emails/reply-from-mongodb")
async def reply_from_mongodb(message_id: str, reply_body: str):
    """Reply to an email using MongoDB stored data"""
    try:
        if not email_agent:
            raise HTTPException(status_code=500, detail="Email agent not initialized")
        
        if not mongodb_manager or mongodb_manager.emails_collection is None:
            raise HTTPException(status_code=500, detail="MongoDB not connected")
        
        active_account = account_manager.get_active_account()
        if not active_account:
            raise HTTPException(status_code=400, detail="No active account")
        
        # Fetch email from MongoDB (with full body - no projection to exclude bodies)
        # Handle both actual Message-ID and synthetic Gmail ID formats
        email_doc = mongodb_manager.emails_collection.find_one({
            "$or": [
                {"message_id": message_id, "account_id": active_account['id']},
                {"gmail_synthetic_id": message_id, "account_id": active_account['id']}
            ]
        }, {'_id': 0})  # Explicitly include all fields including text_body and html_body
        
        if not email_doc:
            raise HTTPException(status_code=404, detail="Email not found in MongoDB")
        
        # Check if body exists, if not try to re-fetch from IMAP
        text_body = email_doc.get('text_body', '') or ''
        html_body = email_doc.get('html_body', '') or ''
        
        if not text_body and not html_body:
            print(f"⚠️  Email {message_id} has no body in MongoDB, attempting to re-fetch from IMAP...")
            # Try to re-fetch from IMAP
            receiver = email_agent.receiver
            try:
                receiver.mail.noop()
            except:
                receiver.connect()
            
            # Search for the email by subject and from
            subject = email_doc.get('subject', '')
            from_addr = email_doc.get('from', '')
            if subject:
                search_query = f'SUBJECT "{subject}"'
                emails = receiver.search_emails(search_query, folder='INBOX', limit=5)
                if emails and from_addr:
                    emails = [e for e in emails if from_addr.lower() in e.get('from', '').lower()]
                
                if emails:
                    # Found email, update MongoDB with body
                    fresh_email = emails[0]
                    text_body = fresh_email.get('text_body', '') or ''
                    html_body = fresh_email.get('html_body', '') or ''
                    
                    # Update MongoDB with the body
                    mongodb_manager.emails_collection.update_one(
                        {"message_id": message_id, "account_id": active_account['id']},
                        {"$set": {
                            "text_body": text_body,
                            "html_body": html_body
                        }}
                    )
                    print(f"✓ Updated email body in MongoDB: text={len(text_body)} chars, html={len(html_body)} chars")
        
        # Send reply using the sender with original email included
        sender = email_agent.sender
        
        # Update sender with active account credentials
        sender.email_address = active_account['email']
        sender.password = active_account.get('password', '')
        sender.smtp_server = active_account.get('smtp_server', 'smtp.gmail.com')
        sender.smtp_port = active_account.get('smtp_port', 587)
        
        # Set OAuth credentials if available
        if 'oauth_credentials' in active_account and active_account.get('oauth_credentials'):
            try:
                from auth_manager import AuthManager
                from google.auth.transport.requests import Request
                auth_mgr = AuthManager()
                creds = auth_mgr.dict_to_credentials(active_account['oauth_credentials'])
                
                # Refresh if expired
                if creds.expired and creds.refresh_token:
                    try:
                        creds.refresh(Request())
                        # Update stored credentials
                        updated_creds_dict = auth_mgr.credentials_to_dict(creds)
                        account_manager.update_account_oauth_credentials(active_account['id'], updated_creds_dict)
                    except Exception as refresh_e:
                        print(f"⚠ Failed to refresh OAuth token: {refresh_e}")
                
                sender.set_oauth_credentials(active_account['oauth_credentials'])
            except Exception as oauth_error:
                print(f"⚠ Failed to set OAuth credentials: {oauth_error}")
                sender.oauth_credentials = None
                sender.gmail_service = None
        else:
            # Clear OAuth if not available
            sender.oauth_credentials = None
            sender.gmail_service = None
        
        # Convert MongoDB document to email dict format for reply_to_email
        original_subject = email_doc.get('subject', 'No Subject')
        original_email_dict = {
            'from': email_doc.get('from', ''),
            'subject': original_subject,
            'date': email_doc.get('date', ''),
            'text_body': text_body,  # Use the fetched/updated body
            'html_body': html_body   # Use the fetched/updated body
        }
        
        # Format reply subject
        if not original_subject.startswith('Re:'):
            reply_subject = f"Re: {original_subject}"
        else:
            reply_subject = original_subject
        
        # Use send_email with threading headers for proper email threading
        # Extract the original message_id for threading
        original_message_id = email_doc.get('message_id', '')
        
        # Normalize message_id format - ensure it has angle brackets for proper threading
        if original_message_id:
            # Remove any existing angle brackets and whitespace
            clean_msg_id = original_message_id.strip('<>').strip()
            if clean_msg_id:
                # Ensure proper Message-ID format: <id@domain>
                if not clean_msg_id.startswith('<'):
                    normalized_message_id = f"<{clean_msg_id}>"
                else:
                    normalized_message_id = clean_msg_id
            else:
                normalized_message_id = None
        else:
            normalized_message_id = None
        
        # Get thread_id if available (for Gmail API threading)
        thread_id = email_doc.get('thread_id', '')
        gmail_id = email_doc.get('gmail_id', '')
        
        print(f"🔍 Email document fields: thread_id={thread_id if thread_id else 'MISSING'}, gmail_id={gmail_id if gmail_id else 'MISSING'}")
        
        # Build reply body with original email included
        reply_body_with_original = f"""{reply_body}

---------- Original Message ----------
From: {email_doc.get('from', '')}
Date: {email_doc.get('date', '')}
Subject: {original_subject}

{text_body or html_body or '(No body content)'}
"""
        
        # Check if sender is properly configured
        sender_email = sender.email_address
        has_oauth = sender.oauth_credentials is not None and sender.gmail_service is not None
        has_password = sender.password is not None and sender.password.strip() != ''
        
        if not has_oauth and not has_password:
            raise HTTPException(
                status_code=500, 
                detail="Email sender not configured. Please configure OAuth credentials or SMTP password in account settings."
            )
        
        print(f"📤 Sending reply from {sender_email} to {email_doc.get('from', '')}")
        print(f"   Method: {'Gmail API' if has_oauth else 'SMTP'}")
        print(f"   Subject: {reply_subject}")
        print(f"   Threading: message_id={normalized_message_id}, thread_id={thread_id if thread_id else 'N/A'}")
        
        # For Gmail API, always try to use threadId (more reliable than headers alone)
        if has_oauth:
            # Try to get threadId from Gmail API if not in document
            if not thread_id:
                # First, try using gmail_id if available (faster)
                if gmail_id:
                    try:
                        msg = sender.gmail_service.users().messages().get(
                            userId='me',
                            id=gmail_id,
                            format='metadata'
                        ).execute()
                        thread_id = msg.get('threadId', '')
                        if thread_id:
                            print(f"📎 Retrieved threadId from Gmail API using gmail_id: {thread_id}")
                            # Update MongoDB with thread_id for future use
                            mongodb_manager.emails_collection.update_one(
                                {"message_id": message_id, "account_id": active_account['id']},
                                {"$set": {"thread_id": thread_id}}
                            )
                    except Exception as e:
                        print(f"⚠️  Could not retrieve threadId using gmail_id: {e}")
                        gmail_id = None
                
                # Fallback: search by subject and from address if gmail_id not available
                if not thread_id and normalized_message_id:
                    try:
                        subject = email_doc.get('subject', '').replace('Re: ', '').replace('RE: ', '').strip()
                        from_addr = email_doc.get('from', '').split('<')[0].strip() if '<' in email_doc.get('from', '') else email_doc.get('from', '')
                        if subject and from_addr:
                            # Search for the message by subject and from
                            query = f'subject:"{subject[:50]}" from:{from_addr}'
                            gmail_messages = sender.gmail_service.users().messages().list(
                                userId='me',
                                q=query,
                                maxResults=5
                            ).execute()
                            
                            if gmail_messages.get('messages'):
                                # Get the most recent matching message
                                for msg_item in gmail_messages['messages']:
                                    msg = sender.gmail_service.users().messages().get(
                                        userId='me',
                                        id=msg_item['id'],
                                        format='metadata'
                                    ).execute()
                                    thread_id = msg.get('threadId', '')
                                    if thread_id:
                                        print(f"📎 Retrieved threadId from Gmail API using search: {thread_id}")
                                        # Update MongoDB with thread_id and gmail_id for future use
                                        mongodb_manager.emails_collection.update_one(
                                            {"message_id": message_id, "account_id": active_account['id']},
                                            {"$set": {"thread_id": thread_id, "gmail_id": msg_item['id']}}
                                        )
                                        break
                    except Exception as e:
                        print(f"⚠️  Could not retrieve threadId from Gmail API via search: {e}")
            
            # Gmail API - always use threadId if available (more reliable)
            success = sender.send_email(
                to=email_doc.get('from', ''),
                subject=reply_subject,
                body=reply_body_with_original,
                html=False,
                in_reply_to=normalized_message_id if normalized_message_id else None,
                references=normalized_message_id if normalized_message_id else None,
                thread_id=thread_id if thread_id else None  # Gmail API threading
            )
        else:
            # SMTP - use headers only (threadId not supported)
            success = sender.send_email(
                to=email_doc.get('from', ''),
                subject=reply_subject,
                body=reply_body_with_original,
                html=False,
                in_reply_to=normalized_message_id if normalized_message_id else None,
                references=normalized_message_id if normalized_message_id else None
            )
        
        if success:
            # Save reply to MongoDB
            reply_data = {
                'to': email_doc.get('from', ''),
                'subject': reply_subject,
                'body': reply_body,
                'success': True
            }
            mongodb_manager.save_reply(
                message_id,
                active_account['id'],
                reply_data
            )
            
            print(f"✓ Reply sent successfully to {email_doc.get('from', '')}")
            
            return {
                "success": True,
                "message": "Reply sent successfully",
                "to": email_doc.get('from', ''),
                "subject": reply_subject
            }
        else:
            error_msg = f"Failed to send reply. Sender configured: OAuth={has_oauth}, SMTP={has_password}. Check backend logs for details."
            print(f"❌ {error_msg}")
            raise HTTPException(status_code=500, detail=error_msg)
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error sending reply from MongoDB: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# AI Analysis
@app.post("/api/emails/analyze")
async def analyze_email(request: AIAnalysisRequest):
    """Analyze an email using AI"""
    try:
        if not email_agent or not email_agent.ai_agent:
            raise HTTPException(status_code=400, detail="AI features not enabled")
        
        # Get email data
        if request.email_id:
            receiver = email_agent.receiver
            email_data = receiver._fetch_email(request.email_id.encode())
        else:
            email_data = {
                "subject": request.subject or "",
                "text_body": request.body or "",
                "from": request.from_email or ""
            }
        
        if not email_data:
            raise HTTPException(status_code=404, detail="Email not found")
        
        ai_agent = email_agent.ai_agent
        
        # Perform AI analysis
        category = ai_agent.categorize_email(email_data)
        urgency_score, urgency_reason = ai_agent.detect_urgency(email_data)
        is_spam, spam_confidence = ai_agent.is_spam(email_data)
        summary = ai_agent.summarize_email(email_data)
        action_items = ai_agent.extract_action_items(email_data)
        
        return {
            "success": True,
            "analysis": {
                "category": category,
                "urgency": {
                    "score": urgency_score,
                    "reason": urgency_reason
                },
                "spam": {
                    "is_spam": is_spam,
                    "confidence": spam_confidence
                },
                "summary": summary,
                "action_items": action_items
            }
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Generate AI response
@app.post("/api/emails/generate-response")
async def generate_response(
    request: Request,
    email_id: str,
    tone: str = "professional",
    message_id: Optional[str] = None  # Optional: use message_id for MongoDB emails
):
    """Generate an AI response for an email"""
    try:
        if not email_agent or not email_agent.ai_agent:
            raise HTTPException(status_code=400, detail="AI features not enabled")
        
        email_data = None
        
        # If message_id is provided, fetch from MongoDB (for emails loaded via Gmail API or MongoDB)
        if message_id:
            if not mongodb_manager or mongodb_manager.emails_collection is None:
                raise HTTPException(status_code=500, detail="MongoDB not connected")
            
            active_account = get_account_from_session(request)
            if not active_account:
                raise HTTPException(status_code=400, detail="No active account")
            
            # Fetch email from MongoDB (handle both message_id formats)
            email_doc = mongodb_manager.emails_collection.find_one({
                "$or": [
                    {"message_id": message_id, "account_id": active_account['id']},
                    {"gmail_synthetic_id": message_id, "account_id": active_account['id']}
                ]
            }, {'_id': 0})
            
            if email_doc:
                # Convert MongoDB document to email dict format
                email_data = {
                    'subject': email_doc.get('subject', ''),
                    'from': email_doc.get('from', ''),
                    'to': email_doc.get('to', ''),
                    'text_body': email_doc.get('text_body', ''),
                    'html_body': email_doc.get('html_body', ''),
                    'date': email_doc.get('date', ''),
                    'message_id': email_doc.get('message_id', '')
                }
        
        # If not found in MongoDB or message_id not provided, try IMAP
        if not email_data:
            receiver = email_agent.receiver
            email_data = receiver._fetch_email(email_id.encode())
        
        if not email_data:
            raise HTTPException(status_code=404, detail="Email not found")
        
        # Add sender information to email_data for proper signature generation
        active_account = account_manager.get_active_account()
        custom_prompt = None
        if active_account:
            sender_email = active_account.get('email', '')
            if sender_email:
                sender_name = sender_email.split('@')[0].replace('.', ' ').replace('_', ' ').title()
                email_data['sender_name'] = sender_name
                email_data['reply_account'] = active_account
                print(f"📝 Set sender_name to '{sender_name}' from account {sender_email}")
            # Get custom prompt for this account
            custom_prompt = active_account.get('custom_prompt', '')
            if custom_prompt and custom_prompt.strip():
                print(f"📝 Using custom prompt for account {active_account.get('email')}")
            else:
                print(f"📝 Using default prompt for account {active_account.get('email')}")
        else:
            # If no active account, try to get from config as fallback
            if hasattr(config, 'EMAIL_ADDRESS') and config.EMAIL_ADDRESS:
                sender_email = config.EMAIL_ADDRESS
                sender_name = sender_email.split('@')[0].replace('.', ' ').replace('_', ' ').title()
                email_data['sender_name'] = sender_name
                print(f"📝 Set sender_name to '{sender_name}' from config {sender_email}")
            else:
                print(f"⚠️  WARNING: No active account and no EMAIL_ADDRESS in config - signature may be 'User'")
        
        ai_agent = email_agent.ai_agent
        response_body = ai_agent.generate_response(email_data, tone=tone, custom_prompt=custom_prompt)
        
        return {
            "success": True,
            "response": response_body,
            "original_email": {
                "subject": email_data.get("subject"),
                "from": email_data.get("from")
            }
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Search emails
@app.post("/api/emails/search")
async def search_emails(request: EmailSearchRequest):
    """Search emails"""
    try:
        if not email_agent:
            raise HTTPException(status_code=500, detail="Email agent not initialized")
        
        receiver = email_agent.receiver
        
        if request.sender:
            emails = receiver.search_emails(f'FROM "{request.sender}"')
        elif request.subject:
            emails = receiver.search_emails(f'SUBJECT "{request.subject}"')
        elif request.query:
            emails = receiver.search_emails(request.query)
        else:
            emails = receiver.get_emails(limit=request.limit)
        
        return {
            "success": True,
            "count": len(emails),
            "emails": emails[:request.limit]
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Get statistics
@app.get("/api/statistics")
async def get_statistics():
    """Get email statistics"""
    try:
        if not email_agent:
            raise HTTPException(status_code=500, detail="Email agent not initialized")
        
        # Process recent emails for statistics
        email_agent.process_inbox(limit=20, unread_only=False)
        stats = email_agent.get_email_statistics()
        
        return {
            "success": True,
            "statistics": stats
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Mark as read
@app.put("/api/emails/{email_id}/read")
async def mark_as_read(email_id: str):
    """Mark an email as read"""
    try:
        if not email_agent:
            raise HTTPException(status_code=500, detail="Email agent not initialized")
        
        receiver = email_agent.receiver
        receiver.mark_as_read(email_id)
        
        return {
            "success": True,
            "message": "Email marked as read"
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# List folders
@app.get("/api/folders")
async def list_folders():
    """List all email folders"""
    try:
        if not email_agent:
            raise HTTPException(status_code=500, detail="Email agent not initialized")
        
        receiver = email_agent.receiver
        folders = receiver.list_folders()
        
        return {
            "success": True,
            "folders": folders
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# CHAT ENDPOINTS
# ============================================================================

@app.post("/api/chat/message")
async def chat_message(request: Request, chat_request: ChatRequest):
    """Send a message to the chat agent with vector search enabled (RAG)"""
    try:
        if not chat_agent:
            raise HTTPException(status_code=500, detail="Chat agent not initialized")
        
        # Always use vector search (RAG) if vector store has emails for the active account
        # This enables semantic search for better context-aware responses
        use_vector = False
        vector_count = 0
        
        if vector_store.collection:
            # Get account from session (session-based, not global)
            active_account = get_account_from_session(request)
            if active_account:
                # Ensure vector store is set to the correct account
                vector_store.set_account(active_account['id'], active_account.get('email'), skip_count=True)
                
                # Quick check: try to get at least one email for this account
                try:
                    results = vector_store.collection.get(
                        where={"account_id": str(active_account['id'])},
                        limit=1
                    )
                    if results.get('ids') and len(results['ids']) > 0:
                        use_vector = True
                        # Get count for logging (async, don't block)
                        try:
                            all_results = vector_store.collection.get(
                                where={"account_id": str(active_account['id'])},
                                limit=None
                            )
                            vector_count = len(all_results.get('ids', [])) if all_results.get('ids') else 0
                        except:
                            vector_count = 1  # At least one exists
                except Exception as e:
                    print(f"⚠️ Error checking vector store: {e}")
        
        # Get MongoDB count for accurate total
        mongodb_count = 0
        if active_account:
            try:
                mongodb_count = mongodb_manager.emails_collection.count_documents(
                    {"account_id": active_account['id']}
                )
            except Exception as e:
                print(f"⚠️ Error getting MongoDB count: {e}")
        
        if use_vector:
            print(f"🤖 Chat using RAG (vector search) - {vector_count} emails in vector store, {mongodb_count} in MongoDB for account {active_account['id']}")
        else:
            print(f"⚠️ Chat NOT using vector search - no emails found in vector store")
        
        # Use MongoDB count as the authoritative total (it's the source of truth)
        total_email_count = mongodb_count if mongodb_count > 0 else vector_count
        
        result = chat_agent.chat(
            chat_request.message, 
            include_context=chat_request.include_context, 
            use_vector_search=use_vector,
            total_email_count=total_email_count,
            account_id=active_account['id'] if active_account else None
        )
        
        return {
            "success": not result.get("error", False),
            "response": result["response"],
            "tokens_used": result.get("tokens_used"),
            "error": result.get("error", False)
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat/context")
async def update_chat_context(request: ChatContextUpdate):
    """Update the chat agent's email context"""
    try:
        if not chat_agent:
            raise HTTPException(status_code=500, detail="Chat agent not initialized")
        
        chat_agent.set_email_context(request.emails)
        
        return {
            "success": True,
            "message": f"Chat context updated with {len(request.emails)} emails"
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat/reset")
async def reset_chat():
    """Reset the chat conversation history"""
    try:
        if not chat_agent:
            raise HTTPException(status_code=500, detail="Chat agent not initialized")
        
        result = chat_agent.reset_conversation()
        
        return {
            "success": True,
            "message": result["message"]
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/vector/count")
async def get_vector_count(request: Request):
    """Get the count of emails in vector database for the active account"""
    try:
        active_account = get_account_from_session(request)
        if not active_account:
            print("❌ Vector count: No active account")
            return {
                "success": False,
                "count": 0,
                "error": "No active account"
            }
        
        if not vector_store.collection:
            print("❌ Vector count: Vector store not initialized")
            return {
                "success": False,
                "count": 0,
                "error": "Vector store not initialized"
            }
        
        # Ensure vector store is set to the correct account
        vector_store.set_account(active_account['id'], active_account.get('email'), skip_count=True)
        
        # Count emails for this account in vector store
        try:
            account_id_str = str(active_account['id'])
            print(f"🔍 Vector count: Counting emails for account_id='{account_id_str}'")
            
            # Get all emails for this account (ChromaDB doesn't have efficient count, so we get all IDs)
            results = vector_store.collection.get(
                where={"account_id": account_id_str},
                limit=None  # Get all to count accurately
            )
            count = len(results.get('ids', [])) if results.get('ids') else 0
            print(f"✅ Vector count: Found {count} emails for account {active_account['id']}")
        except Exception as e:
            print(f"❌ Error counting vector emails: {e}")
            import traceback
            traceback.print_exc()
            count = 0
        
        return {
            "success": True,
            "count": count,
            "account_id": active_account['id'],
            "account_email": active_account.get('email', '')
        }
    
    except Exception as e:
        print(f"❌ Vector count endpoint error: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "count": 0,
            "error": str(e)
        }


@app.get("/api/chat/history")
async def get_chat_history():
    """Get the chat conversation history"""
    try:
        if not chat_agent:
            raise HTTPException(status_code=500, detail="Chat agent not initialized")
        
        history = chat_agent.get_conversation_history()
        
        return {
            "success": True,
            "history": history
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/chat/suggestions")
async def get_chat_suggestions():
    """Get suggested questions for the chat"""
    try:
        if not chat_agent:
            raise HTTPException(status_code=500, detail="Chat agent not initialized")
        
        suggestions = chat_agent.suggest_questions()
        
        return {
            "success": True,
            "suggestions": suggestions
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ACCOUNT MANAGEMENT ENDPOINTS
# ============================================================================

@app.get("/api/accounts")
async def get_accounts():
    """Get all email accounts"""
    try:
        if account_manager is None:
            print("⚠️  Account manager is None")
            return {
                "success": True,
                "accounts": [],
                "active_account_id": None
            }
        
        if account_manager.accounts_collection is None:
            print("⚠️  Accounts collection is None (MongoDB not connected)")
            return {
                "success": True,
                "accounts": [],
                "active_account_id": None
            }
        
        accounts = account_manager.get_all_accounts()
        active_account = account_manager.get_active_account()
        
        print(f"📋 Found {len(accounts)} account(s) in MongoDB")
        for acc in accounts:
            print(f"   - Account ID: {acc.get('id')} (type: {type(acc.get('id')).__name__}), Email: {acc.get('email')}, Active: {acc.get('is_active')}")
        
        active_id = active_account['id'] if active_account else None
        print(f"✓ Active account ID: {active_id}")
        
        return {
            "success": True,
            "accounts": accounts,
            "active_account_id": active_id
        }
    except Exception as e:
        print(f"❌ Error getting accounts: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/accounts")
async def add_account(request: AccountAddRequest):
    """Add a new email account"""
    try:
        if account_manager is None:
            raise HTTPException(status_code=500, detail="Account manager not initialized. Please restart the backend.")
        
        if account_manager.accounts_collection is None:
            raise HTTPException(status_code=500, detail="MongoDB not connected. Please check MongoDB connection.")
        
        result = account_manager.add_account(
            email=request.email,
            password=request.password,
            imap_server=request.imap_server,
            imap_port=request.imap_port,
            smtp_server=request.smtp_server,
            smtp_port=request.smtp_port
        )
        
        if 'error' in result:
            print(f"❌ Error adding account: {result['error']}")
            raise HTTPException(status_code=400, detail=result['error'])
        
        # Check if account was updated (already existed)
        if result.get('updated'):
            print(f"✓ Account updated successfully: {request.email}")
            return {
                "success": True,
                "account": result,
                "message": result.get('message', f"Account {request.email} updated successfully")
            }
        else:
            print(f"✓ Account added successfully: {request.email}")
            return {
                "success": True,
                "account": result,
                "message": f"Account {request.email} added successfully"
            }
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Exception adding account: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to add account: {str(e)}")


@app.delete("/api/accounts/{account_id}")
async def delete_account(account_id: int):
    """Delete an email account and all related data"""
    import asyncio
    from concurrent.futures import ThreadPoolExecutor
    
    try:
        print(f"🗑️  Starting deletion of account {account_id}...")
        
        # Run MongoDB and Vector DB deletions in parallel for better performance
        executor = ThreadPoolExecutor(max_workers=4)
        loop = asyncio.get_event_loop()
        
        # Delete all emails from MongoDB for this account
        mongo_result = {"deleted": 0}
        if mongodb_manager.emails_collection is not None:
            mongo_future = loop.run_in_executor(
                executor,
                mongodb_manager.clear_account_emails,
                account_id
            )
        else:
            mongo_future = None
        
        # Delete all replies from MongoDB for this account
        replies_result = {"deleted": 0}
        if mongodb_manager.replies_collection is not None:
            replies_future = loop.run_in_executor(
                executor,
                mongodb_manager.clear_account_replies,
                account_id
            )
        else:
            replies_future = None
        
        # Delete all AI analysis from MongoDB for this account
        analysis_result = {"deleted": 0}
        if mongodb_manager.ai_analysis_collection is not None:
            analysis_future = loop.run_in_executor(
                executor,
                mongodb_manager.clear_account_ai_analysis,
                account_id
            )
        else:
            analysis_future = None
        
        # Delete all emails from vector store for this account
        vector_result = {"deleted": 0}
        if vector_store.collection:
            vector_future = loop.run_in_executor(
                executor,
                vector_store.clear_account_emails,
                account_id
            )
        else:
            vector_future = None
        
        # Wait for all deletions to complete
        if mongo_future:
            mongo_result = await mongo_future
            if mongo_result.get('success'):
                print(f"✓ Deleted {mongo_result.get('deleted', 0)} emails from MongoDB for account {account_id}")
        
        if replies_future:
            replies_result = await replies_future
            if replies_result.get('success'):
                print(f"✓ Deleted {replies_result.get('deleted', 0)} replies from MongoDB for account {account_id}")
        
        if analysis_future:
            analysis_result = await analysis_future
            if analysis_result.get('success'):
                print(f"✓ Deleted {analysis_result.get('deleted', 0)} AI analyses from MongoDB for account {account_id}")
        
        if vector_future:
            vector_result = await vector_future
            if vector_result.get('success'):
                print(f"✓ Deleted {vector_result.get('deleted', 0)} emails from vector store for account {account_id}")
        
        executor.shutdown(wait=False)
        
        # Delete attachments from filesystem
        deleted_files = attachment_storage.delete_account_attachments(account_id)
        print(f"✓ Deleted {deleted_files} attachment files for account {account_id}")
        
        # Delete all sessions for this account
        deleted_sessions = mongodb_manager.delete_account_sessions(account_id)
        # Also remove from memory cache
        sessions_to_remove = [token for token, session in active_sessions.items() 
                              if session.get('account_id') == account_id]
        for token in sessions_to_remove:
            del active_sessions[token]
        if deleted_sessions > 0:
            print(f"✓ Deleted {deleted_sessions} sessions for account {account_id}")
        
        # Finally, delete the account itself
        result = account_manager.remove_account(account_id)
        
        if 'error' in result:
            raise HTTPException(status_code=404, detail=result['error'])
        
        # Get remaining account count after deletion
        remaining_count = account_manager.get_account_count()
        
        print(f"✅ Account {account_id} deletion completed successfully")
        
        return {
            "success": True,
            "message": "Account and all related data deleted successfully",
            "mongo_deleted": mongo_result.get('deleted', 0),
            "replies_deleted": replies_result.get('deleted', 0),
            "analysis_deleted": analysis_result.get('deleted', 0),
            "vector_deleted": vector_result.get('deleted', 0),
            "attachments_deleted": deleted_files,
            "remaining_accounts": remaining_count
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error deleting account {account_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/accounts/all")
async def delete_all_accounts():
    """Delete all accounts and all related data (emails, replies, AI analysis, attachments, vector store)"""
    try:
        print("🗑️  Starting deletion of ALL accounts and data...")
        
        # Get all accounts first to get their IDs
        all_accounts = account_manager.get_all_accounts()
        account_ids = [acc['id'] for acc in all_accounts]
        
        # Delete all emails from MongoDB for all accounts
        mongo_emails_deleted = 0
        if mongodb_manager.emails_collection is not None:
            result = mongodb_manager.emails_collection.delete_many({})
            mongo_emails_deleted = result.deleted_count
            print(f"✓ Deleted {mongo_emails_deleted} emails from MongoDB")
        
        # Delete all replies from MongoDB
        mongo_replies_deleted = 0
        if mongodb_manager.replies_collection is not None:
            result = mongodb_manager.replies_collection.delete_many({})
            mongo_replies_deleted = result.deleted_count
            print(f"✓ Deleted {mongo_replies_deleted} replies from MongoDB")
        
        # Delete all AI analysis from MongoDB
        mongo_analysis_deleted = 0
        if mongodb_manager.ai_analysis_collection is not None:
            result = mongodb_manager.ai_analysis_collection.delete_many({})
            mongo_analysis_deleted = result.deleted_count
            print(f"✓ Deleted {mongo_analysis_deleted} AI analyses from MongoDB")
        
        # Delete all attachments from filesystem for all accounts
        total_attachments_deleted = 0
        for account_id in account_ids:
            deleted_files = attachment_storage.delete_account_attachments(account_id)
            total_attachments_deleted += deleted_files
        if total_attachments_deleted > 0:
            print(f"✓ Deleted {total_attachments_deleted} attachment files")
        
        # Clear all data from vector store
        vector_cleared = False
        if vector_store.collection:
            # Clear vector store completely
            try:
                vector_store.client.delete_collection(name="emails")
                vector_store.collection = vector_store.client.get_or_create_collection(
                    name="emails",
                    metadata={"description": "Email semantic search with account isolation"}
                )
                vector_cleared = True
                print(f"✓ Cleared all data from vector store")
            except Exception as e:
                print(f"⚠️  Error clearing vector store: {e}")
        
        # Delete all sessions
        deleted_sessions = 0
        if mongodb_manager.db is not None:
            sessions_collection = mongodb_manager.db['sessions']
            result = sessions_collection.delete_many({})
            deleted_sessions = result.deleted_count
            # Also clear memory cache
            active_sessions.clear()
            if deleted_sessions > 0:
                print(f"✓ Deleted {deleted_sessions} sessions")
        
        # Delete all accounts
        accounts_deleted = 0
        if account_manager.accounts_collection is not None:
            result = account_manager.clear_all_accounts()
            if result.get('success'):
                accounts_deleted = len(account_ids)
                print(f"✓ Deleted {accounts_deleted} accounts")
        
        print(f"✅ All accounts and data deletion completed")
        
        return {
            "success": True,
            "message": "All accounts and data deleted successfully",
            "accounts_deleted": accounts_deleted,
            "emails_deleted": mongo_emails_deleted,
            "replies_deleted": mongo_replies_deleted,
            "analysis_deleted": mongo_analysis_deleted,
            "attachments_deleted": total_attachments_deleted,
            "sessions_deleted": deleted_sessions,
            "vector_cleared": vector_cleared
        }
    except Exception as e:
        print(f"❌ Error deleting all accounts: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/accounts/{account_id}/activate")
async def activate_account(account_id: int, toggle: bool = True):
    """Set an account as active (toggle mode by default - allows multiple active accounts)"""
    try:
        result = account_manager.set_active_account(account_id, toggle=toggle)
        
        if 'error' in result:
            raise HTTPException(status_code=404, detail=result['error'])
        
        # If account was activated, switch vector store to it (only if it's the first active)
        if result.get('is_active'):
            active_account = account_manager.get_account(account_id)
            if active_account:
                # Only switch vector store if this is the first active account
                active_accounts = account_manager.get_all_accounts()
                active_count = sum(1 for acc in active_accounts if acc.get('is_active'))
                if active_count == 1:  # First active account
                    vector_store.set_account(
                        account_id=active_account['id'],
                        account_email=active_account['email']
                    )
        
        # Disconnect current connection to force reconnect with new account
        if email_agent and email_agent.receiver:
            email_agent.receiver.disconnect()
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/accounts/{account_id}")
async def update_account(account_id: int, request: AccountUpdateRequest):
    """Update account details"""
    try:
        updates = request.dict(exclude_unset=True)
        result = account_manager.update_account(account_id, **updates)
        
        if 'error' in result:
            raise HTTPException(status_code=400, detail=result['error'])
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/accounts/{account_id}/auto-reply")
async def toggle_account_auto_reply(account_id: int, enabled: bool):
    """Toggle auto-reply for a specific account"""
    try:
        result = account_manager.update_account(account_id, auto_reply_enabled=enabled)
        
        if 'error' in result:
            raise HTTPException(status_code=404, detail=result['error'])
        
        status_text = "enabled" if enabled else "disabled"
        account = account_manager.get_account(account_id)
        print(f"🤖 Auto-reply {status_text} for account: {account.get('email') if account else account_id}")
        
        return {
            "success": True,
            "auto_reply_enabled": enabled,
            "message": f"Auto-reply {status_text} for account"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/accounts/{account_id}/custom-prompt")
async def update_account_custom_prompt(account_id: int, request: CustomPromptRequest):
    """Update custom prompt for a specific account"""
    try:
        result = account_manager.update_account(account_id, custom_prompt=request.custom_prompt)
        
        if 'error' in result:
            raise HTTPException(status_code=404, detail=result['error'])
        
        account = account_manager.get_account(account_id)
        print(f"📝 Custom prompt updated for account: {account.get('email') if account else account_id}")
        
        return {
            "success": True,
            "custom_prompt": request.custom_prompt,
            "message": "Custom prompt updated successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/accounts/default-prompt")
async def get_default_prompt():
    """Get the default prompt template"""
    return {
        "success": True,
        "default_prompt": DEFAULT_PROMPT_TEMPLATE
    }


@app.get("/api/accounts/active")
async def get_active_account():
    """Get the currently active account"""
    try:
        account = account_manager.get_active_account()
        
        if not account:
            return {
                "success": False,
                "message": "No active account"
            }
        
        # Remove password from response
        account_safe = {k: v for k, v in account.items() if k != 'password'}
        
        return {
            "success": True,
            "account": account_safe
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Configuration Management Endpoints

class ConfigRequest(BaseModel):
    azure_openai_key: str
    azure_openai_endpoint: str
    azure_openai_deployment: str
    azure_openai_api_version: str
    ai_provider: str
    mongodb_uri: str
    mongodb_db_name: str
    google_client_id: str
    google_client_secret: str
    google_redirect_uri: str
    session_secret: str
    frontend_url: str
    cors_origins: str
    auto_reply_enabled: bool


@app.get("/api/config")
async def get_config():
    """Get current application configuration from database"""
    try:
        if not config_manager:
            raise HTTPException(status_code=500, detail="Config manager not initialized")
        
        config_data = config_manager.get_all_config()
        return {
            "success": True,
            "config": {
                "azure_openai_key": config_data.get("azure_openai_key", ""),
                "azure_openai_endpoint": config_data.get("azure_openai_endpoint", ""),
                "azure_openai_deployment": config_data.get("azure_openai_deployment", "gpt-4.1-mini"),
                "azure_openai_api_version": config_data.get("azure_openai_api_version", "2024-12-01-preview"),
                "ai_provider": config_data.get("ai_provider", "azure"),
                "mongodb_uri": config_data.get("mongodb_uri", "mongodb://localhost:27017/"),
                "mongodb_db_name": config_data.get("mongodb_db_name", "email_agent"),
                "google_client_id": config_data.get("google_client_id", ""),
                "google_client_secret": config_data.get("google_client_secret", ""),
                "google_redirect_uri": config_data.get("google_redirect_uri", "http://localhost:8000/api/auth/callback"),
                "session_secret": config_data.get("session_secret", ""),
                "frontend_url": config_data.get("frontend_url", "http://localhost:3000"),
                "cors_origins": config_data.get("cors_origins", "http://localhost:3000,http://127.0.0.1:3000"),
                "auto_reply_enabled": config_data.get("auto_reply_enabled", "true").lower() == "true"
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/config")
async def save_config(request: ConfigRequest):
    """Save application configuration to database"""
    try:
        if not config_manager:
            raise HTTPException(status_code=500, detail="Config manager not initialized")
        
        config_dict = {
            "azure_openai_key": request.azure_openai_key,
            "azure_openai_endpoint": request.azure_openai_endpoint,
            "azure_openai_deployment": request.azure_openai_deployment,
            "azure_openai_api_version": request.azure_openai_api_version,
            "ai_provider": request.ai_provider,
            "mongodb_uri": request.mongodb_uri,
            "mongodb_db_name": request.mongodb_db_name,
            "google_client_id": request.google_client_id,
            "google_client_secret": request.google_client_secret,
            "google_redirect_uri": request.google_redirect_uri,
            "session_secret": request.session_secret,
            "frontend_url": request.frontend_url,
            "cors_origins": request.cors_origins,
            "auto_reply_enabled": "true" if request.auto_reply_enabled else "false"
        }
        
        success = config_manager.save_config(config_dict)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to save configuration")
        
        return {
            "success": True,
            "message": "Configuration saved successfully. Please restart the backend for changes to take effect."
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/config/init-from-env")
async def init_config_from_env():
    """Initialize database with current .env values (overwrites existing)"""
    try:
        if not config_manager:
            raise HTTPException(status_code=500, detail="Config manager not initialized")
        
        # Force overwrite to always load from .env when explicitly called
        success = config_manager.initialize_from_env(force_overwrite=True)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to initialize configuration")
        
        return {
            "success": True,
            "message": "Configuration initialized from .env to database"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# VECTOR SEARCH ENDPOINTS
# ============================================================================

@app.post("/api/search/semantic")
async def semantic_search(request: SemanticSearchRequest):
    """Semantic search for emails using vector similarity"""
    try:
        if not vector_store.collection:
            raise HTTPException(status_code=503, detail="Vector store not initialized")
        
        results = vector_store.semantic_search(
            query=request.query,
            n_results=request.n_results,
            filter_metadata=request.filter_metadata
        )
        
        if 'error' in results:
            raise HTTPException(status_code=500, detail=results['error'])
        
        return results
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/search/similar/{email_id}")
async def find_similar(email_id: str, n_results: int = 5):
    """Find emails similar to a specific email"""
    try:
        if not vector_store.collection:
            raise HTTPException(status_code=503, detail="Vector store not initialized")
        
        # Get the email data (would need to fetch from receiver)
        # For now, use semantic search with email ID
        results = vector_store.semantic_search(
            query=email_id,
            n_results=n_results
        )
        
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/search/stats")
async def get_vector_stats():
    """Get vector store statistics"""
    try:
        stats = vector_store.get_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/mongodb/stats")
async def get_mongodb_stats():
    """Get MongoDB storage statistics"""
    try:
        # Get active account
        active_account = account_manager.get_active_account()
        if not active_account:
            return {"error": "No active account"}
        
        stats = mongodb_manager.get_stats(active_account['id'])
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ai-analysis/process-existing")
async def process_existing_emails(limit: int = 10):
    """
    Process existing emails in MongoDB with AI analysis
    Useful for retroactively analyzing emails
    """
    try:
        # Get active account
        active_account = account_manager.get_active_account()
        if not active_account:
            raise HTTPException(status_code=400, detail="No active account")
        
        if not email_agent or not email_agent.ai_agent:
            raise HTTPException(status_code=500, detail="AI agent not available")
        
        # Get emails from MongoDB that don't have analysis yet
        emails_to_process = mongodb_manager.get_emails(
            account_id=active_account['id'],
            limit=limit
        )
        
        processed_count = 0
        for email in emails_to_process:
            message_id = email.get('message_id')
            if not message_id:
                continue
            
            # Check if already analyzed
            existing_analysis = mongodb_manager.get_ai_analysis(message_id, active_account['id'])
            if existing_analysis:
                continue  # Skip already analyzed emails
            
            try:
                # Get custom prompt from active account
                custom_prompt = active_account.get('custom_prompt', '')
                if custom_prompt and custom_prompt.strip():
                    print(f"📝 Using custom prompt for analysis (account {active_account.get('email')})")
                
                # Run AI analysis with custom prompt
                analysis = email_agent.ai_agent.analyze_email(email, custom_prompt=custom_prompt)
                
                # Save to MongoDB
                result = mongodb_manager.save_ai_analysis(
                    message_id,
                    active_account['id'],
                    analysis
                )
                
                if result.get('success'):
                    processed_count += 1
                    print(f"✅ Analyzed: {email.get('subject', 'No subject')[:50]}")
            
            except Exception as e:
                print(f"❌ Failed to analyze {email.get('subject', '')}: {e}")
        
        return {
            "success": True,
            "message": f"Processed {processed_count} emails",
            "processed": processed_count
        }
    
    except Exception as e:
        print(f"Error processing existing emails: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/mongodb/migrate")
async def migrate_mongodb_emails():
    """
    Migrate existing emails in MongoDB to add date_str field
    This is needed for proper sorting
    """
    try:
        # Get active account
        active_account = account_manager.get_active_account()
        if not active_account:
            raise HTTPException(status_code=400, detail="No active account")
        
        if mongodb_manager.emails_collection is None:
            raise HTTPException(status_code=500, detail="MongoDB not connected")
        
        # Get all emails without date_str
        emails_to_update = list(
            mongodb_manager.emails_collection.find(
                {
                    "account_id": active_account['id'],
                    "date_str": {"$exists": False}
                }
            )
        )
        
        updated_count = 0
        for email in emails_to_update:
            if 'date' in email:
                try:
                    from email.utils import parsedate_to_datetime
                    email_date = parsedate_to_datetime(email['date'])
                    date_str = email_date.strftime('%Y-%m-%d %H:%M:%S')
                    
                    mongodb_manager.emails_collection.update_one(
                        {"_id": email["_id"]},
                        {"$set": {"date_str": date_str}}
                    )
                    updated_count += 1
                except:
                    # Use saved_at or current time as fallback
                    date_str = email.get('saved_at', datetime.utcnow()).strftime('%Y-%m-%d %H:%M:%S')
                    mongodb_manager.emails_collection.update_one(
                        {"_id": email["_id"]},
                        {"$set": {"date_str": date_str}}
                    )
                    updated_count += 1
        
        return {
            "success": True,
            "message": f"Migrated {updated_count} emails",
            "updated": updated_count
        }
    
    except Exception as e:
        print(f"Error migrating emails: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/ai-analysis/stats")
async def get_ai_analysis_stats():
    """Get AI analysis statistics"""
    try:
        # Get active account
        active_account = account_manager.get_active_account()
        if not active_account:
            raise HTTPException(status_code=400, detail="No active account")
        
        stats = mongodb_manager.get_analysis_stats(active_account['id'])
        return stats
    except Exception as e:
        print(f"Error getting AI analysis stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/ai-analysis/{message_id}")
async def get_email_ai_analysis(message_id: str):
    """Get AI analysis for a specific email"""
    try:
        # Get active account
        active_account = account_manager.get_active_account()
        if not active_account:
            raise HTTPException(status_code=400, detail="No active account")
        
        analysis = mongodb_manager.get_ai_analysis(message_id, active_account['id'])
        
        # Return success with null analysis if not found (don't throw 404)
        return {
            "success": True,
            "analysis": analysis  # Will be None if not found
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting AI analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/reply/{message_id}")
async def get_email_reply(message_id: str):
    """Get reply data for a specific email"""
    try:
        # Get active account
        active_account = account_manager.get_active_account()
        if not active_account:
            raise HTTPException(status_code=400, detail="No active account")
        
        reply = mongodb_manager.get_reply(message_id, active_account['id'])
        
        # Return success with null reply if not found
        return {
            "success": True,
            "reply": reply  # Will be None if not found
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting reply: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/email-details/{message_id}")
async def get_email_details_batch(message_id: str):
    """
    Get both AI analysis and reply in one request (faster than separate calls)
    """
    try:
        active_account = account_manager.get_active_account()
        if not active_account:
            raise HTTPException(status_code=400, detail="No active account")
        
        account_id = active_account['id']
        
        # Load both in parallel (if we had async MongoDB, but for now sequential)
        analysis = mongodb_manager.get_ai_analysis(message_id, account_id)
        reply = mongodb_manager.get_reply(message_id, account_id)
        
        return {
            "success": True,
            "analysis": analysis,  # Will be None if not found
            "reply": reply  # Will be None if not found
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting email details: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/mongodb/emails")
async def get_mongodb_emails(
    request: Request,
    limit: int = 20,
    skip: int = 0,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    unread_only: bool = False,
    auto_replied_only: bool = False
):
    """
    Get emails from MongoDB storage
    
    Args:
        limit: Number of emails to return (max 200)
        skip: Number of emails to skip (for pagination)
        date_from: Start date filter (YYYY-MM-DD)
        date_to: End date filter (YYYY-MM-DD)
        unread_only: Only return unread emails
        auto_replied_only: Only return emails that have been auto-replied
    """
    import sys
    print(f"🔍 API CALLED: get_mongodb_emails(date_from={date_from}, date_to={date_to}, limit={limit}, skip={skip})", file=sys.stderr, flush=True)
    try:
        # Get account from session (session-based, not global)
        active_account = get_account_from_session(request)
        if not active_account:
            raise HTTPException(status_code=400, detail="No active account")
        
        # Limit max results
        limit = min(limit, 200)
        
        # Get emails from MongoDB with pagination
        # Exclude large HTML/text bodies for list view (much faster loading)
        print(f"🔍 get_mongodb_emails called: account_id={active_account['id']} (type: {type(active_account['id'])}), date_from={date_from}, date_to={date_to}, limit={limit}, skip={skip}")
        
        # First, check total emails in MongoDB for this account (without date filter)
        if mongodb_manager.emails_collection is not None:
            total_count_no_filter = mongodb_manager.emails_collection.count_documents({"account_id": active_account['id']})
            print(f"🔍 Total emails in MongoDB for account {active_account['id']}: {total_count_no_filter}")
            
            # Test the date filter query directly
            if date_from and date_to:
                from datetime import datetime, timedelta
                date_from_start = f"{date_from} 00:00:00"
                date_obj = datetime.strptime(date_to, "%Y-%m-%d")
                next_day = date_obj + timedelta(days=1)
                date_to_end = next_day.strftime("%Y-%m-%d 00:00:00")
                test_query = {
                    "account_id": active_account['id'],
                    "date_str": {
                        "$gte": date_from_start,
                        "$lt": date_to_end
                    }
                }
                test_count = mongodb_manager.emails_collection.count_documents(test_query)
                print(f"🔍 Direct test query matches {test_count} emails: {test_query}")
            
            # Get a sample email to see date_str format
            sample_email = mongodb_manager.emails_collection.find_one(
                {"account_id": active_account['id']},
                {"date_str": 1, "subject": 1, "date": 1}
            )
            if sample_email:
                print(f"🔍 Sample email in MongoDB: date_str='{sample_email.get('date_str')}', subject='{sample_email.get('subject', 'N/A')[:50]}'")
        
        # If filtering by auto-replied only, get list of message_ids that have replies
        replied_message_ids = set()
        if auto_replied_only:
            print(f"🔍 Filtering for auto-replied emails only")
            if mongodb_manager.replies_collection is not None:
                replied_docs = mongodb_manager.replies_collection.find(
                    {"account_id": active_account['id']},
                    {"email_message_id": 1}
                )
                replied_message_ids = {doc.get('email_message_id') for doc in replied_docs if doc.get('email_message_id')}
                print(f"🔍 Found {len(replied_message_ids)} unique email_message_ids in replies collection")
                
                if len(replied_message_ids) == 0:
                    print(f"⚠️  No replies found for account {active_account['id']}, returning empty list")
                    return {
                        "success": True,
                        "emails": [],
                        "count": 0,
                        "total": 0,
                        "skip": skip,
                        "limit": limit,
                        "has_more": False
                    }
                
                # Also get all possible message_id formats from emails collection for these replied emails
                # This handles cases where reply uses one format but email uses another
                if mongodb_manager.emails_collection is not None:
                    # Find emails that match any of the replied message_ids
                    email_docs = mongodb_manager.emails_collection.find(
                        {
                            "account_id": active_account['id'],
                            "$or": [
                                {"message_id": {"$in": list(replied_message_ids)}},
                                {"gmail_synthetic_id": {"$in": list(replied_message_ids)}}
                            ]
                        },
                        {"message_id": 1, "gmail_synthetic_id": 1}
                    )
                    # Collect all possible IDs for matching
                    all_possible_ids = set(replied_message_ids)
                    for email_doc in email_docs:
                        if email_doc.get('message_id'):
                            all_possible_ids.add(email_doc.get('message_id'))
                        if email_doc.get('gmail_synthetic_id'):
                            all_possible_ids.add(email_doc.get('gmail_synthetic_id'))
                    replied_message_ids = all_possible_ids
                    print(f"🔍 Expanded to {len(replied_message_ids)} possible message_id formats for matching")
            else:
                print(f"⚠️  Replies collection is None, returning empty list")
                return {
                    "success": True,
                    "emails": [],
                    "count": 0,
                    "total": 0,
                    "skip": skip,
                    "limit": limit,
                    "has_more": False
                }
        else:
            print(f"🔍 Showing all emails (not filtering by reply status)")
        
        emails = mongodb_manager.get_emails(
            account_id=active_account['id'],
            limit=limit * 3 if auto_replied_only else limit,  # Get more to filter down (in case of format mismatches)
            skip=skip,
            date_from=date_from,
            date_to=date_to,
            unread_only=unread_only,
            exclude_bodies=True  # Exclude html_body and text_body for faster list loading
        )
        
        # Filter by reply status if needed
        if auto_replied_only:
            original_count = len(emails)
            emails = [
                email for email in emails 
                if (email.get('message_id') in replied_message_ids or 
                    email.get('gmail_synthetic_id') in replied_message_ids)
            ]
            print(f"🔍 Filtered from {original_count} to {len(emails)} auto-replied emails (matched by message_id or gmail_synthetic_id)")
            # Limit to requested amount after filtering
            emails = emails[:limit]
        
        # Get accurate total count with same filters as the query
        if mongodb_manager.emails_collection is not None:
            count_query = {"account_id": active_account['id']}
            
            # Apply same date filters (matching logic from mongodb_manager.get_emails)
            if date_from or date_to:
                date_query = {}
                if date_from:
                    date_query['$gte'] = f"{date_from} 00:00:00"
                if date_to:
                    from datetime import datetime, timedelta
                    date_obj = datetime.strptime(date_to, "%Y-%m-%d")
                    next_day = date_obj + timedelta(days=1)
                    date_query['$lt'] = next_day.strftime("%Y-%m-%d 00:00:00")
                
                # Special handling for "today" (when date_from == date_to)
                # Use regex to match date prefix - this handles timezone variations better
                if date_from and date_to and date_from == date_to:
                    date_prefix = date_from  # e.g., "2025-11-15"
                    import re as re_module
                    escaped_prefix = re_module.escape(date_prefix)
                    date_query = {'$regex': f'^{escaped_prefix}'}
                    print(f"🔍 Today filter (count): Using regex for date prefix '{date_prefix}'")
                    
                    # Debug: Show what dates are available
                    all_dates = mongodb_manager.emails_collection.distinct("date_str", {"account_id": active_account['id']})
                    if all_dates:
                        unique_dates = set()
                        for dt in all_dates[:20]:
                            if dt and isinstance(dt, str) and len(dt) >= 10:
                                unique_dates.add(dt[:10])
                        print(f"🔍 Available dates in DB: {sorted(list(unique_dates))}")
                        print(f"🔍 Looking for: '{date_prefix}'")
                
                if date_query:
                    count_query['date_str'] = date_query
            
            # Apply unread filter
            if unread_only:
                count_query['is_read'] = False
            
            # Apply auto-replied filter for count (check both message_id formats)
            if auto_replied_only and replied_message_ids:
                count_query['$or'] = [
                    {'message_id': {'$in': list(replied_message_ids)}},
                    {'gmail_synthetic_id': {'$in': list(replied_message_ids)}}
                ]
            
            total_count = mongodb_manager.emails_collection.count_documents(count_query)
        else:
            total_count = len(emails)
        
        return {
            "success": True,
            "emails": emails,
            "count": len(emails),
            "total": total_count,
            "skip": skip,
            "limit": limit,
            "has_more": (skip + len(emails)) < total_count
        }
    
    except Exception as e:
        print(f"Error fetching MongoDB emails: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/mongodb/emails/count")
async def get_mongodb_emails_count(
    request: Request,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    unread_only: bool = False,
    account_id: Optional[int] = None
):
    """
    Get email count from MongoDB storage for an account
    
    Args:
        date_from: Start date filter (YYYY-MM-DD)
        date_to: End date filter (YYYY-MM-DD)
        unread_only: Only count unread emails
        account_id: Specific account ID (defaults to session account)
    
    Returns:
        Email count matching the filters
    """
    try:
        # Get account (use provided account_id or session account)
        if account_id:
            account = account_manager.get_account(account_id)
            if not account:
                raise HTTPException(status_code=404, detail=f"Account {account_id} not found")
            target_account = account
        else:
            target_account = get_account_from_session(request)
            if not target_account:
                raise HTTPException(status_code=400, detail="No active account")
        
        if mongodb_manager.emails_collection is None:
            raise HTTPException(status_code=500, detail="MongoDB not connected")
        
        # Build query
        query = {"account_id": target_account['id']}
        
        # Add date filters if provided
        if date_from or date_to:
            date_query = {}
            if date_from:
                date_from_start = f"{date_from} 00:00:00"
                date_query['$gte'] = date_from_start
            if date_to:
                from datetime import datetime, timedelta
                date_obj = datetime.strptime(date_to, "%Y-%m-%d")
                next_day = date_obj + timedelta(days=1)
                date_to_end = next_day.strftime("%Y-%m-%d 00:00:00")
                date_query['$lt'] = date_to_end
            
            # Special handling for "today" (when date_from == date_to)
            # Use regex to match date prefix - this handles timezone variations better
            if date_from and date_to and date_from == date_to:
                date_prefix = date_from  # e.g., "2025-11-15"
                import re as re_module
                escaped_prefix = re_module.escape(date_prefix)
                date_query = {'$regex': f'^{escaped_prefix}'}
                print(f"🔍 Today filter (email count): Using regex for date prefix '{date_prefix}'")
                
                # Debug: Show what dates are available
                all_dates = mongodb_manager.emails_collection.distinct("date_str", {"account_id": target_account['id']})
                if all_dates:
                    unique_dates = set()
                    for dt in all_dates[:20]:
                        if dt and isinstance(dt, str) and len(dt) >= 10:
                            unique_dates.add(dt[:10])
                    print(f"🔍 Available dates in DB: {sorted(list(unique_dates))}")
                    print(f"🔍 Looking for: '{date_prefix}'")
            
            if date_query:
                query['date_str'] = date_query
        
        # Add unread filter if needed
        if unread_only:
            query['is_read'] = False
        
        # Get count
        count = mongodb_manager.emails_collection.count_documents(query)
        
        print(f"🔍 Email count for account {target_account['id']}: {count} (filters: date_from={date_from}, date_to={date_to}, unread_only={unread_only})")
        
        return {
            "success": True,
            "count": count,
            "account_id": target_account['id'],
            "account_email": target_account.get('email', ''),
            "filters": {
                "date_from": date_from,
                "date_to": date_to,
                "unread_only": unread_only
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting email count: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/mongodb/email/{message_id}")
async def get_single_email(message_id: str):
    """Get a single email with full body content"""
    try:
        active_account = account_manager.get_active_account()
        if not active_account:
            raise HTTPException(status_code=400, detail="No active account")
        
        # Find email by message_id or gmail_synthetic_id (with full body - no projection to exclude bodies)
        # Handle both actual Message-ID and synthetic Gmail ID formats
        email_doc = mongodb_manager.emails_collection.find_one({
            "$or": [
                {"message_id": message_id, "account_id": active_account['id']},
                {"gmail_synthetic_id": message_id, "account_id": active_account['id']}
            ]
        }, {'_id': 0})  # Explicitly include all fields including text_body and html_body
        
        if not email_doc:
            raise HTTPException(status_code=404, detail="Email not found")
        
        return {
            "success": True,
            "email": email_doc
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/search/clear")
async def clear_vector_store():
    """Clear all emails from vector store"""
    try:
        result = vector_store.clear()
        
        if 'error' in result:
            raise HTTPException(status_code=500, detail=result['error'])
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/search/remove-sent-emails")
async def remove_sent_emails_from_vector():
    """Remove sent emails (auto-replies) from vector store"""
    try:
        active_account = account_manager.get_active_account()
        if not active_account:
            raise HTTPException(status_code=400, detail="No active account")
        
        account_email = active_account.get('email', '')
        account_id = active_account.get('id')
        
        if not account_email:
            raise HTTPException(status_code=400, detail="Account email not found")
        
        result = vector_store.remove_sent_emails(account_email, account_id)
        
        if 'error' in result:
            raise HTTPException(status_code=500, detail=result['error'])
        
        return {
            "success": True,
            "deleted": result.get('deleted', 0),
            "message": result.get('message', 'Sent emails removed')
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# MONITORING ENDPOINTS
# ============================================================================

@app.get("/api/monitoring/status")
async def get_monitoring_status():
    """Get real-time monitoring status"""
    try:
        if not email_agent:
            raise HTTPException(status_code=500, detail="Email agent not initialized")
        
        return {
            "monitoring": email_agent.monitoring,
            "auto_reply_enabled": email_agent.auto_reply_enabled,
            "last_check": email_agent.last_check_time.isoformat() if email_agent.last_check_time else None,
            "processed_count": len(email_agent.processed_emails)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/auto-reply/status")
async def get_auto_reply_status():
    """Get auto-reply status"""
    try:
        if not email_agent:
            raise HTTPException(status_code=500, detail="Email agent not initialized")
        
        return {
            "success": True,
            "auto_reply_enabled": email_agent.auto_reply_enabled
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/auto-reply/toggle")
async def toggle_auto_reply(request: AutoReplyToggleRequest):
    """Toggle auto-reply on or off"""
    try:
        if not email_agent:
            raise HTTPException(status_code=500, detail="Email agent not initialized")
        
        enabled = request.enabled
        email_agent.auto_reply_enabled = enabled
        status_text = "enabled" if enabled else "disabled"
        print(f"🤖 Auto-reply {status_text} (global setting updated)")
        
        return {
            "success": True,
            "auto_reply_enabled": email_agent.auto_reply_enabled,
            "message": f"Auto-reply {status_text}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/monitoring/start")
async def start_monitoring(check_interval: int = 30):
    """Start real-time email monitoring"""
    try:
        if not email_agent:
            raise HTTPException(status_code=500, detail="Email agent not initialized")
        
        email_agent.start_monitoring(check_interval=check_interval)
        
        return {
            "success": True,
            "message": f"Monitoring started (check every {check_interval}s)"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/monitoring/stop")
async def stop_monitoring():
    """Stop real-time email monitoring"""
    try:
        if not email_agent:
            raise HTTPException(status_code=500, detail="Email agent not initialized")
        
        email_agent.stop_monitoring()
        
        return {
            "success": True,
            "message": "Monitoring stopped"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# NOTIFICATIONS (Server-Sent Events)
# ============================================================================

async def notification_stream():
    """Generator for Server-Sent Events"""
    while True:
        try:
            # Wait for notification with timeout
            notification = await asyncio.wait_for(notification_queue.get(), timeout=30.0)
            
            # Format as SSE
            yield f"data: {json_lib.dumps(notification)}\n\n"
            
        except asyncio.TimeoutError:
            # Send keepalive every 30 seconds
            yield f"data: {json_lib.dumps({'type': 'keepalive'})}\n\n"
        except Exception as e:
            print(f"SSE error: {e}")
            break


@app.get("/api/notifications/stream")
async def notifications(token: str = None):
    """
    Server-Sent Events endpoint for real-time notifications
    Connect to this endpoint to receive push notifications when new emails arrive
    Requires session token as query parameter for authentication
    """
    # Validate token
    if not token:
        raise HTTPException(status_code=401, detail="Missing authentication token")
    
    # Check if token exists in active sessions
    if token not in active_sessions:
        # Try to validate token and recreate session
        try:
            token_data = session_serializer.loads(token, max_age=604800)  # 7 days
            account_id = token_data.get('account_id')
            
            if account_id:
                # Recreate session
                active_sessions[token] = {
                    'account_id': account_id,
                    'email': token_data.get('email', ''),
                    'created_at': datetime.utcnow().isoformat()
                }
            else:
                raise HTTPException(status_code=401, detail="Invalid token")
        except Exception as e:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    return StreamingResponse(
        notification_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable buffering in nginx
        }
    )


async def broadcast_notification(notification: Dict):
    """Broadcast notification to all connected clients"""
    try:
        await notification_queue.put(notification)
    except Exception as e:
        print(f"Failed to broadcast notification: {e}")


# ============================================================================
# ATTACHMENT ENDPOINTS
# ============================================================================

@app.get("/api/emails/{email_id}/attachments")
async def get_email_attachments(email_id: str):
    """Get all attachments from an email with content"""
    try:
        if not email_agent:
            raise HTTPException(status_code=500, detail="Email agent not initialized")
        
        receiver = email_agent.receiver
        
        # Ensure connection
        if not receiver.mail:
            receiver.connect()
        
        attachments = receiver.get_all_attachments(email_id)
        
        return {
            "success": True,
            "email_id": email_id,
            "count": len(attachments),
            "attachments": attachments
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/emails/{email_id}/attachments/{filename}")
async def get_specific_attachment(email_id: str, filename: str):
    """Get a specific attachment from an email"""
    try:
        if not email_agent:
            raise HTTPException(status_code=500, detail="Email agent not initialized")
        
        receiver = email_agent.receiver
        
        # Ensure connection
        if not receiver.mail:
            receiver.connect()
        
        attachment = receiver.get_attachment(email_id, filename)
        
        if not attachment:
            raise HTTPException(status_code=404, detail="Attachment not found")
        
        return {
            "success": True,
            "attachment": attachment
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Gmail API Endpoints
@app.get("/api/gmail/auth")
async def gmail_auth_status():
    """Check Gmail API authentication status"""
    try:
        if not config.GMAIL_USE_API:
            return {
                "success": False,
                "message": "Gmail API is disabled. Set GMAIL_USE_API=true in .env"
            }
        
        active_account = account_manager.get_active_account()
        if not active_account:
            return {
                "success": False,
                "message": "No active account"
            }
        
        email_address = active_account['email']
        gmail_client = GmailAPIClient(email_address)
        
        if gmail_client.authenticate():
            profile = gmail_client.get_profile()
            return {
                "success": True,
                "authenticated": True,
                "email": email_address,
                "history_id": gmail_client.history_id,
                "profile": profile
            }
        else:
            return {
                "success": False,
                "authenticated": False,
                "message": "Authentication failed. Check credentials."
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@app.get("/api/mongodb/indexes")
async def get_mongodb_indexes():
    """Get list of all MongoDB indexes for performance monitoring"""
    try:
        indexes = {}
        
        if mongodb_manager.emails_collection is not None:
            emails_indexes = list(mongodb_manager.emails_collection.list_indexes())
            indexes['emails'] = [
                {
                    "name": idx.get('name', ''),
                    "key": idx.get('key', {}),
                    "background": idx.get('background', False)
                }
                for idx in emails_indexes
            ]
        
        if mongodb_manager.ai_analysis_collection is not None:
            ai_indexes = list(mongodb_manager.ai_analysis_collection.list_indexes())
            indexes['ai_analysis'] = [
                {
                    "name": idx.get('name', ''),
                    "key": idx.get('key', {}),
                    "background": idx.get('background', False)
                }
                for idx in ai_indexes
            ]
        
        if mongodb_manager.replies_collection is not None:
            replies_indexes = list(mongodb_manager.replies_collection.list_indexes())
            indexes['replies'] = [
                {
                    "name": idx.get('name', ''),
                    "key": idx.get('key', {}),
                    "background": idx.get('background', False)
                }
                for idx in replies_indexes
            ]
        
        return {
            "success": True,
            "indexes": indexes,
            "total_indexes": sum(len(v) for v in indexes.values())
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@app.get("/api/mongodb/email/{message_id}/debug")
async def debug_email_structure(message_id: str):
    """Debug endpoint to inspect email structure from IMAP"""
    try:
        if not email_agent:
            raise HTTPException(status_code=500, detail="Email agent not initialized")
        
        active_account = account_manager.get_active_account()
        if not active_account:
            raise HTTPException(status_code=400, detail="No active account")
        
        receiver = email_agent.receiver
        
        # Ensure connection
        try:
            receiver.mail.noop()
        except:
            receiver.connect()
        
        # Get email from MongoDB first
        email_doc = mongodb_manager.emails_collection.find_one({
            "message_id": message_id,
            "account_id": active_account['id']
        })
        
        if not email_doc:
            raise HTTPException(status_code=404, detail="Email not found in MongoDB")
        
        # Try to find and fetch the raw email
        emails = []
        if email_doc.get('subject'):
            subject = email_doc.get('subject', '').strip()
            search_query = f'SUBJECT "{subject}"'
            emails = receiver.search_emails(search_query, folder='INBOX', limit=5)
            
            if emails and email_doc.get('from'):
                from_addr = email_doc.get('from', '')
                emails = [e for e in emails if from_addr.lower() in e.get('from', '').lower()]
        
        if not emails:
            return {
                "success": False,
                "message": "Email not found in IMAP",
                "email_doc": {
                    "subject": email_doc.get('subject'),
                    "from": email_doc.get('from'),
                    "message_id": email_doc.get('message_id'),
                    "text_body_length": len(email_doc.get('text_body', '')),
                    "html_body_length": len(email_doc.get('html_body', ''))
                }
            }
        
        email = emails[0]
        
        # Return debug info
        return {
            "success": True,
            "email_found": True,
            "structure": {
                "subject": email.get('subject'),
                "from": email.get('from'),
                "message_id": email.get('message_id'),
                "text_body_length": len(email.get('text_body', '')),
                "html_body_length": len(email.get('html_body', '')),
                "text_body_preview": email.get('text_body', '')[:200] if email.get('text_body') else None,
                "html_body_preview": email.get('html_body', '')[:200] if email.get('html_body') else None,
                "has_attachments": email.get('has_attachments', False)
            }
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@app.post("/api/mongodb/email/{message_id}/refetch")
async def refetch_email_from_imap(message_id: str):
    """Re-fetch an email from IMAP and update it in MongoDB (useful for fixing empty bodies)"""
    try:
        if not email_agent:
            raise HTTPException(status_code=500, detail="Email agent not initialized")
        
        if not mongodb_manager or mongodb_manager.emails_collection is None:
            raise HTTPException(status_code=500, detail="MongoDB not connected")
        
        active_account = account_manager.get_active_account()
        if not active_account:
            raise HTTPException(status_code=400, detail="No active account")
        
        # Get email from MongoDB first to get subject/date for search
        email_doc = mongodb_manager.emails_collection.find_one({
            "message_id": message_id,
            "account_id": active_account['id']
        })
        
        if not email_doc:
            raise HTTPException(status_code=404, detail=f"Email with Message-ID {message_id} not found in MongoDB")
        
        receiver = email_agent.receiver
        
        # Ensure connection
        try:
            receiver.mail.noop()
        except:
            receiver.connect()
        
        # Try multiple search strategies
        emails = []
        
        # Strategy 1: Search by Message-ID (exact match)
        try:
            # Try with angle brackets
            search_query = f'HEADER Message-ID "{message_id}"'
            emails = receiver.search_emails(search_query, folder='INBOX', limit=5)
            
            # Try without angle brackets
            if not emails:
                clean_msg_id = message_id.strip('<>')
                search_query = f'HEADER Message-ID "{clean_msg_id}"'
                emails = receiver.search_emails(search_query, folder='INBOX', limit=5)
        except Exception as e:
            print(f"⚠️  Message-ID search failed: {e}")
        
        # Strategy 2: If Message-ID search fails, search by subject and date
        if not emails and email_doc.get('subject'):
            try:
                subject = email_doc.get('subject', '').strip()
                # Escape special characters in subject for IMAP search
                subject = subject.replace('"', '\\"')
                
                # Search by subject (recent emails)
                search_query = f'SUBJECT "{subject}"'
                emails = receiver.search_emails(search_query, folder='INBOX', limit=10)
                
                # Filter by matching from address if available
                if emails and email_doc.get('from'):
                    from_addr = email_doc.get('from', '')
                    emails = [e for e in emails if from_addr.lower() in e.get('from', '').lower()]
            except Exception as e:
                print(f"⚠️  Subject search failed: {e}")
        
        # Strategy 3: Get recent emails and match by subject + from
        if not emails and email_doc.get('subject') and email_doc.get('from'):
            try:
                # Get recent emails (last 50)
                recent_emails = receiver.get_emails(folder='INBOX', limit=50, unread_only=False)
                
                # Match by subject and from
                subject = email_doc.get('subject', '').strip().lower()
                from_addr = email_doc.get('from', '').lower()
                
                for email in recent_emails:
                    if (email.get('subject', '').strip().lower() == subject and 
                        from_addr in email.get('from', '').lower()):
                        emails = [email]
                        break
            except Exception as e:
                print(f"⚠️  Recent emails search failed: {e}")
        
        if not emails:
            raise HTTPException(
                status_code=404, 
                detail=f"Email with Message-ID {message_id} not found in IMAP. It may have been deleted or moved."
            )
        
        # Get the first matching email (should have updated body)
        updated_email = emails[0]
        
        # Debug: Log body extraction results
        text_body_len = len(updated_email.get('text_body', ''))
        html_body_len = len(updated_email.get('html_body', ''))
        print(f"📧 Re-fetched email: {updated_email.get('subject', 'No subject')}")
        print(f"   Text body length: {text_body_len} chars")
        print(f"   HTML body length: {html_body_len} chars")
        if text_body_len == 0 and html_body_len == 0:
            print(f"   ⚠️  WARNING: Both text and HTML bodies are empty!")
            print(f"   Email structure: subject={updated_email.get('subject')}, from={updated_email.get('from')}")
            print(f"   This email may have no body content (subject-only email)")
            # Try to fetch raw email for inspection
            try:
                receiver.mail.select('INBOX')
                # Find the email again to get raw structure
                if email_doc.get('subject'):
                    subject = email_doc.get('subject', '').strip().replace('"', '\\"')
                    status, messages = receiver.mail.search(None, f'SUBJECT "{subject}"')
                    if status == "OK" and messages[0]:
                        email_ids = messages[0].split()
                        if email_ids:
                            # Get the first match
                            status, msg_data = receiver.mail.fetch(email_ids[-1], "(RFC822)")
                            if status == "OK":
                                import email as email_lib
                                raw_msg = email_lib.message_from_bytes(msg_data[0][1])
                                # Log email structure
                                print(f"   Raw email Content-Type: {raw_msg.get_content_type()}")
                                print(f"   Raw email IsMultipart: {raw_msg.is_multipart()}")
                                if raw_msg.is_multipart():
                                    print(f"   Multipart parts:")
                                    for i, part in enumerate(raw_msg.walk()):
                                        print(f"     Part {i}: {part.get_content_type()}, filename={part.get_filename()}")
            except Exception as e:
                print(f"   Error fetching/inspecting raw email: {e}")
        
        # Ensure we're updating the correct document by preserving original message_id
        # (IMAP might return a slightly different format, but we want to update the MongoDB document)
        if updated_email.get('message_id') != message_id:
            if updated_email.get('message_id'):
                print(f"⚠️  Warning: Message-ID mismatch. Expected: {message_id}, Got: {updated_email.get('message_id')}")
                print(f"   Preserving original message_id for MongoDB update")
            updated_email['message_id'] = message_id
        
        # Update in MongoDB
        result = mongodb_manager.save_emails([updated_email], active_account['id'])
        
        if result.get('success'):
            return {
                "success": True,
                "message": "Email re-fetched and updated in MongoDB",
                "email": updated_email,
                "text_body_length": text_body_len,
                "html_body_length": html_body_len,
                "body_extracted": text_body_len > 0 or html_body_len > 0
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to update email in MongoDB")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error re-fetching email: {str(e)}")


@app.post("/api/gmail/watch")
async def start_gmail_watch():
    """Start Gmail watch (register for push notifications)"""
    try:
        if not config.GMAIL_USE_API:
            raise HTTPException(status_code=400, detail="Gmail API is disabled")
        
        if not config.GMAIL_PUBSUB_TOPIC:
            raise HTTPException(status_code=400, detail="GMAIL_PUBSUB_TOPIC not configured")
        
        active_account = account_manager.get_active_account()
        if not active_account:
            raise HTTPException(status_code=400, detail="No active account")
        
        email_address = active_account['email']
        gmail_client = GmailAPIClient(email_address)
        
        if not gmail_client.authenticate():
            raise HTTPException(status_code=401, detail="Gmail API authentication failed")
        
        response = gmail_client.watch_mailbox(config.GMAIL_PUBSUB_TOPIC)
        
        if response:
            return {
                "success": True,
                "message": "Gmail watch registered",
                "expiration": response.get('expiration'),
                "history_id": response.get('historyId')
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to register watch")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Run server
if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info"
    )

