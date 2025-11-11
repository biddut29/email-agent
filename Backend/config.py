"""
Configuration file for Email Agent
Loads settings from database ONLY - no .env fallback
"""

import os
from datetime import datetime

# Try to load config from database ONLY
# Note: We need to import mongodb_manager first, but it might not be initialized yet
# So we'll use lazy loading in get_config_value
config_manager = None
USE_DB_CONFIG = False

def _init_config_manager():
    """Initialize config manager (lazy loading to avoid circular imports)"""
    global config_manager, USE_DB_CONFIG
    if config_manager is None:
        try:
            from config_manager import ConfigManager
            config_manager = ConfigManager()
            
            # Check if MongoDB is connected
            if config_manager.config_collection is None:
                print("❌ ERROR: MongoDB is not connected or database is not accessible.")
                print("   Please ensure MongoDB is running and MONGODB_URI is correct.")
                USE_DB_CONFIG = False
                return
            
            # Check if config collection exists
            if not config_manager.collection_exists():
                print("❌ ERROR: Configuration collection 'app_config' does not exist in database.")
                print("   Please use the admin panel to initialize configuration:")
                print("   1. Go to http://localhost:3000/admin")
                print("   2. Click 'Load from .env' button to initialize configuration")
                print("   3. Or manually configure settings in the Application Configuration section")
                USE_DB_CONFIG = False
                return
            
            USE_DB_CONFIG = True
        except Exception as e:
            print(f"⚠️  Could not initialize config manager: {e}")
            config_manager = None
            USE_DB_CONFIG = False

def get_config_value(key: str, env_key: str, default: str = "") -> str:
    """Get config from database ONLY - no fallback to .env"""
    _init_config_manager()
    if USE_DB_CONFIG and config_manager:
        db_value = config_manager.get_config(key)
        if db_value:
            # Fix: Strip variable name prefix if present (e.g., "AZURE_OPENAI_KEY=value" -> "value")
            # This handles cases where config was saved incorrectly with the variable name
            if '=' in db_value and db_value.startswith(env_key + '='):
                db_value = db_value.split('=', 1)[1]
            return db_value
        # If value is missing, use default (that's okay - user can set it later)
        return default
    # If config manager not initialized or collection doesn't exist, return default
    # This allows the app to start even if database config is not set up yet
    return default

# Email Credentials
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS", "bidduttest@gmail.com")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")

# IMAP Settings (for receiving emails)
IMAP_SERVER = os.getenv("IMAP_SERVER", "imap.gmail.com")
IMAP_PORT = int(os.getenv("IMAP_PORT", "993"))

# SMTP Settings (for sending emails)
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))

# AI Settings (Azure OpenAI) - Read from database first
AI_PROVIDER = get_config_value("ai_provider", "AI_PROVIDER", "azure")
# USE_AZURE_OPENAI is derived from AI_PROVIDER (for backward compatibility)
USE_AZURE_OPENAI = (AI_PROVIDER.lower() == "azure")
AZURE_OPENAI_KEY = get_config_value("azure_openai_key", "AZURE_OPENAI_KEY", "")
AZURE_OPENAI_ENDPOINT = get_config_value("azure_openai_endpoint", "AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_DEPLOYMENT = get_config_value("azure_openai_deployment", "AZURE_OPENAI_DEPLOYMENT", "gpt-4.1-mini")
AZURE_OPENAI_API_VERSION = get_config_value("azure_openai_api_version", "AZURE_OPENAI_API_VERSION", "2024-12-01-preview")

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

# OAuth/SSO Settings - Read from database first
GOOGLE_CLIENT_ID = get_config_value("google_client_id", "GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = get_config_value("google_client_secret", "GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = get_config_value("google_redirect_uri", "GOOGLE_REDIRECT_URI", "http://localhost:8000/api/auth/callback")
SESSION_SECRET = get_config_value("session_secret", "SESSION_SECRET", "change-this-to-a-random-secret-key")
FRONTEND_URL = get_config_value("frontend_url", "FRONTEND_URL", "http://localhost:3000")

# MongoDB Settings - Read from database first
MONGODB_URI = get_config_value("mongodb_uri", "MONGODB_URI", "mongodb://localhost:27017/")
MONGODB_DB_NAME = get_config_value("mongodb_db_name", "MONGODB_DB_NAME", "email_agent")

# CORS Settings - Allow multiple origins (comma-separated)
CORS_ORIGINS_STR = get_config_value("cors_origins", "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
CORS_ORIGINS = [origin.strip() for origin in CORS_ORIGINS_STR.split(",") if origin.strip()] if CORS_ORIGINS_STR else [
    "http://localhost:3000",
    "http://localhost:3001",
    "https://emailagent.duckdns.org",
]
# Filter out empty strings
CORS_ORIGINS = [origin.strip() for origin in CORS_ORIGINS if origin.strip()]

# Auto-reply settings - Read from database first
AUTO_REPLY_ENABLED = get_config_value("auto_reply_enabled", "AUTO_REPLY_ENABLED", "true").lower() == "true"

