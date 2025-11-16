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
            
            self.client = MongoClient(connection_string, serverSelectionTimeoutMS=2000)  # Reduced from 5000ms to 2000ms
            
            # Test connection
            self.client.admin.command('ping')
            
            self.db = self.client[db_name]
            self.emails_collection = self.db['emails']
            self.ai_analysis_collection = self.db['ai_analysis']
            self.replies_collection = self.db['replies']
            
            # Create indexes for better query performance (async, don't block startup)
            # Run in background to avoid blocking startup
            import threading
            def create_indexes_async():
                try:
                    self._create_indexes()
                except Exception as e:
                    # Index creation errors are non-critical, just log
                    pass
            
            thread = threading.Thread(target=create_indexes_async, daemon=True)
            thread.start()
            
            print(f"✓ MongoDB connected: {db_name}")
            # Skip counting all documents on startup (can be very slow with many emails)
            # Use estimated_document_count() for faster startup, or skip entirely
            try:
                # Use estimated count which is much faster (uses collection metadata)
                estimated_count = self.emails_collection.estimated_document_count()
                if estimated_count > 0:
                    print(f"  Estimated emails in database: ~{estimated_count}")
            except:
                # If estimated count fails, just skip it - not critical for startup
                pass
            
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
        Save emails to MongoDB using bulk operations for better performance
        If emails have attachments with binary_data, save to filesystem first
        
        Args:
            emails: List of email dictionaries
            account_id: Account ID these emails belong to
            
        Returns:
            Dict with stats
        """
        if self.emails_collection is None:
            return {"error": "MongoDB not connected"}
        
        try:
            if not emails:
                return {"success": True, "inserted": 0, "updated": 0, "total": 0}
            
            from pymongo import UpdateOne
            from attachment_storage import attachment_storage
            
            # Prepare bulk operations
            bulk_ops = []
            now = datetime.utcnow()
            
            for email in emails:
                # Process attachments if present
                if email.get('attachments'):
                    processed_attachments = []
                    
                    for att in email['attachments']:
                        # If attachment has binary_data, save to filesystem
                        if 'binary_data' in att:
                            result = attachment_storage.save_attachment(
                                account_id=account_id,
                                message_id=email.get('message_id'),
                                filename=att.get('filename', 'attachment'),
                                binary_data=att['binary_data']
                            )
                            
                            if result['success']:
                                # Store metadata (not binary data)
                                processed_att = {
                                    "original_filename": result['original_filename'],
                                    "saved_filename": result['saved_filename'],
                                    "content_type": att.get('content_type', 'application/octet-stream'),
                                    "size": result['size'],
                                    "file_path": result['relative_path'],
                                    "hash": result['hash'],
                                    "storage": "filesystem"
                                }
                                # Preserve text_content if it was extracted (OCR/PDF text)
                                if att.get('text_content'):
                                    processed_att['text_content'] = att['text_content']
                                
                                processed_attachments.append(processed_att)
                            else:
                                print(f"Failed to save attachment: {att.get('filename')}")
                            
                            # Remove binary_data from email doc
                            del att['binary_data']
                        else:
                            # Attachment already processed or only metadata
                            processed_attachments.append(att)
                    
                    # Replace attachments with processed version
                    email['attachments'] = processed_attachments
                    email['has_attachments'] = len(processed_attachments) > 0
                
                # Add metadata
                email['account_id'] = account_id
                email['saved_at'] = now
                
                # Always recalculate date_str from date to ensure it's correct and sortable
                # This fixes existing emails with incorrect date_str and ensures consistency
                if 'date' in email:
                    try:
                        email_date = parsedate_to_datetime(email['date'])
                        email['date_str'] = email_date.strftime('%Y-%m-%d %H:%M:%S')
                    except:
                        # If date parsing fails, use current time as fallback
                        email['date_str'] = now.strftime('%Y-%m-%d %H:%M:%S')
                
                # Use message_id as unique identifier
                message_id = email.get('message_id')
                
                if message_id:
                    # Use bulk upsert operation
                    bulk_ops.append(
                        UpdateOne(
                            {
                                'message_id': message_id,
                                'account_id': account_id
                            },
                            {'$set': email},
                            upsert=True
                        )
                    )
                else:
                    # No message_id, use insert operation
                    # Create a temporary unique identifier
                    temp_id = f"{account_id}_{now.timestamp()}_{len(bulk_ops)}"
                    bulk_ops.append(
                        UpdateOne(
                            {'_temp_id': temp_id},
                            {'$setOnInsert': {**email, '_temp_id': temp_id}},
                            upsert=True
                        )
                    )
            
            # Execute bulk operation (much faster than individual operations)
            if bulk_ops:
                result = self.emails_collection.bulk_write(bulk_ops, ordered=False)
                inserted_count = result.upserted_count
                updated_count = result.modified_count
                
                return {
                    "success": True,
                    "inserted": inserted_count,
                    "updated": updated_count,
                    "total": inserted_count + updated_count
                }
            else:
                return {"success": True, "inserted": 0, "updated": 0, "total": 0}
        
        except Exception as e:
            print(f"Error saving emails to MongoDB: {e}")
            import traceback
            traceback.print_exc()
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
                # Use string comparison with date bounds (works reliably with date_str format)
                date_query = {}
                if date_from:
                    # Match from start of day
                    date_from_start = f"{date_from} 00:00:00"
                    date_query['$gte'] = date_from_start
                if date_to:
                    # Match until end of day (use < next day to include all of end date)
                    from datetime import datetime, timedelta
                    date_obj = datetime.strptime(date_to, "%Y-%m-%d")
                    next_day = date_obj + timedelta(days=1)
                    date_to_end = next_day.strftime("%Y-%m-%d 00:00:00")
                    date_query['$lt'] = date_to_end  # Use $lt (less than) to exclude next day
                
                # Special handling for "today" (when date_from == date_to)
                # Use regex to match date prefix - this handles timezone variations better
                if date_from and date_to and date_from == date_to:
                    # For same-day queries, use regex to match any time on that date
                    # This is more reliable than time-based comparison due to timezone issues
                    date_prefix = date_from  # e.g., "2025-11-15"
                    # MongoDB regex: match date_str that starts with the date prefix
                    # Escape special regex characters in the date prefix
                    import re as re_module
                    escaped_prefix = re_module.escape(date_prefix)
                    date_query = {'$regex': f'^{escaped_prefix}'}
                    print(f"🔍 Today filter: Using regex for date prefix '{date_prefix}' (matches any time on this date)")
                    
                    # Debug: Check a sample email to see date_str format
                    sample = self.emails_collection.find_one(
                        {"account_id": account_id},
                        {"date_str": 1, "subject": 1, "date": 1}
                    )
                    if sample:
                        print(f"🔍 Sample email date_str: '{sample.get('date_str')}', date: '{sample.get('date')}'")
                        # Test if regex would match
                        import re
                        date_str = sample.get('date_str', '')
                        if date_str:
                            matches = bool(re.match(f'^{date_prefix}', date_str))
                            print(f"🔍 Regex test: '{date_prefix}' matches '{date_str}'? {matches}")
                
                if date_query:
                    query['date_str'] = date_query
                    print(f"🔍 MongoDB date filter: {date_query}, account_id={account_id}")
            
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
            print(f"🔍 Executing MongoDB query: {query}")
            cursor = self.emails_collection.find(query, projection).sort('date_str', DESCENDING)
            
            # Try to use index hint for better performance (if index exists)
            try:
                cursor = cursor.hint([('account_id', ASCENDING), ('date_str', DESCENDING)])
            except:
                # Index might not exist yet, continue without hint
                pass
            
            # Test query before skip/limit to see total matches
            test_count = self.emails_collection.count_documents(query)
            print(f"🔍 Query matches {test_count} emails (before skip/limit)")
            
            # Special debug for "today" queries
            if date_from and date_to and date_from == date_to:
                # Get all unique date_str values for this account to see what dates exist
                all_dates = self.emails_collection.distinct("date_str", {"account_id": account_id})
                if all_dates:
                    # Extract just the date part (YYYY-MM-DD) from date_str values
                    unique_dates = set()
                    for dt in all_dates[:20]:  # Check first 20
                        if dt and isinstance(dt, str) and len(dt) >= 10:
                            unique_dates.add(dt[:10])  # Get YYYY-MM-DD part
                    print(f"🔍 Available dates in DB (first 20): {sorted(list(unique_dates))}")
                    print(f"🔍 Looking for date: '{date_from}'")
                    if date_from in unique_dates:
                        print(f"✅ Date '{date_from}' EXISTS in database!")
                    else:
                        print(f"❌ Date '{date_from}' NOT FOUND in database. Available dates: {sorted(list(unique_dates))}")
            
            emails = list(cursor.skip(skip).limit(limit))
            print(f"🔍 Query returned {len(emails)} emails (after skip={skip}, limit={limit})")
            
            # Debug: Print sample date_str values if emails found
            if emails and (date_from or date_to):
                sample_dates = [e.get('date_str', 'N/A') for e in emails[:3]]
                print(f"✅ Found {len(emails)} emails with date filter. Sample date_str values: {sample_dates}")
            elif not emails and (date_from or date_to):
                # Check if there are any emails without date filter to debug
                test_query = {"account_id": account_id}
                test_cursor = self.emails_collection.find(test_query, {'date_str': 1, 'subject': 1, 'date': 1}).limit(10).sort('date_str', DESCENDING)
                test_emails = list(test_cursor)
                if test_emails:
                    sample_dates = [e.get('date_str', 'N/A') for e in test_emails]
                    sample_subjects = [e.get('subject', 'N/A')[:30] for e in test_emails]
                    total_count = self.emails_collection.count_documents(test_query)
                    print(f"❌ No emails found with date filter!")
                    print(f"   Total emails in DB for account {account_id}: {total_count}")
                    print(f"   Date filter: from={date_from}, to={date_to}")
                    print(f"   Query used: {query}")
                    print(f"   Latest 10 emails in DB (date_str): {sample_dates}")
                    print(f"   Latest 10 subjects: {sample_subjects}")
                    
                    # Test the query manually to see what's wrong
                    test_result = list(self.emails_collection.find(query, {'date_str': 1, 'subject': 1}).limit(5))
                    print(f"   Query result count: {len(test_result)}")
                    if test_result:
                        print(f"   Query result dates: {[e.get('date_str') for e in test_result]}")
                else:
                    print(f"❌ No emails found in MongoDB for account_id={account_id}")
            
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
        Get reply for a specific email (checks both actual and synthetic message_id formats)
        
        Args:
            email_message_id: Email message ID (can be actual Message-ID or synthetic)
            account_id: Account ID
            
        Returns:
            Reply data or None
        """
        if self.replies_collection is None:
            return None
        
        try:
            # First try with the provided message_id
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
            
            # If not found, try to find the email and check with alternate message_id format
            if self.emails_collection is not None:
                email_doc = self.emails_collection.find_one({
                    "$or": [
                        {"message_id": email_message_id, "account_id": account_id},
                        {"gmail_synthetic_id": email_message_id, "account_id": account_id}
                    ]
                }, {'gmail_synthetic_id': 1, 'message_id': 1})
                
                if email_doc:
                    # Get the alternate message_id format
                    synthetic_id = email_doc.get('gmail_synthetic_id')
                    actual_id = email_doc.get('message_id')
                    
                    # Try the alternate format
                    alternate_id = None
                    if email_message_id == synthetic_id and actual_id:
                        alternate_id = actual_id
                    elif email_message_id == actual_id and synthetic_id:
                        alternate_id = synthetic_id
                    
                    if alternate_id:
                        reply = self.replies_collection.find_one(
                            {
                                "email_message_id": alternate_id,
                                "account_id": account_id
                            },
                            {"_id": 0}
                        )
                        
                        if reply:
                            if 'sent_at' in reply and isinstance(reply['sent_at'], datetime):
                                reply['sent_at'] = reply['sent_at'].isoformat()
                            return reply
            
            return None
        
        except Exception as e:
            print(f"Error retrieving reply: {e}")
            return None
    
    def save_session(self, session_token: str, session_data: Dict) -> bool:
        """Save session to MongoDB"""
        try:
            if self.db is None:
                return False
            
            sessions_collection = self.db['sessions']
            session_doc = {
                'session_token': session_token,
                'account_id': session_data.get('account_id'),
                'email': session_data.get('email'),
                'name': session_data.get('name', ''),
                'expires_at': session_data.get('expires_at'),
                'created_at': session_data.get('created_at', datetime.utcnow().isoformat()),
                'last_accessed': datetime.utcnow().isoformat()
            }
            
            # Add credentials if present (for OAuth sessions)
            if 'credentials' in session_data:
                session_doc['credentials'] = session_data['credentials']
            
            sessions_collection.update_one(
                {'session_token': session_token},
                {'$set': session_doc},
                upsert=True
            )
            return True
        except Exception as e:
            print(f"Error saving session: {e}")
            return False
    
    def get_session(self, session_token: str) -> Optional[Dict]:
        """Get session from MongoDB"""
        try:
            if self.db is None:
                return None
            
            sessions_collection = self.db['sessions']
            session_doc = sessions_collection.find_one({'session_token': session_token})
            
            if session_doc:
                # Remove MongoDB _id and return
                session_doc.pop('_id', None)
                # Check if expired
                expires_at = session_doc.get('expires_at')
                if expires_at:
                    try:
                        # Parse ISO format string
                        if isinstance(expires_at, str):
                            expires_dt = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                        else:
                            expires_dt = expires_at
                        if expires_dt < datetime.utcnow():
                            # Session expired, delete it
                            self.delete_session(session_token)
                            return None
                    except:
                        pass
                return session_doc
            return None
        except Exception as e:
            print(f"Error getting session: {e}")
            return None
    
    def delete_session(self, session_token: str) -> bool:
        """Delete session from MongoDB"""
        try:
            if self.db is None:
                return False
            
            sessions_collection = self.db['sessions']
            result = sessions_collection.delete_one({'session_token': session_token})
            return result.deleted_count > 0
        except Exception as e:
            print(f"Error deleting session: {e}")
            return False
    
    def load_all_sessions(self) -> Dict[str, Dict]:
        """Load all active sessions from MongoDB"""
        try:
            if self.db is None:
                return {}
            
            sessions_collection = self.db['sessions']
            now = datetime.utcnow()
            
            # Get all non-expired sessions
            sessions = {}
            for session_doc in sessions_collection.find({}):
                session_token = session_doc.get('session_token')
                if not session_token:
                    continue
                
                # Check if expired
                expires_at = session_doc.get('expires_at')
                if expires_at:
                    try:
                        # Parse ISO format string
                        if isinstance(expires_at, str):
                            expires_dt = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                        else:
                            expires_dt = expires_at
                        if expires_dt < now:
                            # Skip expired sessions
                            continue
                    except:
                        # If we can't parse, skip it
                        continue
                
                # Remove MongoDB _id and add to dict
                session_doc.pop('_id', None)
                sessions[session_token] = session_doc
            
            return sessions
        except Exception as e:
            print(f"Error loading sessions: {e}")
            return {}
    
    def cleanup_expired_sessions(self):
        """Remove expired sessions from MongoDB"""
        try:
            if self.db is None:
                return
            
            sessions_collection = self.db['sessions']
            now = datetime.utcnow().isoformat()
            
            # Delete sessions where expires_at < now
            result = sessions_collection.delete_many({
                'expires_at': {'$lt': now}
            })
            if result.deleted_count > 0:
                print(f"✓ Cleaned up {result.deleted_count} expired sessions")
        except Exception as e:
            print(f"Error cleaning up sessions: {e}")
    
    def delete_account_sessions(self, account_id: int) -> int:
        """Delete all sessions for a specific account"""
        try:
            if self.db is None:
                return 0
            
            sessions_collection = self.db['sessions']
            result = sessions_collection.delete_many({'account_id': account_id})
            return result.deleted_count
        except Exception as e:
            print(f"Error deleting account sessions: {e}")
            return 0
    
    def close(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()
            print("✓ MongoDB connection closed")


# Global instance
mongodb_manager = MongoDBManager()

