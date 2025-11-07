"""
Email Receiver Module - Handles retrieving and reading emails via IMAP
"""

import imaplib
import email
from email.header import decode_header
from datetime import datetime
from typing import List, Dict, Optional
import re
import html
import config


class EmailReceiver:
    """Handles receiving and reading emails from Gmail"""
    
    def __init__(self):
        self.email_address = config.EMAIL_ADDRESS
        self.password = config.EMAIL_PASSWORD
        self.imap_server = config.IMAP_SERVER
        self.imap_port = config.IMAP_PORT
        self.mail = None
    
    def connect(self) -> bool:
        """Connect to Gmail via IMAP"""
        try:
            import socket
            # Set socket timeout to prevent hanging
            socket.setdefaulttimeout(10)  # 10 second timeout
            self.mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port, timeout=10)
            self.mail.login(self.email_address, self.password)
            print(f"✓ Connected to {self.email_address}")
            return True
        except Exception as e:
            print(f"✗ Connection error: {str(e)}")
            return False
    
    def disconnect(self):
        """Disconnect from the email server"""
        try:
            if self.mail:
                self.mail.close()
                self.mail.logout()
                print("✓ Disconnected from email server")
        except:
            pass
    
    def list_folders(self) -> List[str]:
        """List all available folders/mailboxes"""
        try:
            status, folders = self.mail.list()
            if status == "OK":
                return [folder.decode() for folder in folders]
            return []
        except Exception as e:
            print(f"Error listing folders: {str(e)}")
            return []
    
    def _decode_header(self, header: str) -> str:
        """Decode email header"""
        if not header:
            return ""
        
        decoded_parts = decode_header(header)
        decoded_string = ""
        
        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                try:
                    decoded_string += part.decode(encoding or "utf-8", errors="ignore")
                except:
                    decoded_string += part.decode("utf-8", errors="ignore")
            else:
                decoded_string += str(part)
        
        return decoded_string
    
    def _extract_body(self, msg) -> tuple:
        """Extract plain text and HTML body from email (improved parsing)"""
        text_body = ""
        html_body = ""
        
        def decode_payload(part):
            """Helper to decode email payload with proper encoding"""
            try:
                # Try to get charset from part
                charset = part.get_content_charset() or 'utf-8'
                payload = part.get_payload(decode=True)
                if payload:
                    return payload.decode(charset, errors='ignore')
            except:
                try:
                    # Fallback: try utf-8
                    payload = part.get_payload(decode=True)
                    if payload:
                        return payload.decode('utf-8', errors='ignore')
                except:
                    try:
                        # Last resort: decode as string
                        payload = part.get_payload(decode=False)
                        if isinstance(payload, str):
                            return payload
                    except:
                        pass
            return None
        
        if msg.is_multipart():
            # Track parts we've processed to avoid duplicates
            processed_parts = set()
            processed_part_ids = set()  # Track by Content-ID and position
            
            # First pass: look for text/plain and text/html in multipart/alternative
            # This handles emails with both plain and HTML versions
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = part.get("Content-Disposition", "")
                # Handle None case properly
                if content_disposition is None:
                    content_disposition = ""
                else:
                    content_disposition = str(content_disposition).lower()
                
                # Skip attachments (only process body parts)
                if content_disposition and "attachment" in content_disposition:
                    continue
                
                # Handle multipart/alternative - prefer text/plain over text/html
                if content_type == "multipart/alternative":
                    # Process alternative parts in order of preference
                    alternative_parts = []
                    for alt_part in part.walk():
                        alt_ct = alt_part.get_content_type()
                        if alt_ct in ["text/plain", "text/html"]:
                            alt_disposition = str(alt_part.get("Content-Disposition", "")).lower()
                            if "attachment" not in alt_disposition and not alt_part.get_filename():
                                # Create unique ID for this part - use object id to track the actual part instance
                                alt_id = id(alt_part)
                                alt_content_id = alt_part.get('Content-ID', '')
                                alternative_parts.append((alt_ct, alt_part, alt_id, alt_content_id))
                                processed_part_ids.add(alt_id)  # Mark as processed by object id
                                if alt_content_id:
                                    processed_part_ids.add(alt_content_id)  # Also mark by Content-ID
                    
                    # Prefer plain text, but use HTML if that's all we have
                    for alt_ct, alt_part, alt_id, alt_content_id in alternative_parts:
                        if alt_ct == "text/plain" and not text_body:
                            decoded = decode_payload(alt_part)
                            if decoded and decoded.strip():
                                text_body = decoded.strip()
                                break
                    
                    # If no plain text, use HTML
                    if not text_body:
                        for alt_ct, alt_part, alt_id, alt_content_id in alternative_parts:
                            if alt_ct == "text/html":
                                decoded = decode_payload(alt_part)
                                if decoded and decoded.strip():
                                    html_body = decoded.strip()
                                    break
                    continue
                
                # Skip nested multipart containers (just process their children)
                if content_type.startswith("multipart/"):
                    continue
                
                # Check if this part has a filename (likely attachment)
                filename = part.get_filename()
                if filename:
                    # Has filename, likely an attachment, skip
                    continue
                
                # Create a unique identifier for this part to avoid processing duplicates
                # Use object id as primary identifier (most reliable)
                part_obj_id = id(part)
                part_content_id = part.get('Content-ID', '')
                
                # Skip if we've already processed this exact part object
                if part_obj_id in processed_part_ids:
                    continue
                processed_part_ids.add(part_obj_id)
                
                # Also track by Content-ID if available (for parts with same content)
                if part_content_id:
                    processed_part_ids.add(part_content_id)
                
                # Also track by content type and Content-ID to catch duplicates
                part_key = f"{content_type}_{part_content_id}"
                if part_key in processed_parts:
                    continue
                processed_parts.add(part_key)
                
                try:
                    decoded_content = decode_payload(part)
                    if not decoded_content or not decoded_content.strip():
                        # Try alternative decoding methods
                        try:
                            # Try getting payload without decoding first
                            raw_payload = part.get_payload(decode=False)
                            if isinstance(raw_payload, str) and raw_payload.strip():
                                decoded_content = raw_payload.strip()
                        except:
                            pass
                        
                        if not decoded_content or not decoded_content.strip():
                            continue
                    
                    # Set body content (don't append to avoid duplicates)
                    # Only set if we don't already have content for this type
                    if content_type == "text/plain":
                        if not text_body:
                            text_body = decoded_content.strip()
                    elif content_type == "text/html":
                        if not html_body:
                            html_body = decoded_content.strip()
                    elif content_type == "text/" or content_type.startswith("text/"):
                        # Generic text content - only set if we don't have text_body yet
                        if not text_body:
                            text_body = decoded_content.strip()
                    else:
                        # For other text-like content, try to extract
                        if "text" in content_type.lower() and not text_body:
                            text_body = decoded_content.strip()
                        # Also try if payload is a string (might be plain text)
                        elif isinstance(part.get_payload(decode=False), str) and not text_body:
                            raw_str = str(part.get_payload(decode=False))
                            if raw_str.strip():
                                text_body = raw_str.strip()
                except Exception as e:
                    print(f"⚠️  Error extracting body part ({content_type}): {e}")
                    continue
        else:
            # Simple (non-multipart) message
            try:
                decoded_content = decode_payload(msg)
                if decoded_content:
                    content_type = msg.get_content_type()
                    if content_type == "text/plain":
                        text_body = decoded_content
                    elif content_type == "text/html":
                        html_body = decoded_content
                    else:
                        # Try to use as text anyway
                        text_body = decoded_content
            except Exception as e:
                print(f"⚠️  Error extracting simple body: {e}")
        
        # If we have HTML but no text, try to extract text from HTML
        if html_body and not text_body.strip():
            try:
                # Simple HTML to text extraction (remove tags)
                # Remove script and style tags
                text_from_html = re.sub(r'<script[^>]*>.*?</script>', '', html_body, flags=re.DOTALL | re.IGNORECASE)
                text_from_html = re.sub(r'<style[^>]*>.*?</style>', '', text_from_html, flags=re.DOTALL | re.IGNORECASE)
                # Remove HTML tags
                text_from_html = re.sub(r'<[^>]+>', '', text_from_html)
                # Clean up whitespace
                text_from_html = re.sub(r'\s+', ' ', text_from_html).strip()
                # Decode HTML entities
                text_from_html = html.unescape(text_from_html)
                if text_from_html:
                    text_body = text_from_html
            except:
                pass
        
        # For reply emails, try to extract just the new reply content (before quoted original)
        # This helps when reply emails have quoted original content mixed in
        # But keep the full body as backup if separation fails
        original_text_body = text_body  # Keep backup
        if text_body:
            # Common reply patterns that indicate start of quoted content
            quote_patterns = [
                r'----------\s*Original\s*Message\s*----------',
                r'From:\s*.*?\n.*?Date:\s*.*?\n.*?Subject:',
                r'On\s+.*?\s+wrote:',
                r'Le\s+.*?\s+a\s+écrit\s*:',
                r'^\s*On\s+.*?\s+said:',
            ]
            
            # Try to find where quoted content starts
            for pattern in quote_patterns:
                match = re.search(pattern, text_body, re.IGNORECASE | re.MULTILINE)
                if match:
                    # Extract only the content before the quoted section
                    new_content = text_body[:match.start()].strip()
                    if new_content and len(new_content) > 5:  # Only if we have meaningful content
                        text_body = new_content
                        break
            
            # If we couldn't separate but body starts with > (common quote marker)
            # Try to extract lines that don't start with >
            if text_body == original_text_body and text_body.strip().startswith('>'):
                lines = text_body.split('\n')
                new_lines = []
                for line in lines:
                    # Stop at first quoted line, but include previous non-quoted lines
                    if line.strip().startswith('>'):
                        break
                    new_lines.append(line)
                if new_lines:
                    separated = '\n'.join(new_lines).strip()
                    if separated and len(separated) > 5:
                        text_body = separated
        
        # Similar for HTML - try to extract new content before quoted blocks
        original_html_body = html_body  # Keep backup
        if html_body:
            # Look for common HTML quote markers
            html_quote_patterns = [
                r'<blockquote[^>]*>',
                r'<div[^>]*class="[^"]*quote[^"]*"[^>]*>',
                r'<div[^>]*style="[^"]*border[^"]*"[^>]*>.*?Original\s*Message',
            ]
            
            for pattern in html_quote_patterns:
                match = re.search(pattern, html_body, re.IGNORECASE | re.DOTALL)
                if match:
                    # Extract only the content before the quoted section
                    new_content = html_body[:match.start()].strip()
                    if new_content and len(new_content) > 10:  # Only if we have meaningful content
                        html_body = new_content
                        break
            
            # If separation didn't work, keep the full HTML body
            # At least we have the content, even if it includes quoted parts
        
        # Clean up text body
        text_body = text_body.strip()
        html_body = html_body.strip()
        
        # If still no content, try more aggressive extraction
        if not text_body and not html_body:
            try:
                # Strategy 1: Try raw payload
                raw_payload = msg.get_payload(decode=False)
                if isinstance(raw_payload, str):
                    # Check if it's base64 encoded or has actual content
                    if len(raw_payload.strip()) > 10:  # Has meaningful content
                        text_body = raw_payload.strip()
                elif isinstance(raw_payload, list):
                    # Sometimes payload is a list of Message objects
                    for sub_msg in raw_payload:
                        # Check if it's a Message-like object (has get_payload method)
                        if hasattr(sub_msg, 'get_payload') and hasattr(sub_msg, 'get_content_type'):
                            sub_text, sub_html = self._extract_body(sub_msg)
                            if sub_text:
                                text_body += sub_text + "\n"
                            if sub_html:
                                html_body += sub_html
                
                # Strategy 2: Try to extract from ALL parts, even if they look like attachments
                if not text_body and not html_body and msg.is_multipart():
                    for part in msg.walk():
                        try:
                            # Try to get ANY text content, even from parts we normally skip
                            part_payload = part.get_payload(decode=True)
                            if part_payload:
                                try:
                                    decoded = part_payload.decode('utf-8', errors='ignore')
                                    # Check if it looks like text (not binary)
                                    if decoded and len(decoded.strip()) > 5 and not decoded.startswith(b'\x00'.decode('utf-8', errors='ignore')):
                                        # Check content type
                                        ct = part.get_content_type()
                                        if 'text' in ct.lower() or 'html' in ct.lower():
                                            if 'html' in ct.lower():
                                                html_body = decoded
                                            else:
                                                text_body = decoded
                                            break
                                except:
                                    pass
                        except:
                            continue
                
                # Strategy 3: Try to get content from email as_string() method
                if not text_body and not html_body:
                    try:
                        email_str = str(msg)
                        # Look for body content in the string representation
                        # Email format usually has headers, blank line, then body
                        parts = email_str.split('\n\n', 1)
                        if len(parts) > 1:
                            potential_body = parts[1]
                            # Remove quoted-printable markers and decode
                            if potential_body and len(potential_body.strip()) > 10:
                                # Try to clean it up
                                cleaned = potential_body.strip()
                                # Remove email headers that might be in body
                                if not cleaned.startswith('From:') and not cleaned.startswith('Date:'):
                                    text_body = cleaned[:5000]  # Limit to 5000 chars
                    except:
                        pass
                        
            except Exception as e:
                print(f"⚠️  Error in fallback extraction: {e}")
        
        # Final cleanup
        text_body = text_body.strip()
        html_body = html_body.strip()
        
        # Debug logging for empty bodies
        if not text_body and not html_body:
            print(f"⚠️  Warning: Empty body extracted")
            print(f"   Content-Type: {msg.get_content_type()}")
            print(f"   IsMultipart: {msg.is_multipart()}")
            print(f"   Subject: {msg.get('Subject', 'No Subject')[:50]}")
            # Try to get raw payload info
            try:
                payload = msg.get_payload(decode=False)
                if isinstance(payload, list):
                    print(f"   Payload type: list with {len(payload)} items")
                    for i, item in enumerate(payload):
                        if hasattr(item, 'get_content_type'):
                            print(f"     Item {i}: {item.get_content_type()}")
                elif isinstance(payload, str):
                    print(f"   Payload type: string (length: {len(payload)})")
                    if len(payload) > 0:
                        print(f"   Payload preview: {payload[:100]}")
            except Exception as e:
                print(f"   Error inspecting payload: {e}")
        else:
            # Success logging
            print(f"✓ Body extracted: text={len(text_body)} chars, html={len(html_body)} chars")
        
        return text_body, html_body
    
    def _extract_attachments(self, msg) -> List[Dict]:
        """Extract attachment information from email"""
        attachments = []
        
        if msg.is_multipart():
            for part in msg.walk():
                content_disposition = str(part.get("Content-Disposition"))
                
                if "attachment" in content_disposition:
                    filename = part.get_filename()
                    if filename:
                        filename = self._decode_header(filename)
                        attachments.append({
                            "filename": filename,
                            "content_type": part.get_content_type(),
                            "size": len(part.get_payload(decode=True) or b"")
                        })
        
        return attachments
    
    def get_emails(self, folder: str = "INBOX", limit: int = 10, 
                   unread_only: bool = False) -> List[Dict]:
        """
        Retrieve emails from specified folder
        
        Args:
            folder: Mailbox folder to read from
            limit: Maximum number of emails to retrieve
            unread_only: If True, only retrieve unread emails
        
        Returns:
            List of email dictionaries
        """
        try:
            # Ensure connection is alive
            try:
                self.mail.noop()  # Check if connection is alive
            except:
                # Reconnect if connection is dead
                print("⚠ Connection lost, reconnecting...")
                self.connect()
            
            # Select the mailbox
            self.mail.select(folder)
            
            # Search criteria
            search_criteria = "UNSEEN" if unread_only else "ALL"
            status, messages = self.mail.search(None, search_criteria)
            
            if status != "OK":
                return []
            
            email_ids = messages[0].split()
            if not email_ids:
                return []
            
            # Get the latest emails
            latest_email_ids = email_ids[-limit:] if len(email_ids) > limit else email_ids
            latest_email_ids = list(reversed(latest_email_ids))
            
            emails = []
            
            for email_id in latest_email_ids:
                email_data = self._fetch_email(email_id)
                if email_data:
                    emails.append(email_data)
            
            return emails
            
        except Exception as e:
            print(f"Error retrieving emails: {str(e)}")
            return []
    
    def _fetch_email(self, email_id: bytes) -> Optional[Dict]:
        """Fetch and parse a single email"""
        try:
            status, msg_data = self.mail.fetch(email_id, "(RFC822)")
            
            if status != "OK":
                return None
            
            msg = email.message_from_bytes(msg_data[0][1])
            
            # Extract basic info
            subject = self._decode_header(msg.get("Subject", ""))
            from_email = self._decode_header(msg.get("From", ""))
            to_email = self._decode_header(msg.get("To", ""))
            date_str = msg.get("Date", "")
            message_id = msg.get("Message-ID", "")
            
            # Extract body
            text_body, html_body = self._extract_body(msg)
            
            # Extract attachments
            attachments = self._extract_attachments(msg)
            
            return {
                "id": email_id.decode(),
                "message_id": message_id,
                "subject": subject,
                "from": from_email,
                "to": to_email,
                "date": date_str,
                "text_body": text_body,
                "html_body": html_body,
                "attachments": attachments,
                "has_attachments": len(attachments) > 0
            }
            
        except Exception as e:
            print(f"Error fetching email {email_id}: {str(e)}")
            return None
    
    def mark_as_read(self, email_id: str):
        """Mark an email as read"""
        try:
            self.mail.store(email_id.encode(), '+FLAGS', '\\Seen')
        except Exception as e:
            print(f"Error marking email as read: {str(e)}")
    
    def mark_as_unread(self, email_id: str):
        """Mark an email as unread"""
        try:
            self.mail.store(email_id.encode(), '-FLAGS', '\\Seen')
        except Exception as e:
            print(f"Error marking email as unread: {str(e)}")
    
    def delete_email(self, email_id: str):
        """Delete an email (move to trash)"""
        try:
            self.mail.store(email_id.encode(), '+FLAGS', '\\Deleted')
            self.mail.expunge()
        except Exception as e:
            print(f"Error deleting email: {str(e)}")
    
    def get_attachment(self, email_id: str, filename: str) -> Optional[Dict]:
        """
        Get attachment content from an email
        
        Args:
            email_id: The email ID
            filename: Name of the attachment to extract
        
        Returns:
            Dictionary with filename, content_type, and data (base64 encoded)
        """
        try:
            import base64
            
            status, msg_data = self.mail.fetch(email_id.encode(), "(RFC822)")
            
            if status != "OK":
                return None
            
            msg = email.message_from_bytes(msg_data[0][1])
            
            if msg.is_multipart():
                for part in msg.walk():
                    content_disposition = str(part.get("Content-Disposition"))
                    
                    if "attachment" in content_disposition:
                        part_filename = part.get_filename()
                        if part_filename:
                            part_filename = self._decode_header(part_filename)
                            
                            if part_filename == filename:
                                content = part.get_payload(decode=True)
                                if content:
                                    return {
                                        "filename": filename,
                                        "content_type": part.get_content_type(),
                                        "size": len(content),
                                        "data": base64.b64encode(content).decode('utf-8')
                                    }
            
            return None
            
        except Exception as e:
            print(f"Error extracting attachment: {str(e)}")
            return None
    
    def get_all_attachments(self, email_id: str) -> List[Dict]:
        """
        Get all attachments from an email with their content
        
        Args:
            email_id: The email ID
        
        Returns:
            List of attachment dictionaries with data
        """
        try:
            import base64
            
            status, msg_data = self.mail.fetch(email_id.encode(), "(RFC822)")
            
            if status != "OK":
                return []
            
            msg = email.message_from_bytes(msg_data[0][1])
            attachments = []
            
            if msg.is_multipart():
                for part in msg.walk():
                    content_disposition = str(part.get("Content-Disposition"))
                    
                    if "attachment" in content_disposition:
                        filename = part.get_filename()
                        if filename:
                            filename = self._decode_header(filename)
                            content = part.get_payload(decode=True)
                            
                            if content:
                                # Try to decode text attachments
                                text_content = None
                                content_type = part.get_content_type()
                                
                                if content_type.startswith('text/'):
                                    try:
                                        text_content = content.decode('utf-8', errors='ignore')
                                    except:
                                        pass
                                
                                attachments.append({
                                    "filename": filename,
                                    "content_type": content_type,
                                    "size": len(content),
                                    "data": base64.b64encode(content).decode('utf-8'),
                                    "text_content": text_content  # For text files
                                })
            
            return attachments
            
        except Exception as e:
            print(f"Error extracting attachments: {str(e)}")
            return []
    
    def search_emails(self, criteria: str, folder: str = "INBOX", limit: int = None) -> List[Dict]:
        """
        Search emails with custom criteria
        
        Args:
            criteria: IMAP search criteria
            folder: Mailbox folder
            limit: Maximum number of emails to return
        
        Examples:
            - 'FROM "sender@example.com"'
            - 'SUBJECT "Important"'
            - 'SINCE "01-Jan-2025"'
        """
        try:
            # Ensure connection is alive
            try:
                self.mail.noop()
            except:
                print("⚠ Connection lost, reconnecting...")
                self.connect()
            
            self.mail.select(folder)
            status, messages = self.mail.search(None, criteria)
            
            if status != "OK":
                return []
            
            email_ids = messages[0].split()
            
            # Apply limit if specified
            if limit and len(email_ids) > limit:
                email_ids = email_ids[-limit:]
            
            # Reverse to get most recent first
            email_ids = list(reversed(email_ids))
            
            emails = []
            
            for email_id in email_ids:
                email_data = self._fetch_email(email_id)
                if email_data:
                    emails.append(email_data)
            
            return emails
            
        except Exception as e:
            print(f"Error searching emails: {str(e)}")
            return []

