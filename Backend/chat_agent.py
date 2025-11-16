"""
Chat Agent - Conversational interface for email management using Azure OpenAI
"""

from typing import List, Dict, Optional
import config
import json


class ChatAgent:
    """AI-powered chat agent for conversing about emails"""
    
    def __init__(self):
        """Initialize Chat Agent with Azure OpenAI"""
        self.client = None
        self.deployment = None
        self.conversation_history = []
        self.email_context = []
        
        # Initialize Azure OpenAI - Read from .env files
        if config.USE_AZURE_OPENAI:
            try:
                from openai import AzureOpenAI
                # Read from .env files
                azure_key = config.AZURE_OPENAI_KEY
                azure_endpoint = config.AZURE_OPENAI_ENDPOINT
                azure_deployment = config.AZURE_OPENAI_DEPLOYMENT
                azure_api_version = config.AZURE_OPENAI_API_VERSION
                
                if not azure_key or not azure_endpoint:
                    print("⚠ Chat Agent: Azure OpenAI credentials not configured. Please configure in admin panel.")
                else:
                    self.client = AzureOpenAI(
                        api_key=azure_key,
                        api_version=azure_api_version,
                        azure_endpoint=azure_endpoint
                    )
                    self.deployment = azure_deployment
                    print(f"✓ Chat Agent initialized with Azure OpenAI (deployment: {self.deployment})")
            except ImportError:
                print("⚠ OpenAI package not installed. Run: pip install openai")
            except Exception as e:
                print(f"⚠ Could not initialize Chat Agent: {e}")
    
    def set_email_context(self, emails: List[Dict]):
        """Set the email context for the conversation"""
        self.email_context = emails
        print(f"✓ Chat Agent context updated with {len(emails)} emails")
    
    def _format_email_context(self, limit: int = 20) -> str:
        """Format email context for the AI prompt"""
        if not self.email_context:
            return "No emails loaded yet."
        
        context = "Here are the user's recent emails:\n\n"
        
        for idx, email in enumerate(self.email_context[:limit], 1):
            context += f"Email {idx}:\n"
            context += f"From: {email.get('from', 'Unknown')}\n"
            context += f"Subject: {email.get('subject', 'No subject')}\n"
            context += f"Date: {email.get('date', 'Unknown date')}\n"
            
            # Add AI analysis if available
            if email.get('ai_analysis'):
                analysis = email['ai_analysis']
                context += f"Category: {analysis.get('category', 'other')}\n"
                if analysis.get('urgency_score', 0) > 6:
                    context += f"⚠️ Urgent (score: {analysis['urgency_score']}/10)\n"
                if analysis.get('summary'):
                    context += f"Summary: {analysis['summary']}\n"
            
            # Add body preview
            body = email.get('text_body', '')
            if body:
                preview = body.strip()[:200]
                if len(body) > 200:
                    preview += "..."
                context += f"Preview: {preview}\n"
            
            context += "\n---\n\n"
        
        return context
    
    def _get_system_prompt(self) -> str:
        """Get the system prompt for the chat agent"""
        return """You are an intelligent email assistant powered by Azure OpenAI. You help users manage and understand their emails through natural conversation.

Your capabilities:
- Answer questions about emails (who sent what, when, subjects, etc.)
- Summarize emails or groups of emails
- Find specific emails based on criteria
- Identify urgent or important emails
- Suggest actions or responses
- Extract information from emails

Guidelines:
- Be conversational, friendly, and helpful
- Provide specific email details when relevant (use email numbers like "Email 1", "Email 2")
- If asked to compose a reply, draft professional responses
- If information isn't in the email context, say so
- Keep responses concise but informative
- Use emojis sparingly and professionally

Email context is provided below. Use this information to answer user questions."""
    
    def chat(self, user_message: str, include_context: bool = True, use_vector_search: bool = False, total_email_count: int = 0, account_id: Optional[int] = None) -> Dict:
        """
        Send a message and get a response from the chat agent
        
        Args:
            user_message: The user's message
            include_context: Whether to include email context
            use_vector_search: Use semantic search to find relevant emails
            total_email_count: Total number of emails in the inbox (for accurate counting)
            account_id: Account ID to use (session-based, not global active account)
        
        Returns:
            Dictionary with response and metadata
        """
        if not self.client:
            return {
                "response": "Chat agent is not initialized. Please check Azure OpenAI configuration.",
                "error": True
            }
        
        try:
            # Build messages for the conversation
            messages = [
                {"role": "system", "content": self._get_system_prompt()}
            ]
            
            # Add email context using RAG (Retrieval Augmented Generation)
            # Always use vector search if available for better context
            if include_context:
                context_message = ""
                
                # Detect temporal queries (last, recent, newest, latest, most recent)
                user_message_lower = user_message.lower()
                temporal_keywords = ['last', 'recent', 'newest', 'latest', 'most recent', 'new email', 'latest email', 'last email', 'recent email']
                is_temporal_query = any(keyword in user_message_lower for keyword in temporal_keywords)
                
                # Extract number from query (e.g., "last 2", "last two", "recent 3 emails")
                email_limit = 5  # Default to 5 for plural
                if is_temporal_query:
                    import re
                    
                    # First check for explicit numbers
                    numeric_match = re.search(r'(?:last|recent|newest|latest)\s+(\d+)', user_message_lower)
                    has_explicit_number = False
                    
                    if numeric_match:
                        email_limit = int(numeric_match.group(1))
                        has_explicit_number = True
                        print(f"📅 Detected numeric temporal query: '{user_message}' -> limit = {email_limit}")
                    else:
                        # Try word numbers: "last two", "last three", etc.
                        word_numbers = {
                            'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
                            'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10
                        }
                        for word, num in word_numbers.items():
                            if f'last {word}' in user_message_lower or f'recent {word}' in user_message_lower:
                                email_limit = num
                                has_explicit_number = True
                                break
                    
                    # If no explicit number, detect singular queries (flexible matching)
                    if not has_explicit_number:
                        # Flexible singular keywords - match "last email", "latest email" etc. anywhere
                        singular_keywords = ['last email', 'latest email', 'newest email', 'most recent email', 'new email']
                        is_singular = any(keyword in user_message_lower for keyword in singular_keywords)
                        
                        if is_singular:
                            email_limit = 1
                            print(f"📅 Detected singular temporal query: '{user_message}' -> limit = 1")
                        else:
                            # Default to 5 for plural or unspecified
                            print(f"📅 Detected temporal query (default): '{user_message}' -> limit = 5")
                
                # For temporal queries, use MongoDB date sorting instead of vector search
                # Always use MongoDB for temporal queries (don't require use_vector_search)
                if is_temporal_query:
                    try:
                        from mongodb_manager import mongodb_manager
                        # Import from api_server where account_manager is initialized
                        import api_server
                        account_manager = api_server.account_manager
                        
                        # Use account_id parameter if provided (session-based), otherwise fallback to global
                        if account_id and account_manager:
                            active_account = account_manager.get_account(account_id)
                        elif account_manager:
                            active_account = account_manager.get_active_account()
                        else:
                            print("⚠️ Temporal query: account_manager not initialized")
                            active_account = None
                        
                        if active_account and mongodb_manager.emails_collection is not None:
                            # Get most recent emails sorted by date_str (newest first)
                            # Filter to only include emails with valid date_str for accurate sorting
                            query = {
                                "account_id": active_account['id'],
                                "date_str": {"$exists": True, "$ne": ""}
                            }
                            emails_cursor = mongodb_manager.emails_collection.find(
                                query
                            ).sort("date_str", -1).limit(email_limit)  # Use extracted limit
                            
                            emails_list = list(emails_cursor)
                            if emails_list:
                                print(f"📅 Temporal query detected: Found {len(emails_list)} most recent emails (requested: {email_limit})")
                                # Log the actual dates for debugging
                                for i, email in enumerate(emails_list[:3], 1):
                                    print(f"  📧 Email {i}: date_str='{email.get('date_str')}', subject='{email.get('subject', '')[:50]}'")
                                
                                context_parts = [
                                    f"IMPORTANT: You have access to a total of {total_email_count} emails in the inbox. ",
                                    f"The following are the {len(emails_list)} most recent emails (sorted by date, newest first):\n"
                                ]
                                for i, email in enumerate(emails_list, 1):
                                    context_parts.append(f"\n--- Email {i} (Most Recent) ---")
                                    if email.get('subject'):
                                        context_parts.append(f"Subject: {email['subject']}")
                                    if email.get('from'):
                                        context_parts.append(f"From: {email['from']}")
                                    if email.get('date_str'):
                                        context_parts.append(f"Date: {email['date_str']}")
                                    if email.get('text_body'):
                                        body_preview = email['text_body'][:500] if len(email['text_body']) > 500 else email['text_body']
                                        context_parts.append(f"Body: {body_preview}")
                                    elif email.get('html_body'):
                                        # Fallback to HTML body if text_body not available
                                        import re
                                        html_body = email['html_body']
                                        # Remove HTML tags for preview
                                        text_content = re.sub(r'<[^>]+>', '', html_body)
                                        body_preview = text_content[:500] if len(text_content) > 500 else text_content
                                        context_parts.append(f"Body: {body_preview}")
                                context_message = "\n".join(context_parts)
                            else:
                                print(f"⚠️ Temporal query: No emails found in MongoDB")
                    except Exception as e:
                        print(f"❌ Error fetching recent emails for temporal query: {e}")
                        import traceback
                        traceback.print_exc()
                        # Fall through to vector search as backup
                        is_temporal_query = False
                        context_message = ""
                
                # For non-temporal queries, use vector search (RAG) for semantic search
                if not context_message and use_vector_search:
                    try:
                        from vector_store import vector_store
                        if vector_store.collection:
                            relevant_results = vector_store.get_relevant_emails_for_chat(user_message, n_results=10)
                            if relevant_results:
                                print(f"✅ Found {len(relevant_results)} relevant emails for query: '{user_message}'")
                                # Log similarity scores for debugging
                                similarities = [f"{r.get('similarity', 0):.3f}" for r in relevant_results[:5]]
                                print(f"📊 Relevance scores (top 5): {similarities}")
                                
                                # Include total count in context so AI knows the full picture
                                context_parts = [
                                    f"IMPORTANT: You have access to a total of {total_email_count} emails in the inbox. ",
                                    f"The following are the most relevant emails (top {min(len(relevant_results), 10)}) found via semantic search based on the user's query '{user_message}':\n",
                                    "Please carefully review these emails and provide a helpful answer based on their content.\n"
                                ]
                                for i, result in enumerate(relevant_results, 1):
                                    similarity = result.get('similarity', 0)
                                    context_parts.append(f"\n--- Email {i} (Relevance: {similarity:.1%}) ---")
                                    context_parts.append(result.get('document', ''))
                                    # Add metadata if available
                                    if result.get('metadata'):
                                        meta = result['metadata']
                                        if meta.get('subject'):
                                            context_parts.append(f"Subject: {meta['subject']}")
                                        if meta.get('from'):
                                            context_parts.append(f"From: {meta['from']}")
                                context_message = "\n".join(context_parts)
                            else:
                                print(f"⚠️ No relevant emails found for query: '{user_message}'")
                                # Try a broader search with individual keywords as fallback
                                keywords = [w for w in user_message.lower().split() if len(w) > 3]  # Skip short words
                                for keyword in keywords[:3]:  # Try first 3 meaningful keywords
                                    broader_results = vector_store.get_relevant_emails_for_chat(keyword, n_results=5)
                                    if broader_results:
                                        print(f"✅ Found {len(broader_results)} emails using keyword fallback: '{keyword}'")
                                        context_parts = [
                                            f"IMPORTANT: You have access to a total of {total_email_count} emails in the inbox. ",
                                            f"The following emails were found using keyword search for '{keyword}':\n"
                                        ]
                                        for i, result in enumerate(broader_results, 1):
                                            context_parts.append(f"\n--- Email {i} ---")
                                            context_parts.append(result.get('document', ''))
                                            if result.get('metadata'):
                                                meta = result['metadata']
                                                if meta.get('subject'):
                                                    context_parts.append(f"Subject: {meta['subject']}")
                                                if meta.get('from'):
                                                    context_parts.append(f"From: {meta['from']}")
                                        context_message = "\n".join(context_parts)
                                        break
                    except Exception as e:
                        print(f"❌ Vector search error: {e}")
                        import traceback
                        traceback.print_exc()
                        context_message = ""
                
                # Fallback to email_context if vector search didn't provide results
                if not context_message and self.email_context:
                    context_message = self._format_email_context()
                
                # Add total count to context if available (even if no vector search)
                if total_email_count > 0 and context_message:
                    # Prepend total count info to context
                    context_message = f"IMPORTANT: You have access to a total of {total_email_count} emails in the inbox.\n\n{context_message}"
                elif total_email_count > 0 and not context_message:
                    # If no other context, at least provide the count
                    context_message = f"You have access to a total of {total_email_count} emails in the inbox."
                
                # Add context to messages if we have any
                if context_message:
                    messages.append({
                        "role": "system", 
                        "content": f"Email context (use this information to answer the user's question):\n\n{context_message}\n\nIMPORTANT INSTRUCTIONS:\n- You MUST carefully review the emails provided above and answer based on their ACTUAL content\n- If the emails contain information relevant to the user's query, summarize and present that information\n- If the emails do NOT actually contain the requested information (even if they were returned by search), you MUST say so clearly and honestly\n- Reference specific emails by number (e.g., 'Email 1', 'Email 2') when mentioning details\n- Be critical: if an email's relevance score is low or it doesn't match the query, point that out\n- Do NOT claim emails are relevant if they clearly are not - be honest about search quality"
                    })
                elif total_email_count > 0:
                    # If we have emails but no context was found, inform the AI
                    messages.append({
                        "role": "system",
                        "content": f"You have access to {total_email_count} emails in the inbox, but no specific emails matched the user's query '{user_message}'. Politely inform the user that you couldn't find relevant emails. Suggest they try:\n- Using different keywords\n- Rephrasing their question\n- Being more specific about what they're looking for"
                    })
            
            # Add conversation history (last 10 messages)
            messages.extend(self.conversation_history[-10:])
            
            # Add current user message
            messages.append({"role": "user", "content": user_message})
            
            # Call Azure OpenAI
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=messages,
                temperature=0.7,
                max_tokens=800,
                top_p=0.9
            )
            
            assistant_response = response.choices[0].message.content
            
            # Update conversation history
            self.conversation_history.append({"role": "user", "content": user_message})
            self.conversation_history.append({"role": "assistant", "content": assistant_response})
            
            # Keep only last 20 messages to avoid token limits
            if len(self.conversation_history) > 20:
                self.conversation_history = self.conversation_history[-20:]
            
            return {
                "response": assistant_response,
                "error": False,
                "tokens_used": response.usage.total_tokens if hasattr(response, 'usage') else None
            }
        
        except Exception as e:
            print(f"Chat error: {e}")
            return {
                "response": f"I encountered an error: {str(e)}",
                "error": True
            }
    
    def reset_conversation(self):
        """Reset the conversation history"""
        self.conversation_history = []
        return {"message": "Conversation history cleared"}
    
    def get_conversation_history(self) -> List[Dict]:
        """Get the conversation history"""
        return self.conversation_history
    
    def suggest_questions(self) -> List[str]:
        """Suggest questions the user can ask"""
        if not self.email_context:
            return [
                "Load some emails first, then I can help you!",
                "Try clicking 'Load Emails' in the Inbox tab."
            ]
        
        suggestions = [
            "What are my most urgent emails?",
            "Summarize my unread emails",
            "Who sent me emails today?",
            "Are there any important emails I should respond to?",
            "Find emails about [topic]",
            "Draft a reply to the latest email",
            "Show me emails from [sender]",
            "What emails need my attention?"
        ]
        
        # Add context-specific suggestions
        if len(self.email_context) > 0:
            latest_sender = self.email_context[0].get('from', '').split('<')[0].strip()
            if latest_sender:
                suggestions.insert(0, f"Tell me about the email from {latest_sender}")
        
        return suggestions[:6]  # Return top 6 suggestions

