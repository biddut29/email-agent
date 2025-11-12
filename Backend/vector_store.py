"""
Vector Store - Semantic search for emails using ChromaDB
"""

import chromadb
from chromadb.config import Settings
from typing import List, Dict, Optional
import hashlib
import json
import os


class EmailVectorStore:
    """Vector database for semantic email search using ChromaDB"""
    
    def __init__(self, persist_directory: str = "chroma_db"):
        """Initialize ChromaDB with persistent storage"""
        try:
            # Get the directory where this file is located
            base_dir = os.path.dirname(os.path.abspath(__file__))
            self.persist_dir = os.path.join(base_dir, persist_directory)
            
            # Ensure the directory exists
            os.makedirs(self.persist_dir, exist_ok=True)
            
            # Initialize ChromaDB client with persistent storage
            self.client = chromadb.PersistentClient(
                path=self.persist_dir,
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            
            # Single collection for all emails with account_id in metadata
            self.collection = self.client.get_or_create_collection(
                name="emails",
                metadata={"description": "Email semantic search with account isolation"}
            )
            
            # Track current account for filtering
            self.current_account_id = None
            
            print(f"✓ Vector Store initialized (ChromaDB persistent: {self.persist_dir})")
            # Skip counting on startup - can be slow with many emails
            # Count will be shown when account is set
        except Exception as e:
            print(f"⚠ Vector Store initialization failed: {e}")
            self.client = None
            self.collection = None
    
    def set_account(self, account_id: int, account_email: str = None, skip_count: bool = False) -> Dict:
        """
        Set the active account for filtering
        
        Args:
            account_id: Account ID to switch to
            account_email: Optional email for logging
            skip_count: If True, skip counting emails (faster startup)
            
        Returns:
            Dict with success status and message
        """
        try:
            self.current_account_id = account_id
            
            # Count emails for this account (skip on startup for speed)
            email_count = 0
            if self.collection and not skip_count:
                try:
                    # Quick count - just get a small sample to check if any exist
                    results = self.collection.get(
                        where={"account_id": str(account_id)},
                        limit=1  # Just check if any exist, don't count all
                    )
                    email_count = len(results['ids']) if results.get('ids') else 0
                    if email_count > 0:
                        email_count = "some"  # Don't do expensive full count
                except:
                    email_count = 0
            
            email_info = f" ({account_email})" if account_email else ""
            if skip_count:
                print(f"✓ Vector Store switched to account {account_id}{email_info}")
            else:
                count_str = f"{email_count} emails indexed" if email_count != "some" else "emails indexed"
                print(f"✓ Vector Store switched to account {account_id}{email_info} - {count_str}")
            
            return {
                "success": True,
                "account_id": account_id,
                "email_count": email_count
            }
        except Exception as e:
            print(f"⚠ Failed to switch account: {e}")
            return {"success": False, "error": str(e)}
    
    def get_current_account_id(self) -> Optional[int]:
        """Get the currently active account ID"""
        return self.current_account_id
    
    def get_account_stats(self) -> Dict:
        """Get statistics for each account in the vector store"""
        try:
            if not self.collection:
                return {"accounts": []}
            
            # Get all emails to count by account
            all_results = self.collection.get(
                include=['metadatas']
            )
            
            # Count emails per account
            account_counts = {}
            if all_results.get('metadatas'):
                for metadata in all_results['metadatas']:
                    account_id = metadata.get('account_id', 'unknown')
                    account_counts[account_id] = account_counts.get(account_id, 0) + 1
            
            accounts = []
            for account_id, count in account_counts.items():
                accounts.append({
                    "account_id": account_id,
                    "email_count": count
                })
            
            return {
                "success": True,
                "total_emails": self.collection.count(),
                "accounts": accounts
            }
        except Exception as e:
            print(f"Error getting account stats: {e}")
            return {"error": str(e), "accounts": []}
    
    def _generate_email_id(self, email_data: Dict) -> str:
        """Generate unique ID for email"""
        # Use message_id if available, otherwise hash content
        if email_data.get('message_id'):
            return hashlib.md5(email_data['message_id'].encode()).hexdigest()
        
        content = f"{email_data.get('from', '')}{email_data.get('subject', '')}{email_data.get('date', '')}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def _prepare_email_text(self, email_data: Dict) -> str:
        """Prepare email text for embedding"""
        parts = []
        
        if email_data.get('subject'):
            parts.append(f"Subject: {email_data['subject']}")
        
        if email_data.get('from'):
            parts.append(f"From: {email_data['from']}")
        
        if email_data.get('to'):
            parts.append(f"To: {email_data['to']}")
        
        # Add body (limit to 1000 chars for efficiency)
        body = email_data.get('text_body', '')
        if body:
            body_preview = body[:1000]
            parts.append(f"Body: {body_preview}")
        
        # Add attachment info and text content
        attachments = email_data.get('attachments', [])
        if attachments:
            attachment_names = [att.get('filename', '') for att in attachments]
            parts.append(f"Attachments: {', '.join(attachment_names)}")
            
            # Include text content from attachments
            for att in attachments:
                if att.get('text_content'):
                    parts.append(f"Attachment Content ({att['filename']}): {att['text_content'][:500]}")
        
        # Add AI analysis if available
        if email_data.get('ai_analysis'):
            analysis = email_data['ai_analysis']
            if analysis.get('category'):
                parts.append(f"Category: {analysis['category']}")
            if analysis.get('summary'):
                parts.append(f"Summary: {analysis['summary']}")
        
        return "\n".join(parts)
    
    def add_emails(self, emails: List[Dict]) -> Dict:
        """
        Add emails to vector store
        
        Args:
            emails: List of email dictionaries
        
        Returns:
            Dict with stats
        """
        if not self.collection:
            return {"error": "Vector store not initialized"}
        
        try:
            ids = []
            documents = []
            metadatas = []
            
            for email in emails:
                email_id = self._generate_email_id(email)
                document = self._prepare_email_text(email)
                
                metadata = {
                    "account_id": str(self.current_account_id) if self.current_account_id else "unknown",
                    "subject": email.get('subject', '')[:200],  # ChromaDB metadata limit
                    "from": email.get('from', '')[:200],
                    "date": email.get('date', '')[:100],
                    "has_attachments": str(email.get('has_attachments', False)),
                }
                
                # Add AI analysis metadata
                if email.get('ai_analysis'):
                    analysis = email['ai_analysis']
                    metadata['category'] = analysis.get('category', 'other')
                    metadata['urgency_score'] = str(analysis.get('urgency_score', 0))
                    metadata['is_spam'] = str(analysis.get('is_spam', False))
                
                ids.append(email_id)
                documents.append(document)
                metadatas.append(metadata)
            
            # Add to collection (ChromaDB handles embeddings automatically)
            self.collection.add(
                ids=ids,
                documents=documents,
                metadatas=metadatas
            )
            
            return {
                "success": True,
                "added": len(ids),
                "total": self.collection.count()
            }
        
        except Exception as e:
            print(f"Error adding emails to vector store: {e}")
            return {"error": str(e)}
    
    def semantic_search(self, query: str, n_results: int = 10, 
                       filter_metadata: Optional[Dict] = None) -> Dict:
        """
        Semantic search for emails
        
        Args:
            query: Search query (natural language)
            n_results: Number of results to return
            filter_metadata: Optional metadata filters (automatically includes current account)
        
        Returns:
            Dict with search results
        """
        if not self.collection:
            return {"error": "Vector store not initialized"}
        
        try:
            # Automatically add account filter
            if filter_metadata is None:
                filter_metadata = {}
            
            # Add current account filter if set
            if self.current_account_id is not None:
                filter_metadata['account_id'] = str(self.current_account_id)
            
            # Query the collection
            results = self.collection.query(
                query_texts=[query],
                n_results=min(n_results, self.collection.count()),
                where=filter_metadata if filter_metadata else None
            )
            
            # Format results
            formatted_results = []
            
            if results['ids'] and results['ids'][0]:
                for i, email_id in enumerate(results['ids'][0]):
                    result = {
                        "id": email_id,
                        "distance": results['distances'][0][i] if results.get('distances') else None,
                        "metadata": results['metadatas'][0][i] if results.get('metadatas') else {},
                        "document": results['documents'][0][i] if results.get('documents') else ""
                    }
                    formatted_results.append(result)
            
            return {
                "success": True,
                "query": query,
                "results": formatted_results,
                "count": len(formatted_results)
            }
        
        except Exception as e:
            print(f"Error in semantic search: {e}")
            return {"error": str(e)}
    
    def find_similar_emails(self, email_data: Dict, n_results: int = 5) -> Dict:
        """
        Find emails similar to a given email
        
        Args:
            email_data: Email to find similar emails for
            n_results: Number of similar emails to return
        
        Returns:
            Dict with similar emails
        """
        if not self.collection:
            return {"error": "Vector store not initialized"}
        
        try:
            # Prepare the email text
            document = self._prepare_email_text(email_data)
            
            # Query for similar emails
            results = self.collection.query(
                query_texts=[document],
                n_results=min(n_results + 1, self.collection.count())  # +1 to exclude itself
            )
            
            # Format and filter out the query email itself
            email_id = self._generate_email_id(email_data)
            formatted_results = []
            
            if results['ids'] and results['ids'][0]:
                for i, result_id in enumerate(results['ids'][0]):
                    if result_id != email_id:  # Exclude the query email
                        result = {
                            "id": result_id,
                            "similarity": 1 - results['distances'][0][i] if results.get('distances') else None,
                            "metadata": results['metadatas'][0][i] if results.get('metadatas') else {},
                        }
                        formatted_results.append(result)
            
            return {
                "success": True,
                "similar_emails": formatted_results[:n_results],
                "count": len(formatted_results[:n_results])
            }
        
        except Exception as e:
            print(f"Error finding similar emails: {e}")
            return {"error": str(e)}
    
    def get_relevant_emails_for_chat(self, query: str, n_results: int = 5) -> List[Dict]:
        """
        Get most relevant emails for chat context
        
        Args:
            query: Chat query
            n_results: Number of emails to return
        
        Returns:
            List of relevant email metadata
        """
        if not self.collection:
            return []
        
        try:
            results = self.semantic_search(query, n_results=n_results)
            
            if results.get('success'):
                return results.get('results', [])
            
            return []
        
        except Exception as e:
            print(f"Error getting relevant emails: {e}")
            return []
    
    def get_stats(self) -> Dict:
        """Get vector store statistics for current account"""
        if not self.collection:
            return {"error": "Vector store not initialized"}
        
        try:
            total_count = self.collection.count()
            
            # If account is set, count only emails for this account
            account_count = total_count
            if self.current_account_id is not None:
                try:
                    results = self.collection.get(
                        where={"account_id": str(self.current_account_id)},
                        limit=10000
                    )
                    account_count = len(results['ids']) if results.get('ids') else 0
                except:
                    account_count = 0
            
            return {
                "success": True,
                "total_emails": account_count,
                "collection_name": self.collection.name,
                "account_id": self.current_account_id
            }
        except Exception as e:
            return {"error": str(e)}
    
    def clear(self) -> Dict:
        """Clear emails from vector store (for current account only if account is set)"""
        if not self.collection:
            return {"error": "Vector store not initialized"}
        
        try:
            # If account is set, only clear emails for that account
            if self.current_account_id is not None:
                # Get all email IDs for this account
                results = self.collection.get(
                    where={"account_id": str(self.current_account_id)},
                    limit=10000
                )
                
                if results.get('ids') and len(results['ids']) > 0:
                    # Delete emails for this account
                    self.collection.delete(ids=results['ids'])
                    message = f"Cleared {len(results['ids'])} emails for account {self.current_account_id}"
                else:
                    message = f"No emails to clear for account {self.current_account_id}"
            else:
                # No account set - clear everything (full reset)
                self.client.delete_collection(name="emails")
                self.collection = self.client.get_or_create_collection(
                    name="emails",
                    metadata={"description": "Email semantic search with account isolation"}
                )
                message = "All emails cleared from vector store"
            
            return {
                "success": True,
                "message": message
            }
        except Exception as e:
            return {"error": str(e)}
    
    def remove_emails(self, email_ids: List[str]) -> Dict:
        """Remove specific emails from vector store"""
        if not self.collection:
            return {"error": "Vector store not initialized"}
        
        try:
            self.collection.delete(ids=email_ids)
            
            return {
                "success": True,
                "removed": len(email_ids)
            }
        except Exception as e:
            return {"error": str(e)}
    
    def clear_account_emails(self, account_id: int) -> Dict:
        """Clear all emails for a specific account from vector store"""
        if not self.collection:
            return {"error": "Vector store not initialized"}
        
        try:
            results = self.collection.get(
                where={"account_id": str(account_id)},
                limit=10000
            )
            
            if results.get('ids') and len(results['ids']) > 0:
                self.collection.delete(ids=results['ids'])
                return {
                    "success": True,
                    "deleted": len(results['ids'])
                }
            else:
                return {
                    "success": True,
                    "deleted": 0
                }
        except Exception as e:
            return {"error": str(e)}


# Global instance
vector_store = EmailVectorStore()

