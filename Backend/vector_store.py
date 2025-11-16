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
    
    def add_emails(self, emails: List[Dict], account_email: Optional[str] = None) -> Dict:
        """
        Add emails to vector store (ONLY incoming emails, filters out sent emails)
        
        Args:
            emails: List of email dictionaries
            account_email: Account email address to filter out sent emails (emails FROM this address)
        
        Returns:
            Dict with stats
        """
        if not self.collection:
            return {"error": "Vector store not initialized"}
        
        try:
            # Filter out sent emails (emails FROM the account email address)
            incoming_emails = []
            skipped_count = 0
            
            if account_email:
                account_email_lower = account_email.lower()
                for email in emails:
                    from_address = email.get('from', '').lower()
                    # Skip emails that are FROM the account (these are sent emails/auto-replies)
                    # Check if account email appears in the "from" field
                    if account_email_lower in from_address:
                        skipped_count += 1
                        print(f"⏭️  Skipping sent email from vector store: {email.get('subject', 'No subject')[:50]}")
                    else:
                        incoming_emails.append(email)
            else:
                # If no account email provided, store all emails (backward compatibility)
                incoming_emails = emails
            
            if not incoming_emails:
                return {
                    "success": True,
                    "added": 0,
                    "skipped": skipped_count,
                    "total": self.collection.count()
                }
            
            ids = []
            documents = []
            metadatas = []
            
            for email in incoming_emails:
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
            # ChromaDB will skip duplicates (same ID), so we need to check what actually gets added
            try:
                print(f"📤 Adding {len(ids)} emails to vector store (account_id: {self.current_account_id})...")
                self.collection.add(
                    ids=ids,
                    documents=documents,
                    metadatas=metadatas
                )
                
                # Verify how many were actually added (ChromaDB may skip duplicates)
                after_count = self.collection.count()
                print(f"✅ Vector store add completed. Total emails in store: {after_count}")
                
                if skipped_count > 0:
                    print(f"✓ Added {len(ids)} incoming emails to vector store (skipped {skipped_count} sent emails)")
                else:
                    print(f"✓ Added {len(ids)} incoming emails to vector store")
                
                return {
                    "success": True,
                    "added": len(ids),
                    "skipped": skipped_count,
                    "total": after_count
                }
            except Exception as add_error:
                print(f"❌ Error adding emails to ChromaDB: {add_error}")
                import traceback
                traceback.print_exc()
                # Try to add in smaller batches if there's an error
                if len(ids) > 100:
                    print(f"⚠️ Attempting to add in smaller batches...")
                    batch_size = 50
                    added_count = 0
                    for i in range(0, len(ids), batch_size):
                        batch_ids = ids[i:i+batch_size]
                        batch_docs = documents[i:i+batch_size]
                        batch_meta = metadatas[i:i+batch_size]
                        try:
                            self.collection.add(
                                ids=batch_ids,
                                documents=batch_docs,
                                metadatas=batch_meta
                            )
                            added_count += len(batch_ids)
                            print(f"✓ Added batch {i//batch_size + 1}: {len(batch_ids)} emails")
                        except Exception as batch_error:
                            print(f"❌ Error adding batch {i//batch_size + 1}: {batch_error}")
                    
                    return {
                        "success": True,
                        "added": added_count,
                        "skipped": skipped_count,
                        "total": self.collection.count()
                    }
                else:
                    raise
        
        except Exception as e:
            print(f"Error adding emails to vector store: {e}")
            return {"error": str(e)}
    
    def update_account_id(self, old_account_id: str, new_account_id: str, email_ids: List[str]) -> Dict:
        """
        Update account_id for existing emails by deleting and re-adding them.
        This is needed because ChromaDB doesn't support updating metadata for existing embeddings.
        
        Args:
            old_account_id: Current account_id in metadata
            new_account_id: New account_id to set
            email_ids: List of email IDs to update
        
        Returns:
            Dict with success status and count
        """
        if not self.collection or not email_ids:
            return {"success": False, "error": "Collection not initialized or no emails to update"}
        
        try:
            # Get existing emails with their data
            results = self.collection.get(
                ids=email_ids,
                include=['documents', 'metadatas']
            )
            
            if not results.get('ids'):
                return {"success": False, "error": "No emails found with those IDs"}
            
            # Delete old entries
            self.collection.delete(ids=email_ids)
            
            # Update metadata with new account_id
            updated_metadatas = []
            for meta in results.get('metadatas', []):
                updated_meta = meta.copy()
                updated_meta['account_id'] = new_account_id
                updated_metadatas.append(updated_meta)
            
            # Re-add with updated metadata
            self.collection.add(
                ids=results['ids'],
                documents=results['documents'],
                metadatas=updated_metadatas
            )
            
            return {
                "success": True,
                "updated": len(results['ids'])
            }
        except Exception as e:
            print(f"Error updating account_id: {e}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}
    
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
            
            # Security: Always filter by account_id to prevent cross-account data access
            # If current_account_id is not set, this is a security issue
            if self.current_account_id is not None:
                filter_metadata['account_id'] = str(self.current_account_id)
            else:
                # Security: If account_id is not set, return error to prevent data leakage
                print("⚠️ Security: semantic_search called without account_id set - returning empty results")
                return {"success": False, "error": "Account not set", "results": []}
            
            # Query the collection
            results = self.collection.query(
                query_texts=[query],
                n_results=min(n_results, self.collection.count()),
                where=filter_metadata if filter_metadata else None
            )
            
            # Format results and filter by relevance
            formatted_results = []
            
            if results['ids'] and results['ids'][0]:
                for i, email_id in enumerate(results['ids'][0]):
                    distance = results['distances'][0][i] if results.get('distances') else None
                    # ChromaDB uses cosine distance: 0 = identical, 1 = completely different
                    # Convert to similarity score: 1 - distance (higher = more similar)
                    similarity = 1 - distance if distance is not None else 0
                    
                    result = {
                        "id": email_id,
                        "distance": distance,
                        "similarity": similarity,
                        "metadata": results['metadatas'][0][i] if results.get('metadatas') else {},
                        "document": results['documents'][0][i] if results.get('documents') else ""
                    }
                    formatted_results.append(result)
                
                # Sort by similarity (highest first)
                formatted_results.sort(key=lambda x: x.get('similarity', 0), reverse=True)
                
                # Log top results for debugging
                if formatted_results:
                    top_3 = formatted_results[:3]
                    similarity_scores = [f"{r.get('similarity', 0):.3f}" for r in top_3]
                    print(f"📊 Top 3 results - Similarity scores: {similarity_scores}")
            
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
    
    def get_relevant_emails_for_chat(self, query: str, n_results: int = 10) -> List[Dict]:
        """
        Get most relevant emails for chat context with query expansion for better matching
        
        Args:
            query: Chat query
            n_results: Number of emails to return
        
        Returns:
            List of relevant email metadata
        """
        if not self.collection:
            return []
        
        # Security: Ensure account_id is set to prevent cross-account data access
        if self.current_account_id is None:
            print("⚠️ Security: get_relevant_emails_for_chat called without account_id set - returning empty results")
            return []
        
        try:
            # Expand query with synonyms for better matching
            query_variations = [query]
            query_lower = query.lower()
            
            # If query is about "leave", make it more specific
            if 'leave' in query_lower and 'related' in query_lower:
                # Make query more specific for leave-related searches
                query = "leave request vacation time off PTO holiday absence"
                query_variations = [query, "leave request", "vacation request", "time off request", "PTO request", "holiday request"]
                print(f"🔍 Enhanced query for leave search: '{query}'")
            elif 'leave' in query_lower:
                query_variations = [query, "leave request", "vacation", "time off", "PTO", "holiday", "absence", "sick leave"]
            if 'email' in query_lower or 'mail' in query_lower:
                query_variations.extend(['message', 'correspondence'])
            if 'meeting' in query_lower:
                query_variations.extend(['appointment', 'call', 'conference'])
            if 'urgent' in query_lower or 'important' in query_lower:
                query_variations.extend(['priority', 'critical', 'asap'])
            
            # Try original query first
            results = self.semantic_search(query, n_results=n_results)
            found_results = []
            
            if results.get('success') and results.get('results'):
                found_results = results.get('results', [])
                
                # Security: Verify all results belong to the correct account
                expected_account_id = str(self.current_account_id)
                verified_results = []
                for r in found_results:
                    meta = r.get('metadata', {})
                    result_account_id = meta.get('account_id', '')
                    if result_account_id == expected_account_id:
                        verified_results.append(r)
                    else:
                        print(f"⚠️ Security: Filtered out result from wrong account (expected: {expected_account_id}, got: {result_account_id})")
                found_results = verified_results
                print(f"🔍 Vector search for '{query}': Found {len(found_results)} results for account {self.current_account_id}")
                
                # Filter by relevance threshold (similarity > 0.5 means more relevant)
                # ChromaDB cosine distance: 0 = identical, 1 = completely different
                # Similarity = 1 - distance, so similarity > 0.5 means distance < 0.5
                # Also verify emails actually contain relevant keywords
                relevant_results = []
                leave_keywords = ['leave', 'vacation', 'pto', 'holiday', 'absence', 'time off', 'sick leave', 'annual leave', 'personal leave']
                
                for r in found_results:
                    similarity = r.get('similarity', 0)
                    # Higher threshold for better quality (0.5 instead of 0.3)
                    if similarity > 0.5:
                        # If query is about leave, verify email contains leave-related keywords
                        if 'leave' in query_lower:
                            document = r.get('document', '').lower()
                            subject = r.get('metadata', {}).get('subject', '').lower()
                            email_text = f"{subject} {document}"
                            
                            # Check if email contains any leave-related keywords
                            contains_keywords = any(keyword in email_text for keyword in leave_keywords)
                            
                            if contains_keywords:
                                relevant_results.append(r)
                            else:
                                print(f"⚠️ Skipped email (similarity: {similarity:.3f}) - no leave keywords found in subject/body")
                        else:
                            # For non-leave queries, just use similarity threshold
                            relevant_results.append(r)
                
                # If we have good results, return them
                if len(relevant_results) >= 3:
                    print(f"✅ Filtered to {len(relevant_results)} relevant results (similarity > 0.5, keyword verified)")
                    return relevant_results[:n_results]
                
                # If few or no relevant results, try query expansion
                if len(relevant_results) < 3:
                    print(f"⚠️ Only {len(relevant_results)} results above relevance threshold. Trying query expansion...")
                    for expanded_query in query_variations[1:]:  # Skip first (original)
                        if expanded_query.lower() != query.lower():
                            expanded_results = self.semantic_search(expanded_query, n_results=5)
                            if expanded_results.get('success') and expanded_results.get('results'):
                                # Security: Verify expanded results belong to correct account
                                expected_account_id = str(self.current_account_id)
                                verified_expanded = []
                                for r in expanded_results.get('results', []):
                                    meta = r.get('metadata', {})
                                    if meta.get('account_id', '') == expected_account_id:
                                        verified_expanded.append(r)
                                
                                # Merge results, avoiding duplicates, and filter by relevance
                                existing_ids = {r.get('id') for r in relevant_results}
                                for new_result in verified_expanded:
                                    similarity = new_result.get('similarity', 0)
                                    if new_result.get('id') not in existing_ids and similarity > 0.5:
                                        # If query is about leave, verify keywords
                                        if 'leave' in query_lower:
                                            document = new_result.get('document', '').lower()
                                            subject = new_result.get('metadata', {}).get('subject', '').lower()
                                            email_text = f"{subject} {document}"
                                            if any(keyword in email_text for keyword in leave_keywords):
                                                relevant_results.append(new_result)
                                        else:
                                            relevant_results.append(new_result)
                                        if len(relevant_results) >= n_results:
                                            break
                                if len(relevant_results) >= n_results:
                                    break
                    
                    if relevant_results:
                        print(f"✅ After query expansion: Found {len(relevant_results)} relevant results")
                        return relevant_results[:n_results]
                
                # If still no good results, return top 3 anyway (might still be useful)
                if found_results:
                    # Final security check: ensure all results belong to correct account
                    expected_account_id = str(self.current_account_id)
                    final_verified = [r for r in found_results[:3] if r.get('metadata', {}).get('account_id', '') == expected_account_id]
                    if final_verified:
                        low_relevance_scores = [f"{r.get('similarity', 0):.3f}" for r in final_verified]
                        print(f"📋 Returning top {len(final_verified)} results anyway (low relevance): {low_relevance_scores}")
                        return final_verified
            else:
                print(f"⚠️ Vector search for '{query}': No results found")
            
            return []
        
        except Exception as e:
            print(f"❌ Error getting relevant emails: {e}")
            import traceback
            traceback.print_exc()
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
        """Clear all emails for a specific account from vector store (handles large datasets with batching)"""
        if not self.collection:
            return {"error": "Vector store not initialized"}
        
        try:
            total_deleted = 0
            batch_size = 10000  # Process in batches to handle large datasets
            
            # Keep deleting in batches until no more emails are found
            while True:
                results = self.collection.get(
                    where={"account_id": str(account_id)},
                    limit=batch_size
                )
                
                if not results.get('ids') or len(results['ids']) == 0:
                    break
                
                # Delete this batch
                self.collection.delete(ids=results['ids'])
                batch_count = len(results['ids'])
                total_deleted += batch_count
                
                # If we got fewer than batch_size, we're done
                if batch_count < batch_size:
                    break
            
            return {
                "success": True,
                "deleted": total_deleted
            }
        except Exception as e:
            return {"error": str(e)}
    
    def remove_sent_emails(self, account_email: str, account_id: Optional[int] = None) -> Dict:
        """
        Remove sent emails (emails FROM the account email) from vector store
        
        Args:
            account_email: Account email address to identify sent emails
            account_id: Optional account ID to filter by (if None, uses current_account_id)
        
        Returns:
            Dict with removal stats
        """
        if not self.collection:
            return {"error": "Vector store not initialized"}
        
        try:
            # Use provided account_id or current_account_id
            filter_account_id = str(account_id) if account_id is not None else str(self.current_account_id) if self.current_account_id else None
            
            # Get all emails for this account
            if filter_account_id:
                results = self.collection.get(
                    where={"account_id": filter_account_id},
                    limit=10000,
                    include=['metadatas']
                )
            else:
                # If no account_id, get all emails (less efficient but works)
                results = self.collection.get(
                    limit=10000,
                    include=['metadatas']
                )
            
            if not results.get('ids'):
                return {
                    "success": True,
                    "deleted": 0,
                    "message": "No emails found in vector store"
                }
            
            account_email_lower = account_email.lower()
            sent_email_ids = []
            
            # Check each email's metadata to find sent emails
            for i, email_id in enumerate(results['ids']):
                metadata = results['metadatas'][i] if results.get('metadatas') and i < len(results['metadatas']) else {}
                from_address = metadata.get('from', '').lower()
                
                # If the "from" field contains the account email, it's a sent email
                if account_email_lower in from_address:
                    sent_email_ids.append(email_id)
            
            # Delete sent emails
            if sent_email_ids:
                self.collection.delete(ids=sent_email_ids)
                return {
                    "success": True,
                    "deleted": len(sent_email_ids),
                    "message": f"Removed {len(sent_email_ids)} sent email(s) from vector store"
                }
            else:
                return {
                    "success": True,
                    "deleted": 0,
                    "message": "No sent emails found in vector store"
                }
        
        except Exception as e:
            print(f"Error removing sent emails from vector store: {e}")
            return {"error": str(e)}


# Global instance
vector_store = EmailVectorStore()

