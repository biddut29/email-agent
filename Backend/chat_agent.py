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
    
    def chat(self, user_message: str, include_context: bool = True, use_vector_search: bool = False) -> Dict:
        """
        Send a message and get a response from the chat agent
        
        Args:
            user_message: The user's message
            include_context: Whether to include email context
            use_vector_search: Use semantic search to find relevant emails
        
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
                
                # Prioritize vector search (RAG) for semantic search
                if use_vector_search:
                    try:
                        from vector_store import vector_store
                        if vector_store.collection:
                            relevant_results = vector_store.get_relevant_emails_for_chat(user_message, n_results=5)
                            if relevant_results:
                                context_parts = ["Relevant emails from your inbox (found via semantic search):\n"]
                                for i, result in enumerate(relevant_results, 1):
                                    context_parts.append(f"\n--- Email {i} ---")
                                    context_parts.append(result.get('document', ''))
                                    # Add metadata if available
                                    if result.get('metadata'):
                                        meta = result['metadata']
                                        if meta.get('subject'):
                                            context_parts.append(f"Subject: {meta['subject']}")
                                        if meta.get('from'):
                                            context_parts.append(f"From: {meta['from']}")
                                context_message = "\n".join(context_parts)
                    except Exception as e:
                        print(f"Vector search error: {e}")
                        context_message = ""
                
                # Fallback to email_context if vector search didn't provide results
                if not context_message and self.email_context:
                    context_message = self._format_email_context()
                
                # Add context to messages if we have any
                if context_message:
                    messages.append({
                        "role": "system", 
                        "content": f"Email context (use this information to answer the user's question):\n\n{context_message}\n\nAnswer the user's question based on the email context above. If the information is not in the emails, say so."
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

