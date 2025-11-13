"""
Gmail API Client - Real-time email fetching using Gmail API
Supports OAuth 2.0 and history-based change detection
"""

import os
import pickle
import base64
import email
import re
import html
from typing import List, Dict, Optional
from datetime import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


class GmailAPIClient:
    """Gmail API client for fetching emails using OAuth 2.0"""
    
    # Gmail API scopes
    SCOPES = [
        'https://www.googleapis.com/auth/gmail.readonly',
        'https://www.googleapis.com/auth/gmail.modify'
    ]
    
    def __init__(self, email_address: str, credentials_path: str = None, token_path: str = None):
        """
        Initialize Gmail API client
        
        Args:
            email_address: Email address to monitor
            credentials_path: Path to OAuth credentials JSON file
            token_path: Path to store/load OAuth token
        """
        self.email_address = email_address
        self.credentials_path = credentials_path or os.getenv('GMAIL_CREDENTIALS_PATH', 'credentials.json')
        self.token_path = token_path or os.getenv('GMAIL_TOKEN_PATH', f'token_{email_address.replace("@", "_").replace(".", "_")}.pickle')
        self.service = None
        self.history_id = None
        self.creds = None
        
    def authenticate(self) -> bool:
        """
        Authenticate with Gmail API using OAuth 2.0
        
        Returns:
            True if authentication successful
        """
        try:
            # Load existing token
            if os.path.exists(self.token_path):
                with open(self.token_path, 'rb') as token:
                    self.creds = pickle.load(token)
            
            # If no valid credentials, get new ones
            if not self.creds or not self.creds.valid:
                if self.creds and self.creds.expired and self.creds.refresh_token:
                    self.creds.refresh(Request())
                else:
                    # Create credentials from environment variables if credentials.json doesn't exist
                    if not os.path.exists(self.credentials_path):
                        # Use environment variables for OAuth credentials
                        client_id = os.getenv('GMAIL_CLIENT_ID')
                        client_secret = os.getenv('GMAIL_CLIENT_SECRET')
                        
                        if client_id and client_secret:
                            # Import config to get redirect URI
                            import config as app_config
                            redirect_uri = app_config.GOOGLE_REDIRECT_URI or "http://localhost:8000/api/auth/callback"
                            
                            # Create credentials dict
                            credentials_info = {
                                "installed": {
                                    "client_id": client_id,
                                    "client_secret": client_secret,
                                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                                    "token_uri": "https://oauth2.googleapis.com/token",
                                    "redirect_uris": [redirect_uri]
                                }
                            }
                            
                            # Save to temporary file
                            import json
                            temp_creds_path = 'temp_credentials.json'
                            with open(temp_creds_path, 'w') as f:
                                json.dump(credentials_info, f)
                            
                            flow = InstalledAppFlow.from_client_secrets_file(
                                temp_creds_path, self.SCOPES)
                            self.creds = flow.run_local_server(port=0)
                            
                            # Clean up temp file
                            os.remove(temp_creds_path)
                        else:
                            print("❌ Gmail API credentials not found. Please set GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET in .env")
                            return False
                    else:
                        flow = InstalledAppFlow.from_client_secrets_file(
                            self.credentials_path, self.SCOPES)
                        self.creds = flow.run_local_server(port=0)
                
                # Save credentials for next run
                with open(self.token_path, 'wb') as token:
                    pickle.dump(self.creds, token)
            
            # Build Gmail service
            self.service = build('gmail', 'v1', credentials=self.creds)
            
            # Get initial history ID
            profile = self.service.users().getProfile(userId='me').execute()
            self.history_id = profile.get('historyId')
            
            print(f"✓ Gmail API authenticated: {self.email_address}")
            print(f"  History ID: {self.history_id}")
            return True
            
        except Exception as e:
            print(f"❌ Gmail API authentication failed: {e}")
            return False
    
    def get_profile(self) -> Optional[Dict]:
        """Get Gmail profile information"""
        if not self.service:
            return None
        
        try:
            profile = self.service.users().getProfile(userId='me').execute()
            return profile
        except Exception as e:
            print(f"Error getting profile: {e}")
            return None
    
    def get_new_emails(self, limit: int = 10) -> List[Dict]:
        """
        Get new emails using history API (change detection)
        
        Args:
            limit: Maximum number of emails to return
            
        Returns:
            List of email dictionaries
        """
        if not self.service or not self.history_id:
            return []
        
        try:
            # Get history of changes since last check
            history = self.service.users().history().list(
                userId='me',
                startHistoryId=self.history_id,
                maxResults=limit * 2  # Get more to account for deletions
            ).execute()
            
            if not history.get('history'):
                return []
            
            # Extract message IDs from history
            message_ids = set()
            for record in history['history']:
                if 'messagesAdded' in record:
                    for msg in record['messagesAdded']:
                        message_ids.add(msg['message']['id'])
            
            # Update history ID
            if history.get('historyId'):
                self.history_id = history['historyId']
            
            if not message_ids:
                return []
            
            # Fetch full message details
            emails = []
            for msg_id in list(message_ids)[:limit]:
                email_data = self._fetch_message(msg_id)
                if email_data:
                    emails.append(email_data)
            
            return emails
            
        except HttpError as e:
            if e.resp.status == 404:
                # History ID expired, need to get new one
                profile = self.get_profile()
                if profile:
                    self.history_id = profile.get('historyId')
                print("⚠️  History ID expired, reset to current")
            else:
                print(f"Error fetching new emails: {e}")
            return []
        except Exception as e:
            print(f"Error getting new emails: {e}")
            return []
    
    def get_emails(self, limit: int = 10, query: str = None, skip: int = 0) -> List[Dict]:
        """
        Get emails from Gmail with pagination support
        
        Args:
            limit: Maximum number of emails to return
            query: Gmail search query (e.g., "in:inbox")
            skip: Number of emails to skip (for pagination)
            
        Returns:
            List of email dictionaries
        """
        if not self.service:
            return []
        
        try:
            # Build query
            search_query = query or 'in:inbox'
            
            # Gmail API max is 500 per request
            max_results_per_request = min(500, limit)
            
            # Get message list with pagination
            all_message_ids = []
            page_token = None
            fetched_count = 0
            
            # First, skip emails if needed by fetching pages until we reach skip count
            if skip > 0:
                skip_page_token = None
                skipped = 0
                while skipped < skip:
                    skip_results = self.service.users().messages().list(
                        userId='me',
                        q=search_query,
                        maxResults=min(500, skip - skipped),
                        pageToken=skip_page_token
                    ).execute()
                    
                    skip_messages = skip_results.get('messages', [])
                    skipped += len(skip_messages)
                    skip_page_token = skip_results.get('nextPageToken')
                    
                    if not skip_page_token or not skip_messages:
                        break
                
                # Use the page token from skip as starting point
                page_token = skip_page_token
            
            # Now fetch the actual emails we need
            while fetched_count < limit:
                remaining = limit - fetched_count
                fetch_size = min(max_results_per_request, remaining)
                
                results = self.service.users().messages().list(
                    userId='me',
                    q=search_query,
                    maxResults=fetch_size,
                    pageToken=page_token
                ).execute()
                
                messages = results.get('messages', [])
                if not messages:
                    break
                
                all_message_ids.extend([msg['id'] for msg in messages])
                fetched_count += len(messages)
                
                # Check for next page
                page_token = results.get('nextPageToken')
                if not page_token:
                    break
            
            if not all_message_ids:
                return []
            
            # Fetch full message details
            emails = []
            for msg_id in all_message_ids:
                email_data = self._fetch_message(msg_id)
                if email_data:
                    emails.append(email_data)
            
            return emails
            
        except Exception as e:
            print(f"Error getting emails: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _fetch_message(self, msg_id: str) -> Optional[Dict]:
        """
        Fetch full message details by ID
        
        Args:
            msg_id: Gmail message ID
            
        Returns:
            Email dictionary or None
        """
        if not self.service:
            return None
        
        try:
            # Get message
            message = self.service.users().messages().get(
                userId='me',
                id=msg_id,
                format='full'
            ).execute()
            
            # Parse headers
            headers = message['payload'].get('headers', [])
            header_dict = {h['name'].lower(): h['value'] for h in headers}
            
            # Extract body (improved recursive parsing)
            body_text = ''
            body_html = ''
            
            def extract_body_from_payload(payload_part):
                """Recursively extract body from payload parts"""
                text = ''
                html_content = ''
                
                # Check if this part has nested parts
                if 'parts' in payload_part:
                    for nested_part in payload_part['parts']:
                        nested_text, nested_html = extract_body_from_payload(nested_part)
                        text += nested_text
                        html_content += nested_html
                else:
                    # This is a leaf part - extract its content
                    mime_type = payload_part.get('mimeType', '')
                    body_data = payload_part.get('body', {}).get('data')
                    
                    # Skip attachments
                    filename = payload_part.get('filename')
                    if filename:
                        return '', ''
                    
                    if body_data:
                        try:
                            decoded = base64.urlsafe_b64decode(body_data).decode('utf-8', errors='ignore')
                            
                            if mime_type == 'text/plain':
                                text = decoded
                            elif mime_type == 'text/html':
                                html_content = decoded
                            elif 'text' in mime_type:
                                # Generic text content
                                text = decoded
                        except Exception as e:
                            print(f"⚠️  Error decoding Gmail body part: {e}")
                
                return text, html_content
            
            # Extract from main payload
            payload = message['payload']
            body_text, body_html = extract_body_from_payload(payload)
            
            # If we have HTML but no text, extract text from HTML
            if body_html and not body_text.strip():
                try:
                    # Simple HTML to text extraction
                    text_from_html = re.sub(r'<script[^>]*>.*?</script>', '', body_html, flags=re.DOTALL | re.IGNORECASE)
                    text_from_html = re.sub(r'<style[^>]*>.*?</style>', '', text_from_html, flags=re.DOTALL | re.IGNORECASE)
                    text_from_html = re.sub(r'<[^>]+>', '', text_from_html)
                    text_from_html = re.sub(r'\s+', ' ', text_from_html).strip()
                    text_from_html = html.unescape(text_from_html)
                    if text_from_html:
                        body_text = text_from_html
                except Exception as e:
                    print(f"⚠️  Error extracting text from HTML: {e}")
            
            # Clean up
            body_text = body_text.strip()
            body_html = body_html.strip()
            
            # Check for attachments
            has_attachments = False
            attachments = []
            if 'parts' in payload:
                for part in payload['parts']:
                    if part.get('filename'):
                        has_attachments = True
                        attachments.append({
                            'filename': part['filename'],
                            'mime_type': part.get('mimeType', ''),
                            'size': part['body'].get('size', 0),
                            'attachment_id': part['body'].get('attachmentId')
                        })
            
            # Parse date
            date_str = header_dict.get('date', '')
            try:
                parsed_date = email.utils.parsedate_to_datetime(date_str)
                date_iso = parsed_date.isoformat()
            except:
                date_iso = datetime.now().isoformat()
            
            # Extract actual Message-ID header for proper threading (RFC822 standard)
            actual_message_id = header_dict.get('message-id', '') or header_dict.get('message_id', '')
            if not actual_message_id or not actual_message_id.strip():
                # Fallback to synthetic if no Message-ID header exists
                actual_message_id = f"<{message['id']}@gmail.com>"
            else:
                # Ensure Message-ID has angle brackets
                actual_message_id = actual_message_id.strip()
                if not actual_message_id.startswith('<'):
                    actual_message_id = f"<{actual_message_id}>"
            
            # Build email dict (compatible with existing email_agent format)
            email_data = {
                'message_id': actual_message_id,  # Use actual RFC822 Message-ID header for threading
                'gmail_id': message['id'],
                'gmail_synthetic_id': f"<{message['id']}@gmail.com>",  # Keep for backward compatibility
                'subject': header_dict.get('subject', 'No Subject'),
                'from': header_dict.get('from', ''),
                'to': header_dict.get('to', ''),
                'date': date_str,
                'date_iso': date_iso,
                'text_body': body_text,
                'html_body': body_html,
                'has_attachments': has_attachments,
                'attachments': attachments,
                'thread_id': message.get('threadId', ''),
                'label_ids': message.get('labelIds', []),
                'snippet': message.get('snippet', ''),
                'internal_date': message.get('internalDate', '')
            }
            
            return email_data
            
        except Exception as e:
            print(f"Error fetching message {msg_id}: {e}")
            return None
    
    def watch_mailbox(self, topic_name: str) -> Optional[Dict]:
        """
        Register a watch on the mailbox (for Pub/Sub push notifications)
        
        Args:
            topic_name: Google Cloud Pub/Sub topic name (e.g., "projects/PROJECT_ID/topics/TOPIC_NAME")
            
        Returns:
            Watch response or None
        """
        if not self.service:
            return None
        
        try:
            request = {
                'labelIds': ['INBOX'],
                'topicName': topic_name
            }
            
            response = self.service.users().watch(
                userId='me',
                body=request
            ).execute()
            
            print(f"✓ Gmail watch registered: {response.get('expiration')}")
            return response
            
        except Exception as e:
            print(f"Error registering watch: {e}")
            return None
    
    def stop_watch(self) -> bool:
        """Stop watching the mailbox"""
        if not self.service:
            return False
        
        try:
            self.service.users().stop(userId='me').execute()
            print("✓ Gmail watch stopped")
            return True
        except Exception as e:
            print(f"Error stopping watch: {e}")
            return False

