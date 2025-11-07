"""
FastAPI Server for Email Agent
Provides REST API endpoints for the frontend
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr
from typing import List, Optional, Dict, Any
from datetime import datetime
import uvicorn
import asyncio
import json as json_lib
import os

from email_agent import EmailAgent
from email_receiver import EmailReceiver
from email_sender import EmailSender
from ai_agent import AIAgent
from chat_agent import ChatAgent
from account_manager import AccountManager
from vector_store import vector_store
from mongodb_manager import mongodb_manager
from gmail_api_client import GmailAPIClient
import config

# Initialize account manager with MongoDB (will be set up in startup)
account_manager = None


# Initialize FastAPI app
app = FastAPI(
    title="Email Agent API",
    description="AI-powered email management system",
    version="1.0.0"
)

# Add CORS middleware with optimized settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],  # Next.js default ports
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],  # Explicit methods (reduces preflight)
    allow_headers=["Content-Type", "Authorization", "Accept"],  # Explicit headers (reduces preflight)
    max_age=3600,  # Cache preflight response for 1 hour
)

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


class SemanticSearchRequest(BaseModel):
    query: str
    n_results: int = 10
    filter_metadata: Optional[Dict[str, Any]] = None


# Startup event
@app.on_event("startup")
async def startup_event():
    global email_agent, chat_agent, account_manager
    
    # Initialize account manager with MongoDB
    account_manager = AccountManager(mongodb_manager=mongodb_manager)
    
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
            
            # Ensure it's active
            if not existing_account.get('is_active'):
                account_manager.set_active_account(existing_account['id'])
                print(f"✓ Set existing account as active: {config.EMAIL_ADDRESS}")
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
    
    # Set vector store to active account
    active_account = account_manager.get_active_account()
    if active_account:
        vector_store.set_account(
            account_id=active_account['id'],
            account_email=active_account['email']
        )
    
    # Check if auto-reply is enabled via environment variable
    auto_reply_enabled = os.getenv("AUTO_REPLY_ENABLED", "true").lower() == "true"
    
    email_agent = EmailAgent(
        ai_enabled=True, 
        ai_provider="azure",
        account_manager=account_manager,
        mongodb_manager=mongodb_manager,
        notification_callback=broadcast_notification,
        auto_reply_enabled=auto_reply_enabled
    )
    email_agent.start()
    
    # Start real-time email monitoring (checks every 2 seconds)
    email_agent.start_monitoring(check_interval=2)
    
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
        "version": "1.0.0",
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
        "accounts_count": account_manager.get_account_count()
    }


# Get emails
@app.get("/api/emails")
async def get_emails(
    limit: int = 10,
    unread_only: bool = False,
    folder: str = "INBOX",
    date_from: Optional[str] = None,  # Format: YYYY-MM-DD
    date_to: Optional[str] = None      # Format: YYYY-MM-DD
):
    """Get emails from inbox with optional date range filter"""
    try:
        if not email_agent:
            raise HTTPException(status_code=500, detail="Email agent not initialized")
        
        # Get active account credentials
        active_account = account_manager.get_active_account()
        if not active_account:
            return {
                "success": False,
                "count": 0,
                "emails": [],
                "error": "No active email account. Please add an account first."
            }
        
        # Update receiver with active account credentials
        receiver = email_agent.receiver
        receiver.email_address = active_account['email']
        receiver.password = active_account['password']
        receiver.imap_server = active_account['imap_server']
        receiver.imap_port = active_account['imap_port']
        
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
        
        # Get emails with date filter
        if search_criteria:
            emails = receiver.search_emails(" ".join(search_criteria), folder=folder, limit=limit)
        else:
            emails = receiver.get_emails(folder=folder, limit=limit, unread_only=unread_only)
        
        # Save emails to MongoDB for persistent storage
        mongo_result = {"saved": 0}
        if emails and mongodb_manager.emails_collection is not None:
            mongo_result = mongodb_manager.save_emails(emails, active_account['id'])
            print(f"✓ Saved {mongo_result.get('total', 0)} emails to MongoDB (Inserted: {mongo_result.get('inserted', 0)}, Updated: {mongo_result.get('updated', 0)})")
        
        return {
            "success": True,
            "count": len(emails),
            "emails": emails,
            "account": active_account['email'],
            "mongo_saved": mongo_result.get('total', 0),
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
async def get_unread_emails(limit: int = 10):
    """Get unread emails"""
    return await get_emails(limit=limit, unread_only=True)


# Load emails from MongoDB to Vector DB
@app.post("/api/emails/load-to-vector")
async def load_emails_to_vector(
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
        # Get active account
        active_account = account_manager.get_active_account()
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
            result = vector_store.add_emails(emails)
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
        email_doc = mongodb_manager.emails_collection.find_one({
            "message_id": message_id,
            "account_id": active_account['id']
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
        
        success = sender.reply_to_email(
            original_email=original_email_dict,
            body=reply_body,
            html=False,
            include_original=True
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
            
            return {
                "success": True,
                "message": "Reply sent successfully",
                "to": email_doc.get('from', ''),
                "subject": reply_subject
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to send reply")
    
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
    email_id: str,
    tone: str = "professional"
):
    """Generate an AI response for an email"""
    try:
        if not email_agent or not email_agent.ai_agent:
            raise HTTPException(status_code=400, detail="AI features not enabled")
        
        receiver = email_agent.receiver
        email_data = receiver._fetch_email(email_id.encode())
        
        if not email_data:
            raise HTTPException(status_code=404, detail="Email not found")
        
        ai_agent = email_agent.ai_agent
        response_body = ai_agent.generate_response(email_data, tone=tone)
        
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
async def chat_message(request: ChatRequest):
    """Send a message to the chat agent with vector search enabled"""
    try:
        if not chat_agent:
            raise HTTPException(status_code=500, detail="Chat agent not initialized")
        
        # Use vector search if vector store has emails
        use_vector = vector_store.collection and vector_store.collection.count() > 0
        
        result = chat_agent.chat(request.message, include_context=request.include_context, use_vector_search=use_vector)
        
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
    """Delete an email account"""
    try:
        result = account_manager.remove_account(account_id)
        
        if 'error' in result:
            raise HTTPException(status_code=404, detail=result['error'])
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/accounts/{account_id}/activate")
async def activate_account(account_id: int):
    """Set an account as active"""
    try:
        result = account_manager.set_active_account(account_id)
        
        if 'error' in result:
            raise HTTPException(status_code=404, detail=result['error'])
        
        # Switch vector store to the new account
        active_account = account_manager.get_active_account()
        if active_account:
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
                # Run AI analysis
                analysis = email_agent.ai_agent.analyze_email(email)
                
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
    limit: int = 50,
    skip: int = 0,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    unread_only: bool = False
):
    """
    Get emails from MongoDB storage
    
    Args:
        limit: Number of emails to return (max 200)
        skip: Number of emails to skip (for pagination)
        date_from: Start date filter (YYYY-MM-DD)
        date_to: End date filter (YYYY-MM-DD)
        unread_only: Only return unread emails
    """
    try:
        # Get active account
        active_account = account_manager.get_active_account()
        if not active_account:
            raise HTTPException(status_code=400, detail="No active account")
        
        # Limit max results
        limit = min(limit, 200)
        
        # Get emails from MongoDB with pagination
        # Exclude large HTML/text bodies for list view (much faster loading)
        emails = mongodb_manager.get_emails(
            account_id=active_account['id'],
            limit=limit,
            skip=skip,
            date_from=date_from,
            date_to=date_to,
            unread_only=unread_only,
            exclude_bodies=True  # Exclude html_body and text_body for faster list loading
        )
        
        # Get total count for pagination (optimized - skip expensive count_documents)
        # Use smart estimation based on returned results instead of slow exact count
        try:
            if len(emails) < limit:
                # Got fewer than limit - we're at the end, exact count
                total_count = skip + len(emails)
            else:
                # Got full limit - estimate there might be more
                # Use a simple estimate: skip + limit + some buffer
                total_count = skip + len(emails) + limit  # Estimate
        except Exception as e:
            print(f"Warning: Could not calculate total count: {e}")
            # Fallback: estimate based on returned emails
            total_count = skip + len(emails) + (limit if len(emails) == limit else 0)
        
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


@app.get("/api/mongodb/email/{message_id}")
async def get_single_email(message_id: str):
    """Get a single email with full body content"""
    try:
        active_account = account_manager.get_active_account()
        if not active_account:
            raise HTTPException(status_code=400, detail="No active account")
        
        # Find email by message_id (with full body - exclude_bodies=False)
        email_doc = mongodb_manager.emails_collection.find_one({
            "message_id": message_id,
            "account_id": active_account['id']
        }, {'_id': 0})
        
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
async def toggle_auto_reply(enabled: bool):
    """Toggle auto-reply on or off"""
    try:
        if not email_agent:
            raise HTTPException(status_code=500, detail="Email agent not initialized")
        
        email_agent.auto_reply_enabled = enabled
        status_text = "enabled" if enabled else "disabled"
        print(f"🤖 Auto-reply {status_text}")
        
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
async def notifications():
    """
    Server-Sent Events endpoint for real-time notifications
    Connect to this endpoint to receive push notifications when new emails arrive
    """
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
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

