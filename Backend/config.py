"""
Configuration file for Email Agent
Loads settings from .env files
"""

import os
from dotenv import load_dotenv

# Load .env files (in order of precedence: .env is primary, .env.dev is override)
load_dotenv('.env.dev', override=False)  # Load .env.dev first (if exists)
load_dotenv('.env', override=True)  # Then load .env and override .env.dev (primary config)
load_dotenv()  # Also load from environment variables (highest priority)

# Email Credentials
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS", "")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")

# IMAP Settings (for receiving emails)
IMAP_SERVER = os.getenv("IMAP_SERVER", "imap.gmail.com")
IMAP_PORT = int(os.getenv("IMAP_PORT", "993"))

# SMTP Settings (for sending emails)
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))

# AI Settings (Azure OpenAI) - Read from .env files
AI_PROVIDER = os.getenv("AI_PROVIDER", "azure")
# USE_AZURE_OPENAI is derived from AI_PROVIDER (for backward compatibility)
USE_AZURE_OPENAI = (AI_PROVIDER.lower() == "azure")
AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY", "")
# Fix endpoint format: Azure OpenAI client expects base URL only, not full API path
_raw_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
if _raw_endpoint:
    # If endpoint contains /openai/deployments/, extract just the base URL
    if "/openai/deployments/" in _raw_endpoint:
        # Extract base URL: https://xxx.cognitiveservices.azure.com/
        import re
        match = re.match(r"(https://[^/]+)/", _raw_endpoint)
        if match:
            AZURE_OPENAI_ENDPOINT = match.group(1) + "/"
        else:
            AZURE_OPENAI_ENDPOINT = _raw_endpoint
    else:
        AZURE_OPENAI_ENDPOINT = _raw_endpoint
    # Ensure endpoint ends with /
    if AZURE_OPENAI_ENDPOINT and not AZURE_OPENAI_ENDPOINT.endswith("/"):
        AZURE_OPENAI_ENDPOINT += "/"
else:
    AZURE_OPENAI_ENDPOINT = ""
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1-mini")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")

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

# OAuth/SSO Settings - Read from .env files
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/api/auth/callback")
SESSION_SECRET = os.getenv("SESSION_SECRET", "change-this-to-a-random-secret-key")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# MongoDB Settings - Read from .env files
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "email_agent")

# CORS Settings - Allow multiple origins (comma-separated)
CORS_ORIGINS_STR = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
CORS_ORIGINS = [origin.strip() for origin in CORS_ORIGINS_STR.split(",") if origin.strip()] if CORS_ORIGINS_STR else [
    "http://localhost:3000",
    "http://localhost:3001",
]
# Filter out empty strings
CORS_ORIGINS = [origin.strip() for origin in CORS_ORIGINS if origin.strip()]

# Auto-reply settings - Read from .env files
AUTO_REPLY_ENABLED = os.getenv("AUTO_REPLY_ENABLED", "true").lower() == "true"

