import imaplib
import email
from email.header import decode_header
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Email credentials from environment variables
EMAIL = os.getenv("EMAIL_ADDRESS", "")
APP_PASSWORD = os.getenv("EMAIL_PASSWORD", "")

def connect_to_gmail():
    """Connect to Gmail using IMAP"""
    if not EMAIL or not APP_PASSWORD:
        print("✗ Error: EMAIL_ADDRESS and EMAIL_PASSWORD must be set in environment variables")
        return None
    
    try:
        # Connect to Gmail's IMAP server
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(EMAIL, APP_PASSWORD)
        print(f"✓ Successfully connected to {EMAIL}")
        return mail
    except Exception as e:
        print(f"✗ Error connecting to Gmail: {str(e)}")
        return None

def decode_email_subject(subject):
    """Decode email subject"""
    if subject:
        decoded_parts = decode_header(subject)
        decoded_subject = ""
        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                decoded_subject += part.decode(encoding or "utf-8", errors="ignore")
            else:
                decoded_subject += part
        return decoded_subject
    return ""

def get_email_body(msg):
    """Extract email body"""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))
            
            if content_type == "text/plain" and "attachment" not in content_disposition:
                try:
                    body = part.get_payload(decode=True).decode()
                except:
                    pass
    else:
        try:
            body = msg.get_payload(decode=True).decode()
        except:
            pass
    return body

def retrieve_emails(mail, folder="INBOX", num_emails=10):
    """Retrieve recent emails from specified folder"""
    try:
        # Select the mailbox
        mail.select(folder)
        
        # Search for all emails
        status, messages = mail.search(None, "ALL")
        
        if status != "OK":
            print("No emails found.")
            return
        
        # Get list of email IDs
        email_ids = messages[0].split()
        total_emails = len(email_ids)
        
        print(f"\n{'='*80}")
        print(f"Found {total_emails} emails in {folder}")
        print(f"Displaying the last {min(num_emails, total_emails)} emails:")
        print(f"{'='*80}\n")
        
        # Get the latest emails
        latest_email_ids = email_ids[-num_emails:] if total_emails > num_emails else email_ids
        
        # Reverse to show newest first
        latest_email_ids = list(reversed(latest_email_ids))
        
        for idx, email_id in enumerate(latest_email_ids, 1):
            # Fetch the email
            status, msg_data = mail.fetch(email_id, "(RFC822)")
            
            if status != "OK":
                continue
            
            # Parse the email
            msg = email.message_from_bytes(msg_data[0][1])
            
            # Extract email details
            subject = decode_email_subject(msg["Subject"])
            from_email = msg.get("From")
            date = msg.get("Date")
            
            print(f"Email #{idx}")
            print(f"{'─'*80}")
            print(f"From: {from_email}")
            print(f"Date: {date}")
            print(f"Subject: {subject}")
            
            # Get email body
            body = get_email_body(msg)
            if body:
                # Limit body preview to 200 characters
                body_preview = body.strip()[:200]
                if len(body.strip()) > 200:
                    body_preview += "..."
                print(f"\nBody Preview:\n{body_preview}")
            
            print(f"\n{'='*80}\n")
        
    except Exception as e:
        print(f"Error retrieving emails: {str(e)}")

def list_folders(mail):
    """List all available folders"""
    try:
        status, folders = mail.list()
        if status == "OK":
            print("\nAvailable folders:")
            for folder in folders:
                print(f"  - {folder.decode()}")
    except Exception as e:
        print(f"Error listing folders: {str(e)}")

def main():
    # Connect to Gmail
    mail = connect_to_gmail()
    
    if mail:
        # List available folders (optional)
        # list_folders(mail)
        
        # Retrieve emails from INBOX
        retrieve_emails(mail, folder="INBOX", num_emails=10)
        
        # Close connection
        mail.close()
        mail.logout()
        print("Connection closed.")

if __name__ == "__main__":
    main()

