"""
Email Agent - Main orchestrator for automated email management
"""

import time
from typing import List, Dict, Optional
from datetime import datetime
import json
import threading

from email_receiver import EmailReceiver
from email_sender import EmailSender
from ai_agent import AIAgent
import config


class EmailAgent:
    """Main Email Agent that orchestrates all email operations"""
    
    def __init__(self, ai_enabled: bool = True, ai_provider: str = "azure", 
                 account_manager=None, mongodb_manager=None, notification_callback=None,
                 auto_reply_enabled: bool = False):
        """
        Initialize the Email Agent
        
        Args:
            ai_enabled: Enable AI-powered features
            ai_provider: AI provider to use ("azure", "openai", "anthropic", or "local")
            account_manager: Account manager instance for multi-account support
            mongodb_manager: MongoDB manager instance for persistent storage
            notification_callback: Async callback function for notifications
            auto_reply_enabled: Automatically send AI-suggested replies
        """
        self.receiver = EmailReceiver()
        self.sender = EmailSender()
        self.ai_enabled = ai_enabled
        self.auto_reply_enabled = auto_reply_enabled
        self.account_manager = account_manager
        self.mongodb_manager = mongodb_manager
        self.notification_callback = notification_callback
        
        if ai_enabled:
            self.ai_agent = AIAgent(provider=ai_provider)
        else:
            self.ai_agent = None
        
        self.processed_emails = []
        self.monitoring = False
        self.monitor_thread = None
        self.last_check_time = None
        self.auto_reply_lock = threading.Lock()  # Lock to prevent race conditions
        self.pending_replies = set()  # Track emails we're currently replying to
        print(f"✓ Email Agent initialized (Auto-Reply: {'Enabled' if auto_reply_enabled else 'Disabled'})")
    
    def start(self):
        """Start the email agent"""
        print("\n" + "="*80)
        print("EMAIL AGENT - Starting...")
        print("="*80)
        
        # Skip initial connection if no password (OAuth accounts connect on-demand)
        # This speeds up startup significantly
        if not self.receiver.password or not self.receiver.password.strip():
            print("⚠ Skipping initial IMAP connection (OAuth account or no password configured)")
            print("   Connection will be established on-demand when needed")
        else:
            # Quick connection test with shorter timeout
            try:
                import socket
                original_timeout = socket.getdefaulttimeout()
                socket.setdefaulttimeout(3)  # Reduced from 10 to 3 seconds
                if not self.receiver.connect():
                    print("⚠ Initial connection failed, but agent will retry on requests")
                else:
                    print(f"✓ Initial connection successful to {config.EMAIL_ADDRESS}")
                socket.setdefaulttimeout(original_timeout)
            except Exception as e:
                print(f"⚠ Initial connection skipped: {e}")
        
        print(f"Monitoring: {config.EMAIL_ADDRESS}")
        print(f"AI Features: {'Enabled' if self.ai_enabled else 'Disabled'}")
        print("="*80 + "\n")
    
    def stop(self):
        """Stop the email agent"""
        self.stop_monitoring()
        self.receiver.disconnect()
        print("\n" + "="*80)
        print("EMAIL AGENT - Stopped")
        print("="*80)
    
    def start_monitoring(self, check_interval: int = 30):
        """
        Start real-time email monitoring in background
        
        Args:
            check_interval: Seconds between checks for new emails (default: 30)
        """
        if self.monitoring:
            print("⚠ Monitoring already running")
            return
        
        # Capture the main event loop for thread-safe notifications
        try:
            import asyncio
            try:
                self._main_loop = asyncio.get_running_loop()
            except RuntimeError:
                try:
                    self._main_loop = asyncio.get_event_loop()
                except:
                    self._main_loop = None
        except:
            self._main_loop = None
        
        self.monitoring = True
        self.monitor_thread = threading.Thread(
            target=self._monitoring_loop,
            args=(check_interval,),
            daemon=True
        )
        self.monitor_thread.start()
        print(f"✓ Real-time email monitoring started (check every {check_interval}s)")
    
    def stop_monitoring(self):
        """Stop real-time email monitoring"""
        if self.monitoring:
            self.monitoring = False
            if self.monitor_thread:
                self.monitor_thread.join(timeout=5)
            print("✓ Email monitoring stopped")
    
    def _monitoring_loop(self, check_interval: int):
        """Background loop that checks for new emails for ALL accounts"""
        print("📡 Monitoring loop started...")
        
        # Store Gmail API client for OAuth accounts (per account)
        gmail_clients = {}  # account_id -> GmailAPIClient
        imap_receivers = {}  # account_id -> EmailReceiver (for password accounts)
        
        while self.monitoring:
            try:
                if not self.account_manager:
                    time.sleep(check_interval)
                    continue
                
                # Get active account (for auto-reply only)
                active_account = self.account_manager.get_active_account()
                active_account_id = active_account['id'] if active_account else None
                
                # Get ALL accounts to monitor (with credentials for monitoring)
                all_accounts = self.account_manager.get_all_accounts_with_credentials()
                
                if not all_accounts:
                    time.sleep(check_interval)
                    continue
                
                # Debug: Log accounts being monitored
                if not hasattr(self, '_last_accounts_log') or self._last_accounts_log != len(all_accounts):
                    print(f"📋 Monitoring {len(all_accounts)} account(s): {[acc['email'] for acc in all_accounts]}")
                    self._last_accounts_log = len(all_accounts)
                
                # Monitor each account
                for account in all_accounts:
                    try:
                        account_id = account['id']
                        account_email = account['email']
                        
                        # Debug: Log which account we're checking
                        # (only log occasionally to avoid spam)
                        if not hasattr(self, '_last_check_log') or time.time() - self._last_check_log > 30:
                            print(f"🔍 Checking account {account_id} ({account_email})...")
                            self._last_check_log = time.time()
                        
                        # Check if account has OAuth credentials (SSO account)
                        oauth_credentials = account.get('oauth_credentials')
                        
                        if oauth_credentials:
                            # Use Gmail API for OAuth accounts
                            try:
                                from auth_manager import AuthManager
                                from google.oauth2.credentials import Credentials
                                from googleapiclient.discovery import build
                                from gmail_api_client import GmailAPIClient
                                from google.auth.transport.requests import Request
                                
                                # Get or create Gmail client for this account
                                if account_id not in gmail_clients:
                                    # Convert dict to Credentials object
                                    auth_mgr = AuthManager()  # Uses config values
                                    creds = auth_mgr.dict_to_credentials(oauth_credentials)
                                    
                                    # Refresh if expired
                                    if creds.expired and creds.refresh_token:
                                        try:
                                            creds.refresh(Request())
                                            # Update stored credentials
                                            updated_creds_dict = auth_mgr.credentials_to_dict(creds)
                                            self.account_manager.update_account_oauth_credentials(account_id, updated_creds_dict)
                                        except Exception as refresh_e:
                                            print(f"⚠ Failed to refresh OAuth token for {account_email}: {refresh_e}")
                                            continue
                                    
                                    # Build Gmail service
                                    gmail_service = build('gmail', 'v1', credentials=creds)
                                    
                                    # Create Gmail client
                                    gmail_client = GmailAPIClient(account_email)
                                    gmail_client.service = gmail_service
                                    gmail_client.creds = creds
                                    
                                    # Get profile to initialize history_id
                                    try:
                                        profile = gmail_service.users().getProfile(userId='me').execute()
                                        gmail_client.history_id = profile.get('historyId')
                                    except Exception as profile_e:
                                        print(f"⚠ Failed to get Gmail profile for {account_email}: {profile_e}")
                                        gmail_client.history_id = None
                                    
                                    gmail_clients[account_id] = gmail_client
                                    print(f"✓ Gmail API client initialized for {account_email}")
                                
                                gmail_client = gmail_clients[account_id]
                                
                                # Refresh credentials if expired
                                if gmail_client.creds.expired and gmail_client.creds.refresh_token:
                                    try:
                                        gmail_client.creds.refresh(Request())
                                        # Update stored credentials
                                        auth_mgr = AuthManager()  # Uses config values
                                        updated_creds_dict = auth_mgr.credentials_to_dict(gmail_client.creds)
                                        self.account_manager.update_account_oauth_credentials(account_id, updated_creds_dict)
                                        # Rebuild service with refreshed credentials
                                        gmail_client.service = build('gmail', 'v1', credentials=gmail_client.creds)
                                    except Exception as refresh_e:
                                        print(f"⚠ Failed to refresh OAuth token for {account_email}: {refresh_e}")
                                
                                # Get new emails using Gmail API
                                if gmail_client.history_id:
                                    new_emails = gmail_client.get_new_emails(limit=10)
                                    print(f"🔍 Gmail API (history): Found {len(new_emails) if new_emails else 0} emails for {account_email}")
                                else:
                                    # Fallback: get recent emails if history_id not available
                                    new_emails = gmail_client.get_emails(limit=10, query='in:inbox is:unread')
                                    print(f"🔍 Gmail API (fallback): Found {len(new_emails) if new_emails else 0} emails for {account_email}")
                                
                                # Filter to only new emails (check against MongoDB)
                                if new_emails and self.mongodb_manager:
                                    existing_message_ids = set()
                                    message_ids = [e.get('message_id') for e in new_emails if e.get('message_id')]
                                    if message_ids:
                                        existing_docs = self.mongodb_manager.emails_collection.find(
                                            {
                                                "message_id": {"$in": message_ids},
                                                "account_id": account_id
                                            },
                                            {"message_id": 1}
                                        )
                                        existing_message_ids = {doc.get('message_id') for doc in existing_docs}
                                    
                                    new_emails = [e for e in new_emails if e.get('message_id') not in existing_message_ids]
                                
                                # Process new emails (send notifications for all, auto-reply for all accounts)
                                if new_emails:
                                    is_active_account = (account_id == active_account_id)
                                    self._process_new_emails(new_emails, account_id, check_interval, should_auto_reply=True)  # All accounts should auto-reply
                                
                            except Exception as e:
                                print(f"⚠ Gmail API monitoring error for {account_email}: {e}")
                                import traceback
                                traceback.print_exc()
                                continue
                        else:
                            # Use IMAP for password-based accounts
                            password = account.get('password')
                            if not password:
                                continue  # Skip accounts without credentials
                            
                            # Get or create IMAP receiver for this account
                            if account_id not in imap_receivers:
                                from email_receiver import EmailReceiver
                                receiver = EmailReceiver()
                                receiver.email_address = account_email
                                receiver.password = password
                                receiver.imap_server = account.get('imap_server', 'imap.gmail.com')
                                receiver.imap_port = account.get('imap_port', 993)
                                imap_receivers[account_id] = receiver
                            
                            receiver = imap_receivers[account_id]
                            
                            # Ensure connection
                            if not receiver.mail:
                                if not receiver.connect():
                                    print(f"⚠ Failed to connect to {account_email}")
                                    continue
                            
                            # Check for new emails using IMAP
                            try:
                                new_emails = receiver.get_emails(folder='INBOX', limit=10, unread_only=False)
                                
                                # Filter to only new emails (check against MongoDB)
                                if new_emails and self.mongodb_manager:
                                    existing_message_ids = set()
                                    message_ids = [e.get('message_id') for e in new_emails if e.get('message_id')]
                                    if message_ids:
                                        existing_docs = self.mongodb_manager.emails_collection.find(
                                            {
                                                "message_id": {"$in": message_ids},
                                                "account_id": account_id
                                            },
                                            {"message_id": 1}
                                        )
                                        existing_message_ids = {doc.get('message_id') for doc in existing_docs}
                                    
                                    new_emails = [e for e in new_emails if e.get('message_id') not in existing_message_ids]
                                
                                # Process new emails (send notifications for all, auto-reply for all accounts)
                                if new_emails:
                                    is_active_account = (account_id == active_account_id)
                                    self._process_new_emails(new_emails, account_id, check_interval, should_auto_reply=True)  # All accounts should auto-reply
                            except Exception as e:
                                print(f"⚠ IMAP monitoring error for {account_email}: {e}")
                                continue
                    
                    except Exception as e:
                        print(f"⚠ Error monitoring account {account.get('email', 'unknown')}: {e}")
                        continue
                
                # Wait before next check
                time.sleep(check_interval)
                
            except Exception as e:
                print(f"⚠ Monitoring error: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(check_interval)
        
        print("📡 Monitoring loop stopped")
    
    def _process_new_emails(self, new_emails: List[Dict], account_id: Optional[int], check_interval: int, should_auto_reply: bool = True):
        """Process new emails (save, analyze, notify)
        
        Args:
            new_emails: List of new email dictionaries
            account_id: Account ID that received these emails
            check_interval: Monitoring check interval (unused, kept for compatibility)
            should_auto_reply: Whether to send auto-replies (only True for active account)
        """
        if not new_emails:
            return
        
        print(f"📨 Found {len(new_emails)} new email(s) for account {account_id}!")
        
        # Save to MongoDB if available
        if self.mongodb_manager and self.mongodb_manager.emails_collection is not None and account_id:
            result = self.mongodb_manager.save_emails(new_emails, account_id)
            if result.get('success'):
                print(f"💾 Saved {result.get('total', 0)} new emails to MongoDB")
        
        # Run AI analysis if enabled (asynchronously to not block monitoring)
        if self.ai_enabled and self.ai_agent:
            # Process AI analysis in background thread to not block monitoring loop
            import threading
            def analyze_emails_async():
                for email in new_emails:
                    try:
                        print(f"🤖 Analyzing email: {email.get('subject', 'No subject')[:50]}")
                        analysis = self.ai_agent.analyze_email(email)
                        email['ai_analysis'] = analysis
                        
                        # Save AI analysis to separate collection in MongoDB
                        if self.mongodb_manager and self.mongodb_manager.ai_analysis_collection is not None:
                            email_message_id = email.get('message_id')
                            if email_message_id:
                                analysis_result = self.mongodb_manager.save_ai_analysis(
                                    email_message_id, 
                                    account_id, 
                                    analysis
                                )
                                if analysis_result.get('success'):
                                    print(f"🧠 AI analysis saved for: {email.get('subject', 'No subject')[:40]}")
                        
                        # Auto-reply if enabled and appropriate (all accounts)
                        if should_auto_reply and self.auto_reply_enabled and self._should_auto_reply(email, analysis, account_id):
                            try:
                                self._send_auto_reply(email, analysis, account_id)
                            except Exception as e:
                                print(f"⚠ Auto-reply failed: {e}")
                        
                    except Exception as e:
                        print(f"⚠ AI analysis failed: {e}")
            
            # Start analysis in background thread (non-blocking)
            analysis_thread = threading.Thread(target=analyze_emails_async, daemon=True)
            analysis_thread.start()
            print(f"🚀 Started AI analysis in background for {len(new_emails)} email(s)")
        
        # Send notification to UI (with account_id - frontend will filter)
        # Send notifications for ALL accounts - frontend filters by logged-in user's account
        if self.notification_callback:
            try:
                import asyncio
                import concurrent.futures
                
                for email in new_emails:
                    notification = {
                        "type": "new_email",
                        "account_id": account_id,  # Frontend will filter based on logged-in user's account
                        "email": {
                            "subject": email.get('subject', 'No Subject'),
                            "from": email.get('from', 'Unknown'),
                            "date": email.get('date', ''),
                            "category": email.get('ai_analysis', {}).get('category', 'other') if email.get('ai_analysis') else 'other',
                            "is_spam": email.get('ai_analysis', {}).get('is_spam', False) if email.get('ai_analysis') else False,
                            "urgency_score": email.get('ai_analysis', {}).get('urgency_score', 0) if email.get('ai_analysis') else 0
                        },
                        "timestamp": datetime.now().isoformat(),
                        "count": len(new_emails)
                    }
                    
                    # Schedule the coroutine in a thread-safe way
                    try:
                        loop = asyncio.get_event_loop()
                        if loop and loop.is_running():
                            # Schedule coroutine in the existing event loop
                            asyncio.run_coroutine_threadsafe(
                                self.notification_callback(notification), 
                                loop
                            )
                            print(f"📬 Notification sent for account {account_id}: {email.get('subject', 'No Subject')[:40]}")
                        else:
                            # Fallback: try asyncio.run
                            asyncio.run(self.notification_callback(notification))
                            print(f"📬 Notification sent (fallback) for account {account_id}: {email.get('subject', 'No Subject')[:40]}")
                    except RuntimeError:
                        # No event loop in current thread, try to get the main loop
                        try:
                            import threading
                            # Store the main event loop when starting monitoring
                            if hasattr(self, '_main_loop') and self._main_loop:
                                asyncio.run_coroutine_threadsafe(
                                    self.notification_callback(notification),
                                    self._main_loop
                                )
                                print(f"📬 Notification sent (main loop) for account {account_id}: {email.get('subject', 'No Subject')[:40]}")
                        except Exception as e2:
                            print(f"⚠ Failed to send notification (inner): {e2}")
                            
            except Exception as e:
                print(f"⚠ Failed to send notification: {e}")
        
        # Update last check time
        self.last_check_time = datetime.now()
    
    def _check_new_emails(self) -> List[Dict]:
        """
        Check for new emails since last check
        
        Returns:
            List of new emails
        """
        try:
            # Ensure connection
            if not self.receiver.mail:
                self.receiver.connect()
            
            # Get recent emails (last 3 to check for new ones)
            emails = self.receiver.get_emails(folder='INBOX', limit=3, unread_only=False)
            
            if not emails:
                return []
            
            # If first check, just store the latest email ID
            if self.last_check_time is None:
                self.last_check_time = datetime.now()
                return []  # Don't process on first check
            
            # Filter emails - check both in-memory cache AND MongoDB to prevent duplicates
            new_emails = []
            
            # Get all message IDs first
            message_ids = [email.get('message_id') for email in emails if email.get('message_id')]
            
            # Batch check MongoDB for existing emails (much faster than individual queries)
            existing_message_ids = set()
            if self.mongodb_manager and self.mongodb_manager.emails_collection is not None:
                if self.account_manager:
                    active_account = self.account_manager.get_active_account()
                    if active_account and message_ids:
                        # Single query to get all existing message IDs
                        existing_docs = self.mongodb_manager.emails_collection.find(
                            {
                                "message_id": {"$in": message_ids},
                                "account_id": active_account['id']
                            },
                            {"message_id": 1}  # Only fetch message_id field for speed
                        )
                        existing_message_ids = {doc.get('message_id') for doc in existing_docs}
            
            # Get in-memory cache message IDs
            processed_message_ids = {e.get('message_id') for e in self.processed_emails[-20:] if e.get('message_id')}
            
            # Filter emails
            for email in emails:
                try:
                    message_id = email.get('message_id')
                    if not message_id:
                        continue
                    
                    # Check 1: In-memory cache
                    if message_id in processed_message_ids:
                        continue
                    
                    # Check 2: MongoDB (batch check)
                    if message_id in existing_message_ids:
                        continue
                    
                    # Email is new - add it
                    new_emails.append(email)
                except Exception as e:
                    print(f"⚠️  Error checking email duplicate: {e}")
                    continue
            
            # Keep track of processed emails (limit to last 20)
            self.processed_emails.extend(new_emails)
            if len(self.processed_emails) > 20:
                self.processed_emails = self.processed_emails[-20:]
            
            return new_emails
            
        except Exception as e:
            print(f"Error checking new emails: {e}")
            return []
    
    def process_inbox(self, limit: int = None, unread_only: bool = False):
        """
        Process emails in inbox
        
        Args:
            limit: Maximum number of emails to process
            unread_only: Only process unread emails
        """
        limit = limit or config.MAX_EMAILS_TO_PROCESS
        
        print(f"\n📥 Fetching {'unread' if unread_only else 'recent'} emails (limit: {limit})...")
        emails = self.receiver.get_emails(
            folder=config.DEFAULT_MAILBOX,
            limit=limit,
            unread_only=unread_only
        )
        
        if not emails:
            print("No emails to process.")
            return
        
        print(f"Found {len(emails)} emails to process\n")
        
        for idx, email_data in enumerate(emails, 1):
            print(f"\n{'─'*80}")
            print(f"Processing Email {idx}/{len(emails)}")
            print(f"{'─'*80}")
            self._process_single_email(email_data)
        
        print(f"\n✓ Processed {len(emails)} emails")
    
    def _process_single_email(self, email_data: Dict):
        """Process a single email with AI analysis"""
        # Display basic info
        print(f"From: {email_data['from']}")
        print(f"Subject: {email_data['subject']}")
        print(f"Date: {email_data['date']}")
        
        if email_data.get('has_attachments'):
            print(f"Attachments: {len(email_data.get('attachments', []))}")
        
        # AI Analysis
        if self.ai_agent:
            print("\n🤖 AI Analysis:")
            
            # Categorize
            category = self.ai_agent.categorize_email(email_data)
            print(f"  Category: {category.upper()}")
            
            # Check urgency
            urgency_score, urgency_reason = self.ai_agent.detect_urgency(email_data)
            if urgency_score > 6:
                print(f"  ⚠️  Urgency: {urgency_score}/10 - {urgency_reason}")
            
            # Check spam
            is_spam, spam_confidence = self.ai_agent.is_spam(email_data)
            if is_spam:
                print(f"  🚫 Likely SPAM (confidence: {spam_confidence:.0%})")
            
            # Summarize
            if email_data.get('text_body'):
                summary = self.ai_agent.summarize_email(email_data)
                print(f"\n  Summary: {summary}")
            
            # Extract action items
            action_items = self.ai_agent.extract_action_items(email_data)
            if action_items:
                print(f"\n  Action Items:")
                for action in action_items[:3]:
                    print(f"    • {action}")
            
            # Store analysis
            email_data['ai_analysis'] = {
                'category': category,
                'urgency_score': urgency_score,
                'is_spam': is_spam,
                'summary': summary if email_data.get('text_body') else None
            }
        
        # Store processed email
        self.processed_emails.append(email_data)
    
    def auto_respond_to_emails(self, emails: Optional[List[Dict]] = None, 
                               tone: str = "professional"):
        """
        Automatically respond to emails using AI
        
        Args:
            emails: List of emails to respond to (None = use processed emails)
            tone: Response tone (professional, friendly, formal, casual)
        """
        if not self.ai_agent:
            print("⚠️  AI features are disabled. Cannot generate responses.")
            return
        
        emails = emails or self.processed_emails
        
        if not emails:
            print("No emails to respond to.")
            return
        
        print(f"\n📨 Generating AI responses for {len(emails)} emails...")
        
        for idx, email_data in enumerate(emails, 1):
            # Skip spam
            if email_data.get('ai_analysis', {}).get('is_spam'):
                print(f"\n{idx}. Skipping spam email: {email_data['subject']}")
                continue
            
            print(f"\n{idx}. Generating response to: {email_data['subject']}")
            
            # Check if AI agent has a client
            if not self.ai_agent.client:
                print(f"⚠️  WARNING: AI agent has no client - will use template response")
                print(f"   AI Provider: {self.ai_agent.provider}")
                print(f"   This indicates AI configuration is missing or failed")
            
            # Generate response
            response_body = self.ai_agent.generate_response(email_data, tone=tone)
            
            print("\n" + "─"*60)
            print("Generated Response:")
            print("─"*60)
            print(response_body)
            print("─"*60)
            
            if config.DRAFT_MODE:
                print("✓ Response saved as draft (DRAFT_MODE=True)")
            else:
                # Send response
                if config.AUTO_RESPOND:
                    success = self.sender.reply_to_email(
                        original_email=email_data,
                        body=response_body
                    )
                    if success:
                        print("✓ Response sent")
                else:
                    print("⚠️  Auto-respond disabled (set AUTO_RESPOND=True in config)")
    
    def search_emails_by_sender(self, sender_email: str) -> List[Dict]:
        """Search for emails from a specific sender"""
        print(f"\n🔍 Searching emails from: {sender_email}")
        emails = self.receiver.search_emails(f'FROM "{sender_email}"')
        print(f"Found {len(emails)} emails")
        return emails
    
    def search_emails_by_subject(self, subject_keyword: str) -> List[Dict]:
        """Search for emails with subject containing keyword"""
        print(f"\n🔍 Searching emails with subject: {subject_keyword}")
        emails = self.receiver.search_emails(f'SUBJECT "{subject_keyword}"')
        print(f"Found {len(emails)} emails")
        return emails
    
    def get_email_statistics(self) -> Dict:
        """Get statistics about processed emails"""
        if not self.processed_emails:
            return {}
        
        stats = {
            'total_emails': len(self.processed_emails),
            'with_attachments': sum(1 for e in self.processed_emails if e.get('has_attachments')),
            'categories': {},
            'average_urgency': 0,
            'spam_count': 0
        }
        
        if self.ai_agent:
            urgency_scores = []
            for email in self.processed_emails:
                analysis = email.get('ai_analysis', {})
                
                # Count categories
                category = analysis.get('category', 'other')
                stats['categories'][category] = stats['categories'].get(category, 0) + 1
                
                # Urgency
                urgency_score = analysis.get('urgency_score', 0)
                urgency_scores.append(urgency_score)
                
                # Spam
                if analysis.get('is_spam'):
                    stats['spam_count'] += 1
            
            if urgency_scores:
                stats['average_urgency'] = sum(urgency_scores) / len(urgency_scores)
        
        return stats
    
    def print_statistics(self):
        """Print email statistics"""
        stats = self.get_email_statistics()
        
        if not stats:
            print("No statistics available. Process emails first.")
            return
        
        print("\n" + "="*80)
        print("EMAIL STATISTICS")
        print("="*80)
        print(f"Total Emails Processed: {stats['total_emails']}")
        print(f"Emails with Attachments: {stats['with_attachments']}")
        
        if self.ai_agent:
            print(f"\nAverage Urgency Score: {stats['average_urgency']:.1f}/10")
            print(f"Spam Detected: {stats['spam_count']}")
            
            if stats['categories']:
                print("\nCategories:")
                for category, count in sorted(stats['categories'].items(), 
                                             key=lambda x: x[1], reverse=True):
                    print(f"  {category.upper()}: {count}")
        
        print("="*80)
    
    def export_emails(self, filename: str = "emails_export.json"):
        """Export processed emails to JSON file"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.processed_emails, f, indent=2, ensure_ascii=False)
            print(f"✓ Exported {len(self.processed_emails)} emails to {filename}")
        except Exception as e:
            print(f"✗ Export failed: {e}")
    
    def send_email(self, to: str, subject: str, body: str, **kwargs):
        """Send an email"""
        return self.sender.send_email(to=to, subject=subject, body=body, **kwargs)
    
    def _should_auto_reply(self, email: Dict, analysis: Dict, account_id: Optional[int]) -> bool:
        """
        Determine if we should automatically reply to this email
        
        Args:
            email: Email data
            analysis: AI analysis results
            account_id: Account ID that received the email
            
        Returns:
            bool: True if we should auto-reply, False otherwise
        """
        # Use lock to prevent race conditions when multiple threads check the same email
        with self.auto_reply_lock:
            message_id = email.get('message_id')
            if not message_id:
                return False
            
            # Create unique key for this email
            reply_key = f"{account_id}:{message_id}" if account_id else message_id
            
            # Check if we're already processing a reply for this email
            if reply_key in self.pending_replies:
                print(f"⏭️  Skipping auto-reply: Reply already in progress for this email")
                return False
            
            # Safety checks - DO NOT reply if:
            
            # 1. Email is spam
            if analysis.get('is_spam', False):
                print(f"⏭️  Skipping auto-reply: Email is spam")
                return False
            
            # 2. Email is from the same account (prevent self-reply loops)
            from_email = email.get('from', '').lower()
            if self.account_manager and account_id:
                # Get the account that received the email
                all_accounts = self.account_manager.get_all_accounts_with_credentials()
                receiving_account = next((acc for acc in all_accounts if acc.get('id') == account_id), None)
                
                if receiving_account:
                    account_email = receiving_account.get('email', '').lower()
                    
                    # Extract email address from "Name <email@domain.com>" format
                    import re
                    email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', from_email)
                    if email_match:
                        from_email_clean = email_match.group(0).lower()
                    else:
                        from_email_clean = from_email
                    
                    if from_email_clean == account_email:
                        print(f"⏭️  Skipping auto-reply: Email is from same account ({account_email}) - preventing loop")
                        return False
            
            # 3. Email is a newsletter (category)
            category = analysis.get('category', '').lower()
            if category in ['newsletter', 'marketing', 'promotional', 'social']:
                print(f"⏭️  Skipping auto-reply: Email is {category}")
                return False
            
            # 4. No suggested response available (main check)
            suggested_response = analysis.get('suggested_response', '').strip()
            if not suggested_response or len(suggested_response) < 10:
                print(f"⏭️  Skipping auto-reply: No AI-generated response available")
                return False
            
            # 5. Email is from a "noreply" address
            if 'noreply' in from_email or 'no-reply' in from_email:
                print(f"⏭️  Skipping auto-reply: From noreply address")
                return False
            
            # 6. Check MongoDB - Have we already replied to this email?
            if self.mongodb_manager and self.mongodb_manager.replies_collection is not None:
                if message_id and account_id:
                    # Check for existing reply using both message_id formats (actual and synthetic)
                    existing_reply = self.mongodb_manager.get_reply(message_id, account_id)
                    
                    # Also check with alternate message_id format if not found
                    if not existing_reply:
                        # Try to find the email document to get alternate message_id format
                        try:
                            if self.mongodb_manager and self.mongodb_manager.emails_collection is not None:
                                email_doc = self.mongodb_manager.emails_collection.find_one({
                                    "$or": [
                                        {"message_id": message_id, "account_id": account_id},
                                        {"gmail_synthetic_id": message_id, "account_id": account_id}
                                    ]
                                }, {'gmail_synthetic_id': 1, 'message_id': 1})
                                
                                if email_doc:
                                    # Try both message_id formats
                                    synthetic_id = email_doc.get('gmail_synthetic_id')
                                    actual_id = email_doc.get('message_id')
                                    
                                    # Check with actual Message-ID if current message_id is synthetic
                                    if synthetic_id and message_id == synthetic_id and actual_id:
                                        existing_reply = self.mongodb_manager.get_reply(actual_id, account_id)
                                    # Check with synthetic ID if current message_id is actual
                                    elif actual_id and message_id == actual_id and synthetic_id:
                                        existing_reply = self.mongodb_manager.get_reply(synthetic_id, account_id)
                        except Exception as e:
                            print(f"⚠️  Error checking alternate message_id format: {e}")
                    
                    if existing_reply:
                        sent_at = existing_reply.get('sent_at', 'unknown time')
                        print(f"⏭️  Skipping auto-reply: Already replied on {sent_at}")
                        return False
            
            # Mark as pending BEFORE returning True to prevent race conditions
            self.pending_replies.add(reply_key)
            
            # All checks passed - auto-reply is appropriate
            print(f"✅ Auto-reply approved for: {email.get('subject', 'No subject')[:40]}")
            return True
    
    def _send_auto_reply(self, email: Dict, analysis: Dict, account_id: Optional[int]):
        """
        Send an automatic reply based on AI analysis
        
        Args:
            email: Email data
            analysis: AI analysis results
            account_id: Account ID that received the email (will send reply from this account)
        """
        message_id = email.get('message_id')
        reply_key = f"{account_id}:{message_id}" if (message_id and account_id) else None
        
        try:
            from_address = email.get('from', '')
            subject = email.get('subject', 'No Subject')
            suggested_response = analysis.get('suggested_response', '')
            
            if not from_address or not suggested_response:
                print("⚠️  Missing from_address or suggested_response")
                return
            
            # Get the account that received the email (not the active account)
            reply_account = None
            if self.account_manager and account_id:
                # Get account by ID with credentials
                all_accounts = self.account_manager.get_all_accounts_with_credentials()
                reply_account = next((acc for acc in all_accounts if acc.get('id') == account_id), None)
            
            # Fallback to active account if account_id not found
            if not reply_account and self.account_manager:
                reply_account = self.account_manager.get_active_account()
            
            if not reply_account:
                print("⚠️  No account found to send auto-reply")
                return
            
            # Update sender with the account that received the email
            self.sender.email_address = reply_account['email']
            self.sender.password = reply_account.get('password', '')
            self.sender.smtp_server = reply_account.get('smtp_server', 'smtp.gmail.com')
            self.sender.smtp_port = reply_account.get('smtp_port', 587)
            
            # If OAuth credentials are available, use them for Gmail API
            oauth_creds = reply_account.get('oauth_credentials')
            if oauth_creds:
                self.sender.set_oauth_credentials(oauth_creds)
            else:
                # Clear OAuth credentials if not available
                self.sender.oauth_credentials = None
                self.sender.gmail_service = None
            
            # Compose reply
            reply_subject = f"Re: {subject}" if not subject.lower().startswith('re:') else subject
            
            # Get thread_id from MongoDB if available (for Gmail API threading)
            thread_id = None
            if self.mongodb_manager and self.mongodb_manager.emails_collection is not None and message_id:
                try:
                    # Handle both actual Message-ID and synthetic Gmail ID formats
                    email_doc = self.mongodb_manager.emails_collection.find_one({
                        "$or": [
                            {"message_id": message_id, "account_id": account_id},
                            {"gmail_synthetic_id": message_id, "account_id": account_id}
                        ]
                    }, {'thread_id': 1, 'gmail_id': 1, 'message_id': 1})
                    if email_doc:
                        thread_id = email_doc.get('thread_id', '') or None
                        gmail_id = email_doc.get('gmail_id', '')
                        
                        # If thread_id not in MongoDB but we have gmail_id and OAuth, try to get it
                        if not thread_id and gmail_id and self.sender.gmail_service:
                            try:
                                msg = self.sender.gmail_service.users().messages().get(
                                    userId='me',
                                    id=gmail_id,
                                    format='metadata'
                                ).execute()
                                thread_id = msg.get('threadId', '') or None
                                if thread_id:
                                    # Update MongoDB with thread_id for future use
                                    self.mongodb_manager.emails_collection.update_one(
                                        {"message_id": message_id, "account_id": account_id},
                                        {"$set": {"thread_id": thread_id}}
                                    )
                                    print(f"📎 Retrieved threadId from Gmail API for auto-reply: {thread_id}")
                            except Exception as e:
                                print(f"⚠️  Could not retrieve threadId for auto-reply: {e}")
                except Exception as e:
                    print(f"⚠️  Could not get thread_id from MongoDB: {e}")
            
            # Normalize message_id format for headers
            normalized_message_id = None
            if message_id:
                clean_msg_id = message_id.strip('<>').strip()
                if clean_msg_id:
                    normalized_message_id = f"<{clean_msg_id}>" if not clean_msg_id.startswith('<') else clean_msg_id
            
            # Send the reply with threading headers and threadId (for Gmail API)
            print(f"📤 Sending auto-reply to: {from_address}")
            print(f"   From account: {self.sender.email_address}")
            print(f"   Threading: message_id={normalized_message_id}, thread_id={thread_id if thread_id else 'N/A'}")
            success = self.sender.send_email(
                to=from_address,
                subject=reply_subject,
                body=suggested_response,
                html=False,
                in_reply_to=normalized_message_id if normalized_message_id else None,  # Threading header
                references=normalized_message_id if normalized_message_id else None,   # Threading header
                thread_id=thread_id  # Gmail API threadId for proper threading
            )
            
            if success:
                print(f"✅ Auto-reply sent to {from_address}: '{subject[:40]}'")
                
                # Save reply to MongoDB IMMEDIATELY to prevent duplicates
                if self.mongodb_manager and self.mongodb_manager.replies_collection is not None:
                    if message_id and account_id:
                        reply_data = {
                            'to': from_address,
                            'subject': reply_subject,
                            'body': suggested_response,
                            'success': True,
                            'sent_at': datetime.now().isoformat()
                        }
                        result = self.mongodb_manager.save_reply(
                            message_id,
                            account_id,
                            reply_data
                        )
                        if result.get('success'):
                            print(f"💾 Auto-reply saved to MongoDB")
            else:
                print(f"❌ Failed to send auto-reply to {from_address}")
        finally:
            # Always remove from pending set, even if sending failed
            if reply_key:
                with self.auto_reply_lock:
                    self.pending_replies.discard(reply_key)
    
    def interactive_mode(self):
        """Run agent in interactive mode"""
        print("\n" + "="*80)
        print("EMAIL AGENT - INTERACTIVE MODE")
        print("="*80)
        print("\nCommands:")
        print("  1. Process inbox")
        print("  2. Process unread emails only")
        print("  3. Search by sender")
        print("  4. Search by subject")
        print("  5. Generate AI responses")
        print("  6. Send new email")
        print("  7. Show statistics")
        print("  8. Export emails")
        print("  9. Exit")
        print("="*80)
        
        while True:
            try:
                choice = input("\nEnter command (1-9): ").strip()
                
                if choice == '1':
                    limit = input("Number of emails to process (default 10): ").strip()
                    limit = int(limit) if limit.isdigit() else 10
                    self.process_inbox(limit=limit, unread_only=False)
                
                elif choice == '2':
                    limit = input("Number of emails to process (default 10): ").strip()
                    limit = int(limit) if limit.isdigit() else 10
                    self.process_inbox(limit=limit, unread_only=True)
                
                elif choice == '3':
                    sender = input("Enter sender email: ").strip()
                    emails = self.search_emails_by_sender(sender)
                    self.processed_emails.extend(emails)
                
                elif choice == '4':
                    subject = input("Enter subject keyword: ").strip()
                    emails = self.search_emails_by_subject(subject)
                    self.processed_emails.extend(emails)
                
                elif choice == '5':
                    tone = input("Response tone (professional/friendly/formal/casual): ").strip()
                    tone = tone if tone else "professional"
                    self.auto_respond_to_emails(tone=tone)
                
                elif choice == '6':
                    to = input("To: ").strip()
                    subject = input("Subject: ").strip()
                    print("Body (press Enter twice to finish):")
                    lines = []
                    while True:
                        line = input()
                        if line == "" and (not lines or lines[-1] == ""):
                            break
                        lines.append(line)
                    body = "\n".join(lines[:-1] if lines and lines[-1] == "" else lines)
                    self.send_email(to, subject, body)
                
                elif choice == '7':
                    self.print_statistics()
                
                elif choice == '8':
                    filename = input("Export filename (default: emails_export.json): ").strip()
                    filename = filename if filename else "emails_export.json"
                    self.export_emails(filename)
                
                elif choice == '9':
                    print("\nExiting...")
                    break
                
                else:
                    print("Invalid choice. Please enter 1-9.")
            
            except KeyboardInterrupt:
                print("\n\nExiting...")
                break
            except Exception as e:
                print(f"Error: {e}")


def main():
    """Main entry point"""
    # Initialize agent with AI features (Azure OpenAI)
    agent = EmailAgent(ai_enabled=True, ai_provider="azure")
    
    try:
        # Start the agent
        agent.start()
        
        # Run in interactive mode
        agent.interactive_mode()
        
    finally:
        # Stop the agent
        agent.stop()


if __name__ == "__main__":
    main()

