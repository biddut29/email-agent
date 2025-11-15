"""
Attachment Storage Manager - Hybrid Approach
Structure: /attachments/account_X/msg_Y_filename.ext
"""

import os
import hashlib
from pathlib import Path
from typing import Dict, Optional, List
import shutil


class AttachmentStorage:
    """Manages attachment storage with hybrid flat structure per account"""
    
    def __init__(self, base_dir: str = None):
        if base_dir is None:
            backend_dir = os.path.dirname(os.path.abspath(__file__))
            base_dir = os.path.join(backend_dir, "attachments")
        
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        print(f"✓ Attachment storage initialized: {self.base_dir}")
    
    def _sanitize_filename(self, filename: str) -> str:
        """Remove dangerous characters from filename"""
        safe = filename.replace('/', '_').replace('\\', '_')
        safe = safe.replace('..', '_').replace('\x00', '')
        if len(safe) > 200:  # Leave room for prefix
            name_parts = safe.rsplit('.', 1)
            if len(name_parts) == 2:
                base, ext = name_parts
                safe = base[:195] + '.' + ext
            else:
                safe = safe[:200]
        return safe
    
    def _sanitize_message_id(self, message_id: str) -> str:
        """Sanitize message ID for use in filename"""
        # Replace special characters commonly in message IDs
        safe = message_id.replace('<', '').replace('>', '')
        safe = safe.replace('@', '_at_')
        safe = safe.replace('/', '_').replace('\\', '_')
        # Limit length
        if len(safe) > 50:
            # Use hash if message ID is very long
            safe = hashlib.md5(message_id.encode()).hexdigest()[:16]
        return safe
    
    def _build_filename(self, message_id: str, filename: str) -> str:
        """
        Build filename with message ID prefix
        Format: msg_{message_id}_{filename}
        
        Example: msg_abc123_photo.jpg
        """
        safe_msg_id = self._sanitize_message_id(message_id)
        safe_filename = self._sanitize_filename(filename)
        return f"msg_{safe_msg_id}_{safe_filename}"
    
    def _get_unique_filename(self, directory: Path, filename: str) -> str:
        """
        Ensure filename is unique in directory by adding numeric suffix
        
        Example: msg_abc123_photo.jpg → msg_abc123_photo_1.jpg
        """
        base_path = directory / filename
        
        if not base_path.exists():
            return filename
        
        # File exists, add numeric suffix BEFORE extension
        name_parts = filename.rsplit('.', 1)
        if len(name_parts) == 2:
            base_name, extension = name_parts
        else:
            base_name = filename
            extension = ''
        
        counter = 1
        while counter <= 1000:
            if extension:
                new_filename = f"{base_name}_{counter}.{extension}"
            else:
                new_filename = f"{base_name}_{counter}"
            
            new_path = directory / new_filename
            if not new_path.exists():
                return new_filename
            
            counter += 1
        
        # Safety fallback
        import time
        timestamp = int(time.time() * 1000)
        if extension:
            return f"{base_name}_{timestamp}.{extension}"
        else:
            return f"{base_name}_{timestamp}"
    
    def save_attachment(self, account_id: int, message_id: str, 
                       filename: str, binary_data: bytes) -> Dict:
        """
        Save attachment with format: account_X/msg_Y_filename.ext
        
        Args:
            account_id: Account ID
            message_id: Email message ID
            filename: Original filename from email
            binary_data: File binary data
            
        Returns:
            Dict with success, paths, and metadata
        """
        try:
            # Create account directory (only one level)
            account_dir = self.base_dir / f"account_{account_id}"
            account_dir.mkdir(parents=True, exist_ok=True)
            
            # Build filename with message ID prefix
            prefixed_filename = self._build_filename(message_id, filename)
            
            # Make filename unique within account directory
            unique_filename = self._get_unique_filename(account_dir, prefixed_filename)
            
            # Full path
            file_path = account_dir / unique_filename
            
            # Write file
            with open(file_path, 'wb') as f:
                f.write(binary_data)
            
            # Calculate hash
            file_hash = hashlib.sha256(binary_data).hexdigest()
            
            if unique_filename != prefixed_filename:
                print(f"💾 Saved (renamed): {filename} → {unique_filename}")
            else:
                print(f"💾 Saved: {filename} as {unique_filename}")
            
            return {
                "success": True,
                "original_filename": filename,
                "saved_filename": unique_filename,
                "file_path": str(file_path),
                "relative_path": str(file_path.relative_to(self.base_dir)),
                "size": len(binary_data),
                "hash": file_hash
            }
        
        except Exception as e:
            print(f"❌ Error saving attachment: {e}")
            return {
                "success": False,
                "error": str(e),
                "original_filename": filename
            }
    
    def get_attachment(self, account_id: int, message_id: str, 
                      saved_filename: str) -> Optional[bytes]:
        """
        Retrieve attachment from filesystem
        
        Note: saved_filename should already include the msg_ prefix
        """
        try:
            file_path = self.base_dir / f"account_{account_id}" / saved_filename
            
            if not file_path.exists():
                print(f"⚠️  Attachment not found: {file_path}")
                return None
            
            with open(file_path, 'rb') as f:
                return f.read()
        
        except Exception as e:
            print(f"❌ Error reading attachment: {e}")
            return None
    
    def delete_attachment(self, account_id: int, message_id: str, 
                          saved_filename: str) -> bool:
        """Delete a single attachment"""
        try:
            file_path = self.base_dir / f"account_{account_id}" / saved_filename
            
            if file_path.exists():
                file_path.unlink()
                
                # Clean up empty parent directory
                parent = file_path.parent
                if parent.exists() and not any(parent.iterdir()):
                    parent.rmdir()
                
                print(f"🗑️  Deleted: {saved_filename}")
                return True
            return False
        
        except Exception as e:
            print(f"❌ Error deleting attachment: {e}")
            return False
    
    def delete_email_attachments(self, account_id: int, message_id: str) -> int:
        """
        Delete all attachments for an email by pattern matching
        
        Deletes all files matching: account_{account_id}/msg_{message_id}_*
        """
        try:
            account_dir = self.base_dir / f"account_{account_id}"
            
            if not account_dir.exists():
                return 0
            
            # Pattern to match: msg_{message_id}_*
            safe_msg_id = self._sanitize_message_id(message_id)
            pattern = f"msg_{safe_msg_id}_*"
            
            deleted_count = 0
            for file_path in account_dir.glob(pattern):
                if file_path.is_file():
                    file_path.unlink()
                    deleted_count += 1
            
            if deleted_count > 0:
                print(f"🗑️  Deleted {deleted_count} attachments for message {message_id}")
            
            return deleted_count
        
        except Exception as e:
            print(f"❌ Error deleting email attachments: {e}")
            return 0
    
    def delete_account_attachments(self, account_id: int) -> int:
        """Delete all attachments for an account"""
        try:
            account_dir = self.base_dir / f"account_{account_id}"
            
            if account_dir.exists():
                file_count = sum(1 for f in account_dir.iterdir() if f.is_file())
                shutil.rmtree(account_dir)
                print(f"🗑️  Deleted {file_count} attachment files for account {account_id}")
                return file_count
            return 0
        
        except Exception as e:
            print(f"❌ Error deleting account attachments: {e}")
            return 0
    
    def get_storage_stats(self) -> Dict:
        """Get storage statistics"""
        try:
            total_files = 0
            total_size = 0
            accounts = {}
            
            for account_dir in self.base_dir.iterdir():
                if account_dir.is_dir() and account_dir.name.startswith('account_'):
                    account_id = account_dir.name
                    account_files = 0
                    account_size = 0
                    
                    for file_path in account_dir.iterdir():
                        if file_path.is_file():
                            account_files += 1
                            size = file_path.stat().st_size
                            account_size += size
                            total_files += 1
                            total_size += size
                    
                    accounts[account_id] = {
                        "files": account_files,
                        "size": account_size,
                        "size_mb": round(account_size / 1024 / 1024, 2)
                    }
            
            return {
                "success": True,
                "total_files": total_files,
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / 1024 / 1024, 2),
                "total_size_gb": round(total_size / 1024 / 1024 / 1024, 3),
                "storage_path": str(self.base_dir),
                "accounts": accounts
            }
        
        except Exception as e:
            return {"success": False, "error": str(e)}


# Initialize global instance
attachment_storage = AttachmentStorage()

