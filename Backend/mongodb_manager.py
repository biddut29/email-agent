"""
MongoDB Manager - Persistent email storage with account isolation
"""

from pymongo import MongoClient, ASCENDING, DESCENDING
from typing import List, Dict, Optional
from datetime import datetime
from email.utils import parsedate_to_datetime
import os


class MongoDBManager:
    """Manages email storage in MongoDB with account isolation"""
    
    def __init__(self, connection_string: str = None, db_name: str = "email_agent"):
        """
        Initialize MongoDB connection
        
        Args:
            connection_string: MongoDB connection string (default: mongodb://localhost:27017/)
            db_name: Database name to use
        """
        try:
            # Use provided connection string or default to localhost
            if connection_string is None:
                connection_string = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
            
            self.client = MongoClient(connection_string, serverSelectionTimeoutMS=5000)
            
            # Test connection
            self.client.admin.command('ping')
            
            self.db = self.client[db_name]
            self.emails_collection = self.db['emails']
            self.ai_analysis_collection = self.db['ai_analysis']
            self.replies_collection = self.db['replies']
            
            # Create indexes for better query performance
            self._create_indexes()
            
            print(f"✓ MongoDB connected: {db_name}")
            print(f"  Total emails in database: {self.emails_collection.count_documents({})}")
            
        except Exception as e:
            print(f"⚠ MongoDB connection failed: {e}")
            print("  Using fallback mode (emails won't persist)")
            self.client = None
            self.db = None
            self.emails_collection = None
            self.ai_analysis_collection = None
            self.replies_collection = None
    
    def _create_indexes(self):
        """Create database indexes for performance"""
        try:
            # Email collection indexes
            if self.emails_collection is not None:
                # Compound index for account_id + date_str (most common query pattern)
                # This speeds up: find({account_id: X}).sort({date_str: -1})
                self.emails_collection.create_index([
                    ("account_id", ASCENDING),
                    ("date_str", DESCENDING)
                ], background=True, name="idx_account_date")
                
                # Index for message_id lookups
                self.emails_collection.create_index("message_id", background=True, name="idx_message_id")
                
                # Index for account_id alone (for stats queries)
                self.emails_collection.create_index("account_id", background=True, name="idx_account_id")
                
                # Index for date_str (for date range queries)
                self.emails_collection.create_index("date_str", background=True, name="idx_date_str")
                
                print("✓ Email collection indexes created")
            
            # AI Analysis collection indexes
            if self.ai_analysis_collection is not None:
                # Compound index for account_id + email_message_id (most common lookup)
                self.ai_analysis_collection.create_index([
                    ("account_id", ASCENDING),
                    ("email_message_id", ASCENDING)
                ], background=True, name="idx_ai_account_message")
                
                # Index for category filtering
                self.ai_analysis_collection.create_index("category", background=True, name="idx_category")
                
                # Index for urgency score filtering
                self.ai_analysis_collection.create_index("urgency_score", background=True, name="idx_urgency")
                
                print("✓ AI Analysis collection indexes created")
            
            # Replies collection indexes
            if self.replies_collection is not None:
                # Compound index for account_id + email_message_id (most common lookup)
                self.replies_collection.create_index([
                    ("account_id", ASCENDING),
                    ("email_message_id", ASCENDING)
                ], background=True, name="idx_reply_account_message")
                
                # Index for sent_at timestamp
                self.replies_collection.create_index("sent_at", DESCENDING, background=True, name="idx_reply_sent_at")
                
                print("✓ Replies collection indexes created")
            
        except Exception as e:
            print(f"⚠ Failed to create indexes: {e}")
            import traceback
            traceback.print_exc()
    
    def save_emails(self, emails: List[Dict], account_id: int) -> Dict:
        """
        Save emails to MongoDB
        
        Args:
            emails: List of email dictionaries
            account_id: Account ID these emails belong to
            
        Returns:
            Dict with stats
        """
        if self.emails_collection is None:
            return {"error": "MongoDB not connected"}
        
        try:
            inserted_count = 0
            updated_count = 0
            
            for email in emails:
                # Add metadata
                email['account_id'] = account_id
                email['saved_at'] = datetime.utcnow()
                
                # Create sortable date string from email date
                # Convert email date to ISO format for proper sorting
                if 'date' in email and not 'date_str' in email:
                    try:
                        # Parse email date and convert to ISO format (YYYY-MM-DD HH:MM:SS)
                        email_date = parsedate_to_datetime(email['date'])
                        email['date_str'] = email_date.strftime('%Y-%m-%d %H:%M:%S')
                    except:
                        # Fallback: use saved_at time
                        email['date_str'] = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                
                # Use message_id as unique identifier
                message_id = email.get('message_id')
                
                if message_id:
                    # Update if exists, insert if not (upsert)
                    result = self.emails_collection.update_one(
                        {
                            'message_id': message_id,
                            'account_id': account_id
                        },
                        {'$set': email},
                        upsert=True
                    )
                    
                    if result.upserted_id:
                        inserted_count += 1
                    elif result.modified_count > 0:
                        updated_count += 1
                else:
                    # No message_id, just insert
                    self.emails_collection.insert_one(email)
                    inserted_count += 1
            
            return {
                "success": True,
                "inserted": inserted_count,
                "updated": updated_count,
                "total": inserted_count + updated_count
            }
        
        except Exception as e:
            print(f"Error saving emails to MongoDB: {e}")
            return {"error": str(e)}
    
    def save_ai_analysis(self, email_message_id: str, account_id: int, 
                         ai_analysis: Dict) -> Dict:
        """
        Save AI analysis results to MongoDB
        
        Args:
            email_message_id: The message_id of the email
            account_id: Account ID the email belongs to
            ai_analysis: Dict containing AI analysis results
            
        Returns:
            Dict with success status
        """
        if self.ai_analysis_collection is None:
            return {"error": "MongoDB not connected"}
        
        try:
            # Prepare analysis document
            analysis_doc = {
                "email_message_id": email_message_id,
                "account_id": account_id,
                "analyzed_at": datetime.utcnow(),
                "category": ai_analysis.get('category', 'other'),
                "urgency_score": ai_analysis.get('urgency_score', 0),
                "is_spam": ai_analysis.get('is_spam', False),
                "summary": ai_analysis.get('summary', ''),
                "sentiment": ai_analysis.get('sentiment', ''),
                "tags": ai_analysis.get('tags', []),
                "key_points": ai_analysis.get('key_points', []),
                "action_required": ai_analysis.get('action_required', False),
                "suggested_response": ai_analysis.get('suggested_response', ''),
                "full_analysis": ai_analysis  # Store complete analysis
            }
            
            # Upsert - update if exists, insert if not
            result = self.ai_analysis_collection.update_one(
                {
                    "email_message_id": email_message_id,
                    "account_id": account_id
                },
                {"$set": analysis_doc},
                upsert=True
            )
            
            # Also update the email document with a reference to analysis
            if self.emails_collection is not None:
                self.emails_collection.update_one(
                    {
                        "message_id": email_message_id,
                        "account_id": account_id
                    },
                    {
                        "$set": {
                            "has_ai_analysis": True,
                            "ai_analyzed_at": datetime.utcnow()
                        }
                    }
                )
            
            return {
                "success": True,
                "upserted": result.upserted_id is not None,
                "modified": result.modified_count > 0
            }
        
        except Exception as e:
            print(f"Error saving AI analysis to MongoDB: {e}")
            return {"error": str(e)}
    
    def get_ai_analysis(self, email_message_id: str, account_id: int) -> Optional[Dict]:
        """
        Get AI analysis for a specific email (optimized with index hint)
        
        Args:
            email_message_id: The message_id of the email
            account_id: Account ID
            
        Returns:
            AI analysis dict or None
        """
        if self.ai_analysis_collection is None:
            return None
        
        try:
            # Use index hint for faster lookup
            query = {
                "email_message_id": email_message_id,
                "account_id": account_id
            }
            
            # find_one() is optimized for single document queries
            # MongoDB will automatically use the compound index if it exists
            # Projection ensures we only fetch what we need (exclude _id)
            analysis = self.ai_analysis_collection.find_one(
                query,
                {"_id": 0}  # Exclude MongoDB _id field
            )
            
            # If not found, return None immediately (don't retry)
            if not analysis:
                return None
            
            return analysis
        except Exception as e:
            print(f"Error retrieving AI analysis: {e}")
            return None
    
    def get_analysis_stats(self, account_id: int) -> Dict:
        """
        Get AI analysis statistics
        
        Args:
            account_id: Account ID
            
        Returns:
            Dict with statistics
        """
        if self.ai_analysis_collection is None:
            return {"error": "MongoDB not connected"}
        
        try:
            # Optimized: Single aggregation pipeline for all stats (much faster than multiple queries)
            pipeline = [
                {"$match": {"account_id": account_id}},
                {
                    "$facet": {
                        "total": [{"$count": "count"}],
                        "by_category": [
                            {"$group": {"_id": "$category", "count": {"$sum": 1}}}
                        ],
                        "spam": [
                            {"$match": {"is_spam": True}},
                            {"$count": "count"}
                        ],
                        "urgent": [
                            {"$match": {"urgency_score": {"$gte": 7}}},
                            {"$count": "count"}
                        ]
                    }
                }
            ]
            
            result = list(self.ai_analysis_collection.aggregate(pipeline))
            if not result:
                return {
                    "success": True,
                    "total_analyzed": 0,
                    "by_category": {},
                    "spam_count": 0,
                    "urgent_count": 0
                }
            
            facet_data = result[0].get('$facet', {})
            
            total = facet_data.get('total', [{}])[0].get('count', 0) if facet_data.get('total') else 0
            by_category = {item['_id']: item['count'] for item in facet_data.get('by_category', [])}
            spam_count = facet_data.get('spam', [{}])[0].get('count', 0) if facet_data.get('spam') else 0
            urgent_count = facet_data.get('urgent', [{}])[0].get('count', 0) if facet_data.get('urgent') else 0
            
            return {
                "success": True,
                "total_analyzed": total,
                "by_category": by_category,
                "spam_count": spam_count,
                "urgent_count": urgent_count
            }
        
        except Exception as e:
            print(f"Error getting analysis stats: {e}")
            return {"error": str(e)}
    
    def get_emails(self, account_id: int, limit: int = 100, 
                   date_from: str = None, date_to: str = None,
                   unread_only: bool = False, skip: int = 0, 
                   exclude_bodies: bool = False) -> List[Dict]:
        """
        Retrieve emails from MongoDB
        
        Args:
            account_id: Account ID to filter by
            limit: Maximum number of emails to return
            date_from: Start date (YYYY-MM-DD format)
            date_to: End date (YYYY-MM-DD format)
            unread_only: Only return unread emails
            skip: Number of emails to skip (for pagination)
            
        Returns:
            List of email dictionaries
        """
        if self.emails_collection is None:
            return []
        
        try:
            # Build query
            query = {"account_id": account_id}
            
            # Add date filters if provided
            if date_from or date_to:
                date_query = {}
                if date_from:
                    date_query['$gte'] = date_from
                if date_to:
                    date_query['$lte'] = date_to
                
                if date_query:
                    query['date_str'] = date_query
            
            # Add unread filter
            if unread_only:
                query['is_read'] = False
            
            # Build projection to exclude large fields for list views (much faster)
            projection = {'_id': 0}  # Always exclude MongoDB _id
            if exclude_bodies:
                # For list view, exclude large HTML/text bodies to speed up loading
                projection['html_body'] = 0
                projection['text_body'] = 0
            
            # Query with sorting (newest first) and pagination
            # Optimized query with index hint for faster performance
            cursor = self.emails_collection.find(query, projection).sort('date_str', DESCENDING)
            
            # Try to use index hint for better performance (if index exists)
            try:
                cursor = cursor.hint([('account_id', ASCENDING), ('date_str', DESCENDING)])
            except:
                # Index might not exist yet, continue without hint
                pass
            
            emails = list(cursor.skip(skip).limit(limit))
            
            return emails
        
        except Exception as e:
            print(f"Error retrieving emails from MongoDB: {e}")
            return []
    
    def get_emails_for_vector(self, account_id: int, limit: int = 1000) -> List[Dict]:
        """
        Get emails for vector indexing (optimized query)
        
        Args:
            account_id: Account ID to filter by
            limit: Maximum number of emails
            
        Returns:
            List of email dictionaries
        """
        if self.emails_collection is None:
            return []
        
        try:
            # Get emails sorted by date (newest first)
            emails = list(
                self.emails_collection
                .find(
                    {"account_id": account_id},
                    {'_id': 0, 'saved_at': 0}  # Exclude internal fields
                )
                .sort('date_str', DESCENDING)
                .limit(limit)
            )
            
            return emails
        
        except Exception as e:
            print(f"Error retrieving emails for vector: {e}")
            return []
    
    def get_stats(self, account_id: int = None) -> Dict:
        """
        Get statistics about stored emails
        
        Args:
            account_id: If provided, stats for specific account. Otherwise, all accounts.
            
        Returns:
            Dict with statistics
        """
        if self.emails_collection is None:
            return {"error": "MongoDB not connected"}
        
        try:
            if account_id is not None:
                # Stats for specific account - optimized queries
                count = self.emails_collection.count_documents({"account_id": account_id})
                
                # Get date range using optimized queries with index hints
                try:
                    oldest = self.emails_collection.find_one(
                        {"account_id": account_id},
                        sort=[("date_str", ASCENDING)],
                        projection={"date_str": 1, "date": 1}  # Only fetch date fields
                    )
                    newest = self.emails_collection.find_one(
                        {"account_id": account_id},
                        sort=[("date_str", DESCENDING)],
                        projection={"date_str": 1, "date": 1}  # Only fetch date fields
                    )
                except:
                    # Fallback if projection fails
                    oldest = self.emails_collection.find_one(
                        {"account_id": account_id},
                        sort=[("date_str", ASCENDING)],
                        projection={"date_str": 1}
                    )
                    newest = self.emails_collection.find_one(
                        {"account_id": account_id},
                        sort=[("date_str", DESCENDING)],
                        projection={"date_str": 1}
                    )
                
                return {
                    "account_id": account_id,
                    "total_emails": count,
                    "oldest_email": oldest.get('date_str') if oldest else None,
                    "newest_email": newest.get('date_str') if newest else None
                }
            else:
                # Stats for all accounts
                total = self.emails_collection.count_documents({})
                
                # Count by account
                pipeline = [
                    {"$group": {
                        "_id": "$account_id",
                        "count": {"$sum": 1}
                    }}
                ]
                by_account = list(self.emails_collection.aggregate(pipeline))
                
                return {
                    "total_emails": total,
                    "by_account": [
                        {"account_id": item['_id'], "count": item['count']}
                        for item in by_account
                    ]
                }
        
        except Exception as e:
            return {"error": str(e)}
    
    def clear_account_emails(self, account_id: int) -> Dict:
        """
        Clear all emails for a specific account
        
        Args:
            account_id: Account ID to clear
            
        Returns:
            Dict with result
        """
        if self.emails_collection is None:
            return {"error": "MongoDB not connected"}
        
        try:
            result = self.emails_collection.delete_many({"account_id": account_id})
            
            return {
                "success": True,
                "deleted": result.deleted_count
            }
        
        except Exception as e:
            return {"error": str(e)}
    
    def save_reply(self, email_message_id: str, account_id: int, reply_data: Dict) -> Dict:
        """
        Save a sent reply to MongoDB
        
        Args:
            email_message_id: Original email's message ID
            account_id: Account ID that sent the reply
            reply_data: Reply information (to, subject, body)
            
        Returns:
            Dict with result
        """
        if self.replies_collection is None:
            return {"error": "MongoDB not connected"}
        
        try:
            reply_doc = {
                "email_message_id": email_message_id,
                "account_id": account_id,
                "to": reply_data.get('to', ''),
                "subject": reply_data.get('subject', ''),
                "body": reply_data.get('body', ''),
                "sent_at": datetime.utcnow(),
                "success": reply_data.get('success', False)
            }
            
            # Upsert (insert or update)
            result = self.replies_collection.update_one(
                {
                    "email_message_id": email_message_id,
                    "account_id": account_id
                },
                {"$set": reply_doc},
                upsert=True
            )
            
            return {
                "success": True,
                "upserted": result.upserted_id is not None,
                "modified": result.modified_count > 0
            }
        
        except Exception as e:
            return {"error": str(e)}
    
    def get_reply(self, email_message_id: str, account_id: int) -> Optional[Dict]:
        """
        Get reply for a specific email
        
        Args:
            email_message_id: Email message ID
            account_id: Account ID
            
        Returns:
            Reply data or None
        """
        if self.replies_collection is None:
            return None
        
        try:
            # find_one() is optimized for single document queries
            # MongoDB will automatically use the compound index if it exists
            reply = self.replies_collection.find_one(
                {
                    "email_message_id": email_message_id,
                    "account_id": account_id
                },
                {"_id": 0}  # Exclude MongoDB _id field
            )
            
            if reply:
                # Convert datetime to ISO format
                if 'sent_at' in reply and isinstance(reply['sent_at'], datetime):
                    reply['sent_at'] = reply['sent_at'].isoformat()
                return reply
            return None
        
        except Exception as e:
            print(f"Error retrieving reply: {e}")
            return None
    
    def close(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()
            print("✓ MongoDB connection closed")


# Global instance
mongodb_manager = MongoDBManager()

