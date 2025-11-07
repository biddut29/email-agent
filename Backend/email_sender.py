"""
Email Sender Module - Handles sending emails via SMTP
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import os
from typing import List, Optional
import config


class EmailSender:
    """Handles sending emails via SMTP"""
    
    def __init__(self):
        self.email_address = config.EMAIL_ADDRESS
        self.password = config.EMAIL_PASSWORD
        self.smtp_server = config.SMTP_SERVER
        self.smtp_port = config.SMTP_PORT
    
    def send_email(self, 
                   to: str or List[str],
                   subject: str,
                   body: str,
                   cc: Optional[List[str]] = None,
                   bcc: Optional[List[str]] = None,
                   attachments: Optional[List[str]] = None,
                   html: bool = False) -> bool:
        """
        Send an email
        
        Args:
            to: Recipient email address(es)
            subject: Email subject
            body: Email body text
            cc: CC recipients
            bcc: BCC recipients
            attachments: List of file paths to attach
            html: If True, body is treated as HTML
        
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.email_address
            
            # Handle recipients
            if isinstance(to, str):
                to = [to]
            msg['To'] = ', '.join(to)
            
            if cc:
                msg['Cc'] = ', '.join(cc)
            
            msg['Subject'] = subject
            
            # Add body
            mime_type = 'html' if html else 'plain'
            msg.attach(MIMEText(body, mime_type))
            
            # Add attachments
            if attachments:
                for file_path in attachments:
                    if os.path.exists(file_path):
                        self._attach_file(msg, file_path)
                    else:
                        print(f"Warning: Attachment not found: {file_path}")
            
            # Combine all recipients
            all_recipients = to.copy()
            if cc:
                all_recipients.extend(cc)
            if bcc:
                all_recipients.extend(bcc)
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.email_address, self.password)
                server.send_message(msg)
                server.quit()
            
            print(f"✓ Email sent successfully to {', '.join(to)}")
            return True
            
        except Exception as e:
            print(f"✗ Error sending email: {str(e)}")
            return False
    
    def _attach_file(self, msg: MIMEMultipart, file_path: str):
        """Attach a file to the email"""
        try:
            with open(file_path, 'rb') as file:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(file.read())
                encoders.encode_base64(part)
                
                filename = os.path.basename(file_path)
                part.add_header('Content-Disposition', f'attachment; filename= {filename}')
                msg.attach(part)
        except Exception as e:
            print(f"Error attaching file {file_path}: {str(e)}")
    
    def reply_to_email(self,
                       original_email: dict,
                       body: str,
                       html: bool = False,
                       attachments: Optional[List[str]] = None,
                       include_original: bool = True) -> bool:
        """
        Reply to an email
        
        Args:
            original_email: Dictionary containing original email data
            body: Reply body text
            html: If True, body is treated as HTML
            attachments: Optional list of file paths to attach
            include_original: If True, include original email body in reply
        
        Returns:
            True if sent successfully
        """
        try:
            # Extract original sender
            original_from = original_email.get('from', '')
            original_subject = original_email.get('subject', '')
            original_date = original_email.get('date', '')
            
            # Format reply subject
            if not original_subject.startswith('Re:'):
                subject = f"Re: {original_subject}"
            else:
                subject = original_subject
            
            # Build reply body with original email included
            if include_original:
                original_body = original_email.get('text_body', '') or original_email.get('html_body', '')
                
                # If body is empty, use a placeholder message
                if not original_body or not original_body.strip():
                    original_body = "(No body content - subject-only email)"
                
                if html:
                    # HTML format with quoted original
                    reply_body = f"""
{body}

<div style="border-left: 3px solid #ccc; padding-left: 10px; margin-top: 20px; color: #666;">
  <p style="margin: 0; font-size: 12px;"><strong>From:</strong> {original_from}</p>
  <p style="margin: 0; font-size: 12px;"><strong>Date:</strong> {original_date}</p>
  <p style="margin: 0; font-size: 12px;"><strong>Subject:</strong> {original_subject}</p>
  <div style="margin-top: 10px;">
    {original_email.get('html_body', original_body) if original_email.get('html_body') else original_body}
  </div>
</div>
"""
                else:
                    # Plain text format with quoted original
                    reply_body = f"""{body}

---------- Original Message ----------
From: {original_from}
Date: {original_date}
Subject: {original_subject}

{original_body}
"""
            else:
                reply_body = body
            
            return self.send_email(
                to=original_from,
                subject=subject,
                body=reply_body,
                html=html,
                attachments=attachments
            )
            
        except Exception as e:
            print(f"Error replying to email: {str(e)}")
            return False
    
    def forward_email(self,
                      original_email: dict,
                      to: str or List[str],
                      additional_message: Optional[str] = None,
                      attachments: Optional[List[str]] = None) -> bool:
        """
        Forward an email
        
        Args:
            original_email: Dictionary containing original email data
            to: Recipient(s) to forward to
            additional_message: Optional message to add before forwarded content
            attachments: Optional list of file paths to attach
        
        Returns:
            True if sent successfully
        """
        try:
            original_subject = original_email.get('subject', '')
            original_from = original_email.get('from', '')
            original_date = original_email.get('date', '')
            original_body = original_email.get('text_body', '')
            
            # Format forwarded subject
            if not original_subject.startswith('Fwd:'):
                subject = f"Fwd: {original_subject}"
            else:
                subject = original_subject
            
            # Format forwarded body
            forwarded_body = ""
            if additional_message:
                forwarded_body += f"{additional_message}\n\n"
            
            forwarded_body += f"---------- Forwarded message ---------\n"
            forwarded_body += f"From: {original_from}\n"
            forwarded_body += f"Date: {original_date}\n"
            forwarded_body += f"Subject: {original_subject}\n\n"
            forwarded_body += original_body
            
            return self.send_email(
                to=to,
                subject=subject,
                body=forwarded_body,
                attachments=attachments
            )
            
        except Exception as e:
            print(f"Error forwarding email: {str(e)}")
            return False
    
    def send_bulk_emails(self, 
                        recipients: List[str],
                        subject: str,
                        body: str,
                        html: bool = False) -> dict:
        """
        Send the same email to multiple recipients individually
        
        Returns:
            Dictionary with 'success' and 'failed' lists
        """
        results = {'success': [], 'failed': []}
        
        for recipient in recipients:
            if self.send_email(to=recipient, subject=subject, body=body, html=html):
                results['success'].append(recipient)
            else:
                results['failed'].append(recipient)
        
        print(f"\nBulk send complete: {len(results['success'])} sent, {len(results['failed'])} failed")
        return results

