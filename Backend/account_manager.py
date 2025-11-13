"""
Account Manager - Manages multiple email accounts using persistent MongoDB
"""

from typing import List, Dict, Optional
from datetime import datetime
from pymongo import MongoClient, ASCENDING
import os


class AccountManager:
    """Manages email accounts using persistent MongoDB database"""
    
    def __init__(self, mongodb_manager=None):
        """Initialize with MongoDB manager"""
        self.mongodb_manager = mongodb_manager
        
        if mongodb_manager and mongodb_manager.db is not None:
            self.db = mongodb_manager.db
            self.accounts_collection = self.db['accounts']
            self._create_indexes()
            self.active_account_id = self._get_active_account_id()
            print(f"✓ Account Manager initialized (MongoDB)")
        else:
            print(f"⚠ Account Manager: MongoDB not available, using in-memory mode")
            self.db = None
            self.accounts_collection = None
            self.active_account_id = None
    
    def _create_indexes(self):
        """Create database indexes for performance"""
        if self.accounts_collection is None:
            return
        
        try:
            # Unique index on email
            self.accounts_collection.create_index("email", unique=True, background=True, name="idx_email_unique")
            
            # Unique index on integer id (for compatibility with existing code)
            self.accounts_collection.create_index("id", unique=True, background=True, name="idx_id_unique")
            
            # Index on is_active for faster active account queries
            self.accounts_collection.create_index("is_active", background=True, name="idx_is_active")
            
            print("✓ Account collection indexes created")
        except Exception as e:
            print(f"⚠ Error creating account indexes: {e}")
    
    def _get_next_id(self) -> int:
        """Get next integer ID for account (maintains compatibility with int-based code)"""
        if self.accounts_collection is None:
            return 1
        
        try:
            # Get the highest ID
            last_account = self.accounts_collection.find_one(
                sort=[("id", -1)]
            )
            if last_account and 'id' in last_account:
                return last_account['id'] + 1
            return 1
        except Exception as e:
            print(f"Error getting next ID: {e}")
            return 1
    
    def _get_active_account_id(self) -> Optional[int]:
        """Get the currently active account ID from MongoDB (returns integer ID)"""
        if self.accounts_collection is None:
            return None
        
        try:
            account = self.accounts_collection.find_one({"is_active": True}, {"id": 1})
            if account and 'id' in account:
                return account['id']
        except Exception as e:
            print(f"Error getting active account ID: {e}")
        
        return None
    
    def add_account(self, email: str, password: str, 
                    imap_server: str = 'imap.gmail.com',
                    imap_port: int = 993,
                    smtp_server: str = 'smtp.gmail.com',
                    smtp_port: int = 587) -> Dict:
        """
        Add a new email account
        
        Returns:
            Dict with account info
        """
        if self.accounts_collection is None:
            return {"error": "MongoDB not available"}
        
        try:
            # Check if account already exists
            existing = self.accounts_collection.find_one({"email": email})
            if existing:
                # Account exists - update password and settings
                account_int_id = existing.get('id')
                if not account_int_id:
                    account_int_id = self._get_next_id()
                    self.accounts_collection.update_one(
                        {"email": email},
                        {"$set": {"id": account_int_id}}
                    )
                
                # Update password and server settings
                self.accounts_collection.update_one(
                    {"email": email},
                    {"$set": {
                        "password": password,
                        "imap_server": imap_server,
                        "imap_port": imap_port,
                        "smtp_server": smtp_server,
                        "smtp_port": smtp_port
                    }}
                )
                
                # If no active account, make this one active
                if not self.get_active_account():
                    self.set_active_account(account_int_id)
                
                print(f"✓ Account updated: {email} (ID: {account_int_id})")
                return {
                    **self.get_account(account_int_id),
                    "updated": True,
                    "message": f"Account {email} already existed. Password and settings updated."
                }
            
            # Get next integer ID
            account_int_id = self._get_next_id()
            
            # Create new account document
            account_doc = {
                "id": account_int_id,  # Integer ID for compatibility
                "email": email,
                "password": password,
                "imap_server": imap_server,
                "imap_port": imap_port,
                "smtp_server": smtp_server,
                "smtp_port": smtp_port,
                "is_active": False,
                "auto_reply_enabled": True,  # Default to enabled
                "custom_prompt": "",  # Custom prompt for AI responses
                "created_at": datetime.utcnow()
            }
            
            # Insert into MongoDB
            result = self.accounts_collection.insert_one(account_doc)
            
            # If this is the first account, make it active
            if self.get_account_count() == 1:
                self.set_active_account(account_int_id)
            
            print(f"✓ Account added: {email} (ID: {account_int_id})")
            return self.get_account(account_int_id)
            
        except Exception as e:
            return {"error": str(e)}
    
    def remove_account(self, account_id: int) -> Dict:
        """Remove an account by integer ID"""
        if self.accounts_collection is None:
            return {"error": "MongoDB not available"}
        
        try:
            result = self.accounts_collection.delete_one({"id": account_id})
            
            if result.deleted_count > 0:
                # If we deleted the active account, set another as active
                if self.active_account_id == account_id:
                    accounts = self.get_all_accounts()
                    if accounts:
                        # Set first account as active
                        self.set_active_account(accounts[0]['id'])
                    else:
                        self.active_account_id = None
                
                return {"success": True, "message": "Account removed"}
            else:
                return {"error": "Account not found"}
                
        except Exception as e:
            return {"error": str(e)}
    
    def get_account(self, account_id: int) -> Optional[Dict]:
        """Get account by integer ID"""
        if self.accounts_collection is None:
            return None
        
        try:
            account = self.accounts_collection.find_one({"id": account_id})
            if account:
                return self._format_account(account)
            return None
        except Exception as e:
            print(f"Error getting account: {e}")
            return None
    
    def get_account_by_email(self, email: str) -> Optional[Dict]:
        """Get account by email"""
        if self.accounts_collection is None:
            return None
        
        try:
            account = self.accounts_collection.find_one({"email": email})
            if account:
                return self._format_account(account)
            return None
        except Exception as e:
            print(f"Error getting account by email: {e}")
            return None
    
    def get_all_accounts(self) -> List[Dict]:
        """Get all accounts (without passwords in response)"""
        if self.accounts_collection is None:
            return []
        
        try:
            accounts = list(self.accounts_collection.find({}, {"password": 0}))
            return [self._format_account(acc) for acc in accounts]
        except Exception as e:
            print(f"Error getting all accounts: {e}")
            return []
    
    def get_all_accounts_with_credentials(self) -> List[Dict]:
        """Get all accounts WITH passwords and OAuth credentials (for internal monitoring)"""
        if self.accounts_collection is None:
            return []
        
        try:
            # Get all accounts including passwords and OAuth credentials
            accounts = list(self.accounts_collection.find({}))
            return [self._format_account(acc) for acc in accounts]
        except Exception as e:
            print(f"Error getting all accounts with credentials: {e}")
            return []
    
    def get_account_count(self) -> int:
        """Get total number of accounts"""
        if self.accounts_collection is None:
            return 0
        
        try:
            return self.accounts_collection.count_documents({})
        except Exception as e:
            print(f"Error getting account count: {e}")
            return 0
    
    def set_active_account(self, account_id: int, toggle: bool = False) -> Dict:
        """Set an account as active by integer ID
        
        Args:
            account_id: Account ID to activate
            toggle: If True, toggle the account's active status without deactivating others.
                    If False (default), deactivate all others first (original behavior).
        """
        if self.accounts_collection is None:
            return {"error": "MongoDB not available"}
        
        try:
            if not toggle:
                # Original behavior: First, deactivate all accounts
                self.accounts_collection.update_many({}, {"$set": {"is_active": False}})
            
            # Get current status
            account = self.accounts_collection.find_one({"id": account_id})
            if not account:
                return {"error": "Account not found"}
            
            # Toggle or set active
            new_status = not account.get('is_active', False) if toggle else True
            
            # Update the account
            result = self.accounts_collection.update_one(
                {"id": account_id},
                {"$set": {"is_active": new_status}}
            )
            
            if result.modified_count > 0:
                if new_status:
                    self.active_account_id = account_id
                account = self.get_account(account_id)
                if account:
                    status_text = "activated" if new_status else "deactivated"
                    print(f"✓ Account {status_text}: {account['email']}")
                    return {"success": True, "account": account, "is_active": new_status}
                return {"error": "Account not found after update"}
            else:
                return {"error": "Account not found"}
                
        except Exception as e:
            return {"error": str(e)}
    
    def get_active_account(self) -> Optional[Dict]:
        """Get the currently active account"""
        if self.accounts_collection is None:
            return None
        
        try:
            account = self.accounts_collection.find_one({"is_active": True})
            if account:
                return self._format_account(account)
            
            # If no active account, try to get the first one
            account = self.accounts_collection.find_one({})
            if account:
                formatted = self._format_account(account)
                self.set_active_account(account['_id'])
                return formatted
            
            return None
        except Exception as e:
            print(f"Error getting active account: {e}")
            return None
    
    def update_account(self, account_id: int, **kwargs) -> Dict:
        """Update account details by integer ID"""
        if self.accounts_collection is None:
            return {"error": "MongoDB not available"}
        
        try:
            allowed_fields = ['email', 'password', 'imap_server', 'imap_port', 'smtp_server', 'smtp_port', 'auto_reply_enabled', 'custom_prompt']
            updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
            
            if not updates:
                return {"error": "No valid fields to update"}
            
            # Check if account exists first
            existing_account = self.get_account(account_id)
            if not existing_account:
                return {"error": "Account not found"}
            
            result = self.accounts_collection.update_one(
                {"id": account_id},
                {"$set": updates}
            )
            
            # Return success even if modified_count is 0 (value didn't change)
            if result.matched_count > 0:
                return {"success": True, "account": self.get_account(account_id)}
            else:
                return {"error": "Account not found"}
                
        except Exception as e:
            return {"error": str(e)}
    
    def export_accounts(self) -> List[Dict]:
        """Export all accounts (without passwords)"""
        return self.get_all_accounts()
    
    def import_accounts(self, accounts: List[Dict]) -> Dict:
        """Import accounts from list"""
        imported = 0
        errors = []
        
        for account in accounts:
            if 'email' in account and 'password' in account:
                result = self.add_account(
                    email=account['email'],
                    password=account['password'],
                    imap_server=account.get('imap_server', 'imap.gmail.com'),
                    imap_port=account.get('imap_port', 993),
                    smtp_server=account.get('smtp_server', 'smtp.gmail.com'),
                    smtp_port=account.get('smtp_port', 587)
                )
                if 'error' not in result:
                    imported += 1
                else:
                    errors.append(result['error'])
        
        return {
            "imported": imported,
            "errors": errors
        }
    
    def clear_all_accounts(self) -> Dict:
        """Clear all accounts (for testing)"""
        if self.accounts_collection is None:
            return {"error": "MongoDB not available"}
        
        try:
            result = self.accounts_collection.delete_many({})
            self.active_account_id = None
            return {"success": True, "message": f"All accounts cleared ({result.deleted_count} deleted)"}
        except Exception as e:
            return {"error": str(e)}
    
    def find_account_by_email(self, email: str) -> Optional[Dict]:
        """Find account by email (alias for get_account_by_email)"""
        return self.get_account_by_email(email)
    
    def create_account_from_oauth(self, email: str, name: str, credentials_dict: Dict) -> int:
        """Create account from OAuth credentials"""
        if self.accounts_collection is None:
            raise ValueError("MongoDB not available")
        
        try:
            # Check if account already exists
            existing = self.accounts_collection.find_one({"email": email})
            if existing:
                account_id = existing.get('id')
                if not account_id:
                    account_id = self._get_next_id()
                    self.accounts_collection.update_one(
                        {"email": email},
                        {"$set": {"id": account_id}}
                    )
                
                # Update with OAuth credentials
                self.accounts_collection.update_one(
                    {"email": email},
                    {"$set": {
                        "oauth_credentials": credentials_dict,
                        "oauth_name": name,
                        "oauth_enabled": True,
                        "updated_at": datetime.utcnow()
                    }}
                )
                
                # If no active account, make this one active
                if not self.get_active_account():
                    self.set_active_account(account_id)
                
                print(f"✓ OAuth account updated: {email} (ID: {account_id})")
                return account_id
            
            # Create new account
            account_id = self._get_next_id()
            account_doc = {
                "id": account_id,
                "email": email,
                "oauth_credentials": credentials_dict,
                "oauth_name": name,
                "oauth_enabled": True,
                "imap_server": "imap.gmail.com",
                "imap_port": 993,
                "smtp_server": "smtp.gmail.com",
                "smtp_port": 587,
                "is_active": False,
                "created_at": datetime.utcnow()
            }
            
            self.accounts_collection.insert_one(account_doc)
            
            # If this is the first account, make it active
            if self.get_account_count() == 1:
                self.set_active_account(account_id)
            
            print(f"✓ OAuth account created: {email} (ID: {account_id})")
            return account_id
            
        except Exception as e:
            print(f"Error creating OAuth account: {e}")
            raise
    
    def update_account_oauth_credentials(self, account_id: int, credentials_dict: Dict):
        """Update account with OAuth credentials"""
        if self.accounts_collection is None:
            raise ValueError("MongoDB not available")
        
        try:
            self.accounts_collection.update_one(
                {"id": account_id},
                {"$set": {
                    "oauth_credentials": credentials_dict,
                    "oauth_enabled": True,
                    "updated_at": datetime.utcnow()
                }}
            )
            print(f"✓ OAuth credentials updated for account ID: {account_id}")
        except Exception as e:
            print(f"Error updating OAuth credentials: {e}")
            raise
    
    def _format_account(self, account_doc: Dict) -> Dict:
        """Format MongoDB document to match expected format"""
        # Handle account ID - ensure it's an integer
        account_id = account_doc.get('id', 0)
        if account_id is None:
            account_id = 0
        elif isinstance(account_id, str):
            try:
                account_id = int(account_id)
            except (ValueError, TypeError):
                account_id = 0
        elif not isinstance(account_id, int):
            try:
                account_id = int(account_id)
            except (ValueError, TypeError):
                account_id = 0
        
        # Ensure auto_reply_enabled defaults to True for existing accounts
        auto_reply_enabled = account_doc.get('auto_reply_enabled', True)
        
        formatted = {
            "id": account_id,  # Integer ID
            "email": account_doc.get('email', ''),
            "imap_server": account_doc.get('imap_server', 'imap.gmail.com'),
            "imap_port": account_doc.get('imap_port', 993),
            "smtp_server": account_doc.get('smtp_server', 'smtp.gmail.com'),
            "smtp_port": account_doc.get('smtp_port', 587),
            "is_active": bool(account_doc.get('is_active', False)),
            "auto_reply_enabled": bool(auto_reply_enabled),
            "custom_prompt": account_doc.get('custom_prompt', ''),
            "created_at": account_doc.get('created_at', datetime.utcnow())
        }
        
        # Include password if it exists (for internal use)
        if 'password' in account_doc:
            formatted['password'] = account_doc['password']
        
        # Include OAuth credentials if they exist (for Gmail API sending)
        if 'oauth_credentials' in account_doc:
            formatted['oauth_credentials'] = account_doc['oauth_credentials']
        
        return formatted


# Global instance - will be initialized with MongoDB manager in api_server.py
account_manager = None
