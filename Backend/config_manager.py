"""
Configuration Manager - Store and retrieve app configuration from MongoDB
"""
from typing import Dict, Optional
from datetime import datetime
from mongodb_manager import mongodb_manager
import os
from dotenv import load_dotenv


class ConfigManager:
    """Manages application configuration stored in MongoDB"""
    
    def __init__(self):
        self.config_collection = None
        if mongodb_manager is not None and mongodb_manager.db is not None:
            self.config_collection = mongodb_manager.db['app_config']
            # Create unique index on config_key
            try:
                self.config_collection.create_index("config_key", unique=True, background=True)
            except:
                pass  # Index might already exist
    
    def get_config(self, key: str, default: str = "") -> str:
        """Get a configuration value by key"""
        if self.config_collection is None:
            return default
        
        try:
            doc = self.config_collection.find_one({"config_key": key})
            return doc.get("config_value", default) if doc else default
        except:
            return default
    
    def set_config(self, key: str, value: str) -> bool:
        """Set a configuration value"""
        if self.config_collection is None:
            return False
        
        try:
            self.config_collection.update_one(
                {"config_key": key},
                {"$set": {"config_value": value, "updated_at": datetime.now()}},
                upsert=True
            )
            return True
        except:
            return False
    
    def get_all_config(self) -> Dict[str, str]:
        """Get all configuration as a dictionary"""
        if self.config_collection is None:
            return {}
        
        try:
            configs = self.config_collection.find({})
            return {doc["config_key"]: doc.get("config_value", "") for doc in configs}
        except:
            return {}
    
    def save_config(self, config_dict: Dict[str, str]) -> bool:
        """Save multiple configuration values at once"""
        if self.config_collection is None:
            return False
        
        try:
            for key, value in config_dict.items():
                self.config_collection.update_one(
                    {"config_key": key},
                    {"$set": {"config_value": value, "updated_at": datetime.now()}},
                    upsert=True
                )
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False
    
    def collection_exists(self) -> bool:
        """Check if config collection exists in database"""
        if self.config_collection is None:
            return False
        try:
            # Check if collection exists by trying to list collections
            collections = self.config_collection.database.list_collection_names()
            return 'app_config' in collections
        except:
            return False
    
    def initialize_from_env(self, force_overwrite: bool = False) -> bool:
        """Initialize database with current .env values
        
        Args:
            force_overwrite: If True, always overwrite existing values. If False, only fill missing/empty values.
        """
        if self.config_collection is None:
            return False
        
        try:
            # Reload .env file to ensure we have latest values
            load_dotenv('.env', override=False)  # Load .env first
            load_dotenv('.env.dev', override=True)  # Override with .env.dev if exists
            load_dotenv()  # Also load from environment variables
            
            # Get current .env values
            env_config = {
                "azure_openai_key": os.getenv("AZURE_OPENAI_KEY", ""),
                "azure_openai_endpoint": os.getenv("AZURE_OPENAI_ENDPOINT", ""),
                "azure_openai_deployment": os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1-mini"),
                "azure_openai_api_version": os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview"),
                "ai_provider": os.getenv("AI_PROVIDER", "azure"),
                "mongodb_uri": os.getenv("MONGODB_URI", "mongodb://localhost:27017/"),
                "mongodb_db_name": os.getenv("MONGODB_DB_NAME", "email_agent"),
                "google_client_id": os.getenv("GOOGLE_CLIENT_ID", ""),
                "google_client_secret": os.getenv("GOOGLE_CLIENT_SECRET", ""),
                "google_redirect_uri": os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/api/auth/callback"),
                "session_secret": os.getenv("SESSION_SECRET", ""),
                "frontend_url": os.getenv("FRONTEND_URL", "http://localhost:3000"),
                "cors_origins": os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"),
                "auto_reply_enabled": os.getenv("AUTO_REPLY_ENABLED", "true")
            }
            
            # Only save if database is empty (first time initialization) or force_overwrite is True
            existing_count = self.config_collection.count_documents({})
            if existing_count == 0 or force_overwrite:
                # First time or forced overwrite - save all .env values
                for key, value in env_config.items():
                    self.config_collection.update_one(
                        {"config_key": key},
                        {"$set": {"config_value": value, "updated_at": datetime.now()}},
                        upsert=True
                    )
                print("✓ Initialized configuration from .env to database")
                return True
            else:
                # Database already has config - merge missing keys from .env
                db_config = self.get_all_config()
                for key, value in env_config.items():
                    if key not in db_config or not db_config[key]:
                        # Only add if missing or empty in database
                        self.set_config(key, value)
                return True
        except Exception as e:
            print(f"Error initializing config from env: {e}")
            return False

