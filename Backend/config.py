"""
Configuration file for Email Agent
Loads settings from .env file
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Email Credentials
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS", "bidduttest@gmail.com")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")

# IMAP Settings (for receiving emails)
IMAP_SERVER = os.getenv("IMAP_SERVER", "imap.gmail.com")
IMAP_PORT = int(os.getenv("IMAP_PORT", "993"))

# SMTP Settings (for sending emails)
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))

# AI Settings (Azure OpenAI)
USE_AZURE_OPENAI = os.getenv("USE_AZURE_OPENAI", "True").lower() == "true"
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY", "")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1-mini")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")

# Alternative: Regular OpenAI / Anthropic (if not using Azure)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Agent Settings
DEFAULT_MAILBOX = os.getenv("DEFAULT_MAILBOX", "INBOX")
MAX_EMAILS_TO_PROCESS = int(os.getenv("MAX_EMAILS_TO_PROCESS", "10"))

# Email Categories
EMAIL_CATEGORIES = [
    "urgent",
    "important",
    "spam",
    "promotional",
    "personal",
    "work",
    "newsletter",
    "other"
]

# Auto-response settings
AUTO_RESPOND = os.getenv("AUTO_RESPOND", "False").lower() == "true"
AUTO_RESPOND_ONLY_TO = []  # List of email addresses to auto-respond to (empty = all)

# Draft mode - if True, will create drafts instead of sending immediately
DRAFT_MODE = os.getenv("DRAFT_MODE", "True").lower() == "true"

# Gmail API Settings (for push notifications)
GMAIL_CLIENT_ID = os.getenv("GMAIL_CLIENT_ID", "")
GMAIL_CLIENT_SECRET = os.getenv("GMAIL_CLIENT_SECRET", "")
GMAIL_USE_API = os.getenv("GMAIL_USE_API", "False").lower() == "true"
GMAIL_PUBSUB_TOPIC = os.getenv("GMAIL_PUBSUB_TOPIC", "")  # Format: projects/PROJECT_ID/topics/TOPIC_NAME

# OAuth/SSO Settings
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/api/auth/callback")
SESSION_SECRET = os.getenv("SESSION_SECRET", "change-this-to-a-random-secret-key")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

