"""
AI Agent Module - Handles AI-powered email analysis and response generation
"""

import re
from typing import Dict, List, Optional
import config


class AIAgent:
    """AI-powered email agent for analysis and response generation"""
    
    def __init__(self, api_key: Optional[str] = None, provider: str = "azure"):
        """
        Initialize AI Agent
        
        Args:
            api_key: API key for AI provider (OpenAI, Anthropic, Azure, etc.)
            provider: AI provider to use ("azure", "openai", "anthropic", or "local")
        """
        self.api_key = api_key
        self.provider = provider
        self.client = None
        self.azure_deployment = None
        
        # Initialize Azure OpenAI client
        # Read provider from .env files
        db_provider = config.AI_PROVIDER
        print(f"🔍 AI Agent init - Provider from config: '{db_provider}', Provider param: '{self.provider}'")
        
        if db_provider.lower() == "azure" and self.provider == "azure":
            try:
                from openai import AzureOpenAI
                
                # Read from .env files
                azure_key = config.AZURE_OPENAI_KEY
                azure_endpoint = config.AZURE_OPENAI_ENDPOINT
                azure_deployment = config.AZURE_OPENAI_DEPLOYMENT
                azure_api_version = config.AZURE_OPENAI_API_VERSION
                
                print(f"🔍 Azure OpenAI config check:")
                print(f"  Key: {'SET' if azure_key else 'NOT SET'} ({len(azure_key) if azure_key else 0} chars)")
                print(f"  Endpoint: {azure_endpoint[:80] if azure_endpoint else 'NOT SET'}...")
                print(f"  Deployment: {azure_deployment}")
                print(f"  API Version: {azure_api_version}")
                
                # Check if Azure OpenAI credentials are configured
                if not azure_key or not azure_endpoint:
                    print("⚠ Azure OpenAI credentials not configured. Please configure in admin panel or database.")
                    self.client = None
                else:
                    try:
                        self.client = AzureOpenAI(
                            api_key=azure_key,
                            api_version=azure_api_version,
                            azure_endpoint=azure_endpoint
                        )
                        self.azure_deployment = azure_deployment
                        print(f"✓ Azure OpenAI client initialized (deployment: {self.azure_deployment})")
                        print(f"  Endpoint: {azure_endpoint[:80]}...")
                        
                        # Test the client with a simple call
                        print("🔍 Testing Azure OpenAI client...")
                        test_response = self.client.chat.completions.create(
                            model=self.azure_deployment,
                            messages=[{"role": "user", "content": "Say hello"}],
                            max_tokens=5
                        )
                        print(f"✅ Azure OpenAI client test successful: {test_response.choices[0].message.content}")
                    except Exception as init_error:
                        print(f"❌ Failed to initialize Azure OpenAI client: {init_error}")
                        import traceback
                        traceback.print_exc()
                        self.client = None
            except ImportError:
                print("⚠ OpenAI package not installed. Run: pip install openai")
                self.client = None
            except Exception as e:
                print(f"⚠ Could not initialize Azure OpenAI client: {e}")
                import traceback
                traceback.print_exc()
                self.client = None
        else:
            print(f"⚠ Skipping Azure OpenAI init - Provider mismatch: config='{db_provider}', param='{self.provider}'")
        
        # Initialize regular OpenAI client
        if self.provider == "openai":
            self.api_key = api_key or config.OPENAI_API_KEY
            if self.api_key:
                try:
                    import openai
                    self.client = openai.OpenAI(api_key=self.api_key)
                    print("✓ OpenAI client initialized")
                except ImportError:
                    print("⚠ OpenAI package not installed. Run: pip install openai")
                except Exception as e:
                    print(f"⚠ Could not initialize OpenAI client: {e}")
        
        # Initialize Anthropic client
        elif self.provider == "anthropic":
            self.api_key = api_key or config.ANTHROPIC_API_KEY
            if self.api_key:
                try:
                    import anthropic
                    self.client = anthropic.Anthropic(api_key=self.api_key)
                    print("✓ Anthropic client initialized")
                except ImportError:
                    print("⚠ Anthropic package not installed. Run: pip install anthropic")
                except Exception as e:
                    print(f"⚠ Could not initialize Anthropic client: {e}")
    
    def categorize_email(self, email_data: Dict) -> str:
        """
        Categorize an email using AI or rule-based logic
        
        Returns:
            Category name (e.g., "urgent", "spam", "personal", etc.)
        """
        subject = email_data.get('subject', '').lower()
        body = email_data.get('text_body', '').lower()
        from_email = email_data.get('from', '').lower()
        
        # Rule-based categorization (fallback if no AI)
        if self.client:
            return self._ai_categorize(email_data)
        else:
            return self._rule_based_categorize(subject, body, from_email)
    
    def _rule_based_categorize(self, subject: str, body: str, from_email: str) -> str:
        """Rule-based email categorization"""
        # Spam indicators
        spam_keywords = ['viagra', 'lottery', 'winner', 'click here', 'limited time offer']
        if any(keyword in subject or keyword in body for keyword in spam_keywords):
            return "spam"
        
        # Urgent indicators
        urgent_keywords = ['urgent', 'asap', 'emergency', 'important', 'critical']
        if any(keyword in subject for keyword in urgent_keywords):
            return "urgent"
        
        # Newsletter indicators
        if 'unsubscribe' in body or 'newsletter' in subject:
            return "newsletter"
        
        # Promotional indicators
        promo_keywords = ['sale', 'discount', 'offer', 'deal', 'promotion']
        if any(keyword in subject or keyword in body for keyword in promo_keywords):
            return "promotional"
        
        # Work indicators (common work domains)
        work_domains = ['@company.com', '@corp.com', 'slack', 'jira', 'confluence']
        if any(domain in from_email for domain in work_domains):
            return "work"
        
        # Personal (common personal email providers)
        personal_domains = ['@gmail.com', '@yahoo.com', '@outlook.com', '@hotmail.com']
        if any(domain in from_email for domain in personal_domains):
            return "personal"
        
        return "other"
    
    def _ai_categorize(self, email_data: Dict) -> str:
        """AI-powered email categorization"""
        try:
            subject = email_data.get('subject', '')
            body = email_data.get('text_body', '')[:500]  # Limit body length
            from_email = email_data.get('from', '')
            
            prompt = f"""Categorize this email into ONE of these categories: {', '.join(config.EMAIL_CATEGORIES)}

Email From: {from_email}
Subject: {subject}
Body Preview: {body}

Category (respond with just the category name):"""
            
            if self.provider == "azure":
                response = self.client.chat.completions.create(
                    model=self.azure_deployment,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=20
                )
                category = response.choices[0].message.content.strip().lower()
            
            elif self.provider == "openai":
                response = self.client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=20
                )
                category = response.choices[0].message.content.strip().lower()
            
            elif self.provider == "anthropic":
                response = self.client.messages.create(
                    model="claude-3-haiku-20240307",
                    max_tokens=20,
                    messages=[{"role": "user", "content": prompt}]
                )
                category = response.content[0].text.strip().lower()
            
            # Validate category
            if category in config.EMAIL_CATEGORIES:
                return category
            
            return "other"
            
        except Exception as e:
            print(f"AI categorization failed, using rule-based: {e}")
            return self._rule_based_categorize(
                email_data.get('subject', '').lower(),
                email_data.get('text_body', '').lower(),
                email_data.get('from', '').lower()
            )
    
    def summarize_email(self, email_data: Dict) -> str:
        """Generate a summary of the email"""
        if self.client:
            return self._ai_summarize(email_data)
        else:
            return self._simple_summarize(email_data)
    
    def _simple_summarize(self, email_data: Dict) -> str:
        """Simple rule-based summary"""
        body = email_data.get('text_body', '')
        # Return first 200 characters as summary
        summary = body.strip()[:200]
        if len(body) > 200:
            summary += "..."
        return summary
    
    def _ai_summarize(self, email_data: Dict) -> str:
        """AI-powered email summarization"""
        try:
            subject = email_data.get('subject', '')
            body = email_data.get('text_body', '')[:2000]
            
            prompt = f"""Summarize this email in 2-3 concise sentences:

Subject: {subject}
Body: {body}

Summary:"""
            
            if self.provider == "azure":
                response = self.client.chat.completions.create(
                    model=self.azure_deployment,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.5,
                    max_tokens=150
                )
                return response.choices[0].message.content.strip()
            
            elif self.provider == "openai":
                response = self.client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.5,
                    max_tokens=150
                )
                return response.choices[0].message.content.strip()
            
            elif self.provider == "anthropic":
                response = self.client.messages.create(
                    model="claude-3-haiku-20240307",
                    max_tokens=150,
                    messages=[{"role": "user", "content": prompt}]
                )
                return response.content[0].text.strip()
            
        except Exception as e:
            print(f"AI summarization failed: {e}")
            return self._simple_summarize(email_data)
    
    def generate_response(self, email_data: Dict, tone: str = "professional") -> str:
        """
        Generate an AI response to an email
        
        Args:
            email_data: Email data dictionary
            tone: Response tone (professional, friendly, formal, casual)
        
        Returns:
            Generated response text
        """
        if self.client:
            print(f"✅ Using AI client (provider: {self.provider})")
            return self._ai_generate_response(email_data, tone)
        else:
            print(f"⚠️  AI client is None - using template response")
            print(f"   Provider: {self.provider}")
            print(f"   Client status: {self.client}")
            print(f"   This means AI is not configured or initialization failed")
            return self._template_response(email_data)
    
    def _template_response(self, email_data: Dict) -> str:
        """Generate a template response based on email content"""
        from_name = email_data.get('from', '').split('<')[0].strip()
        if not from_name or from_name == email_data.get('from', ''):
            from_name = "there"
        
        subject = email_data.get('subject', 'your message')
        body = email_data.get('text_body', '') or email_data.get('html_body', '')
        
        # Clean body - remove quoted content if it's a reply
        if body:
            # Remove quoted original content
            quote_markers = ['---------- Original Message ----------', 'From:', 'On ', '>']
            for marker in quote_markers:
                if marker in body:
                    parts = body.split(marker)
                    if parts and parts[0].strip():
                        body = parts[0].strip()
                        break
        
        # Clean and normalize body for better matching
        body_clean = body.strip() if body else ''
        body_lower = body_clean.lower() if body_clean else ''
        
        # Get sender name
        sender_name = config.EMAIL_ADDRESS.split('@')[0].replace('.', ' ').title() if hasattr(config, 'EMAIL_ADDRESS') else 'Email Agent'
        
        # Debug: Print what we're working with
        print(f"📝 Template response - Subject: '{subject}', Body length: {len(body_clean)}, Body: '{body_clean[:100]}'")
        
        # Detect different types of messages and respond appropriately
        # Greetings and casual questions (check for these patterns - use word boundaries for better matching)
        greeting_patterns = [
            'how are you', 'how are things', 'how\'s it going', 'how is it going',
            'how do you do', 'how r u', 'how ru', 'how are u',
            'how have you been', 'how\'s everything', 'how is everything'
        ]
        # Check if any greeting pattern appears in the body (more flexible matching)
        has_greeting = False
        for pattern in greeting_patterns:
            # Remove apostrophes and check
            pattern_clean = pattern.replace("'", "").replace("'", "")
            body_for_match = body_lower.replace("'", "").replace("'", "")
            if pattern_clean in body_for_match or pattern in body_lower:
                has_greeting = True
                break
        
        if has_greeting:
            # Customize based on the actual greeting
            if 'how are you' in body_lower:
                greeting_response = "I'm doing well, thank you for asking!"
            elif 'how\'s it going' in body_lower or 'how is it going' in body_lower:
                greeting_response = "Things are going well, thanks for asking!"
            else:
                greeting_response = "I'm doing well, thank you!"
            
            return f"""Hi {from_name},

{greeting_response}

{f'I see you reached out about "{subject}". ' if subject and subject.lower() not in ['re:', 'test', 'test 60', 'test 59'] else ''}How can I help you today?

Best regards,
{sender_name}"""
        
        # Direct questions
        elif '?' in body or any(q in body_lower for q in ['how', 'what', 'when', 'where', 'why', 'can you', 'could you', 'would you', 'do you']):
            # Extract the question
            question_part = body[:150] if body else 'your question'
            return f"""Hi {from_name},

Thank you for your email.

Regarding your question: {question_part}

Let me look into this and get back to you with a detailed answer.

Best regards,
{sender_name}"""
        
        # Requests
        elif any(r in body_lower for r in ['please', 'need', 'request', 'would like', 'asking', 'help', 'assist']):
            request_part = body[:150] if body else 'your request'
            return f"""Hi {from_name},

Thank you for reaching out.

I understand you need: {request_part}

I will look into this and follow up with you shortly.

Best regards,
{sender_name}"""
        
        # Information sharing
        elif any(info in body_lower for info in ['just wanted to', 'letting you know', 'inform', 'update', 'share']):
            return f"""Hi {from_name},

Thank you for sharing this information with me.

{body[:200] if body and len(body) > 10 else 'I have received your message and noted the information.'}

I appreciate you keeping me updated.

Best regards,
{sender_name}"""
        
        # General messages with body content
        elif body and len(body.strip()) > 10:
            # Use the actual body content in response
            body_preview = body[:200] if len(body) > 200 else body
            return f"""Hi {from_name},

Thank you for your email.

{body_preview}

I have received your message and will respond accordingly.

Best regards,
{sender_name}"""
        
        # Fallback for empty or very short messages
        else:
            return f"""Hi {from_name},

Thank you for your email regarding "{subject}".

I have received your message and will get back to you shortly.

Best regards,
{sender_name}"""
    
    def _ai_generate_response(self, email_data: Dict, tone: str) -> str:
        """AI-powered response generation with deep analysis"""
        try:
            if not self.client:
                print("⚠️  AI client not available, using template response")
                return self._template_response(email_data)
            
            subject = email_data.get('subject', '')
            # Get body - prefer text_body, fallback to html_body, ensure we have content
            body = email_data.get('text_body', '') or email_data.get('html_body', '')
            
            # Clean body - remove quoted original content if present (for reply emails)
            original_body = body
            if body:
                # Remove common quote markers to get only new content
                quote_markers = [
                    '---------- Original Message ----------',
                    'From:',
                    'On ',
                    '>',
                ]
                for marker in quote_markers:
                    if marker in body:
                        # Try to extract only the new content before quotes
                        parts = body.split(marker)
                        if parts and parts[0].strip():
                            body = parts[0].strip()
                            break
                
                # If body is too short after cleaning, use original (might be a short message)
                if len(body.strip()) < 10 and len(original_body.strip()) > 10:
                    body = original_body
                
                # Limit body length but ensure we have meaningful content
                if len(body) > 2500:
                    body = body[:2500] + "..."
            else:
                body = "No body content provided."
            
            # Log what we're analyzing
            print(f"🤖 AI analyzing - Subject: '{subject[:50]}', Body length: {len(body)} chars")
            
            from_email = email_data.get('from', '')
            from_name = from_email.split('<')[0].strip() if '<' in from_email else from_email.split('@')[0]
            
            # Get sender's email from config or account
            sender_email = config.EMAIL_ADDRESS if hasattr(config, 'EMAIL_ADDRESS') else 'bidduttest@gmail.com'
            sender_name = sender_email.split('@')[0].replace('.', ' ').title()
            
            prompt = f"""You are an expert email writing assistant that helps draft natural, conversational email replies. You write in a clear, concise tone that matches the sender's communication style.

EMAIL TO REPLY TO:
From: {from_name} ({from_email})
Subject: {subject}
Body: {body}

YOUR TASK:
Understand the sender's intent (question, request, greeting, information sharing, etc.) and write a natural, direct reply.

CRITICAL RULES - FOLLOW STRICTLY:
1. NEVER start with "Thank you for your email" or "Hi [Name], Thank you for your email"
2. NEVER use "Regarding your question" or "Regarding [topic]"
3. NEVER use "I received your message" or "Thank you for reaching out"
4. NEVER use "I see you reached out about..." or "I see you asked about..."
5. NEVER use "How can I help you today?" or similar customer service phrases
6. NEVER use "thank you for asking" - just answer directly
7. NEVER use formal business email templates
8. ALWAYS answer questions directly and naturally - respond as if in a conversation
9. Match the sender's tone - if they're casual, be casual; if formal, be professional
10. Keep responses concise (2-4 sentences) but meaningful
11. Write as if texting a friend (for casual emails) - be friendly, warm, conversational
12. If asked "How are you?" → Answer directly: "I'm doing well! How about you?" (NOT "I'm doing well, thank you for asking!")

WHAT TO DO:
- If they ask "How are you?" → Start directly: "I'm doing well, thanks! How about you?"
- If they ask "where are you?" → Start directly: "I'm here and available. What's up!"
- If they ask "are you okay?" → Start directly: "Yes, I'm doing great! How are you?" (NO "Thank you for your email" or "Regarding your question")
- If they ask "what is the status of your health?" → Start directly: "All good here! How are you?"
- If they ask any question → Answer it directly, don't preface with thank yous or formal greetings
- If they share news → Acknowledge naturally: "That's great!" or "Thanks for letting me know!"
- If they greet you → Respond naturally: "Hi! How can I help?" or "Hey! What's up!"

BAD EXAMPLES (DO NOT DO THIS - THESE ARE WRONG):
❌ "Hi Biddut Hossain, Thank you for your email. Regarding your question: are you okay? Let me look into that."
❌ "Hi Biddut Hossain, Thank you for your email. Regarding your question: where are you? Let me look into that."
❌ "Thank you for reaching out. I received your message about your health status."
❌ "Hi, Thank you for your email regarding [subject]."
❌ "I'm doing well, thank you for asking!" (WRONG - too formal)
❌ "I see you reached out about 'Status'. How can I help you today?" (WRONG - generic customer service)
❌ "I see you asked about [topic]. Let me help you with that." (WRONG - too formal)
❌ ANY response that starts with "Thank you for your email", "Regarding your question", "I see you reached out", or "How can I help you today?"

GOOD EXAMPLES (DO THIS - THESE ARE CORRECT):
✅ "Yes, I'm doing great! How are you?" (for "are you okay?")
✅ "I'm here and available. What's up!" (for "where are you?")
✅ "All good here! How are you?" (for health status questions)
✅ "I'm doing well! How about you?" (for "how are you?" - direct, no "thank you for asking")
✅ "Hey! What's up!" (for casual greetings)
✅ "Everything's good! What do you need?" (for status questions - direct answer)
✅ "I'm doing well! How can I help?" (for greetings with offers - natural, not customer service tone)

OUTPUT:
- Write only the email body (no subject line needed - it's a reply)
- Start your response directly - no formal greetings or thank yous
- Answer their question or respond to their message immediately
- Keep it natural and human-like
- CRITICAL: You MUST end with exactly this format (use actual newlines):
  [your response text]
  
  Best regards,
  {sender_name}
- DO NOT write "Best" alone - it must be "Best regards,"
- DO NOT include email addresses in the signature
- The words "Best regards," must be on their own line, followed by a newline, then the name

Now, write a natural, helpful response that directly addresses their message:

Response:"""
            
            if self.provider == "azure":
                # Re-read deployment from config in case it changed
                if not self.azure_deployment:
                    self.azure_deployment = config.AZURE_OPENAI_DEPLOYMENT
                
                response = self.client.chat.completions.create(
                    model=self.azure_deployment,
                    messages=[
                        {"role": "system", "content": "You are an expert email writing assistant. You write natural, conversational email replies. CRITICAL RULES: NEVER start with 'Thank you for your email', 'I see you reached out about...', or 'How can I help you today?'. NEVER use 'thank you for asking' - just answer directly. NEVER use 'Regarding your question' or 'I received your message'. Always answer questions directly and immediately, as if texting a friend. For 'How are you?' respond with 'I'm doing well! How about you?' - NOT 'I'm doing well, thank you for asking!'. For 'what is your health condition?' respond with 'All good here! How are you?' - NO formal prefaces. ALWAYS end with 'Best regards,' on a separate line, followed by the sender name on the next line. DO NOT include email addresses in signatures."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=1.0,  # Higher temperature for more natural, creative responses
                    max_tokens=400
                )
                response_text = response.choices[0].message.content.strip()
                cleaned_response = self._clean_formal_phrases(response_text, body)
                print(f"🔍 After cleanup - Original length: {len(response_text)}, Cleaned length: {len(cleaned_response)}")
                return cleaned_response
            
            elif self.provider == "openai":
                response = self.client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "You are an expert email writing assistant. You write natural, conversational email replies. CRITICAL RULES: NEVER start with 'Thank you for your email', 'I see you reached out about...', or 'How can I help you today?'. NEVER use 'thank you for asking' - just answer directly. NEVER use 'Regarding your question' or 'I received your message'. Always answer questions directly and immediately, as if texting a friend. For 'How are you?' respond with 'I'm doing well! How about you?' - NOT 'I'm doing well, thank you for asking!'. For 'what is your health condition?' respond with 'All good here! How are you?' - NO formal prefaces. ALWAYS end with 'Best regards,' on a separate line, followed by the sender name on the next line. DO NOT include email addresses in signatures."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=1.0,
                    max_tokens=400
                )
                response_text = response.choices[0].message.content.strip()
                cleaned_response = self._clean_formal_phrases(response_text, body)
                print(f"🔍 After cleanup - Original length: {len(response_text)}, Cleaned length: {len(cleaned_response)}")
                return cleaned_response
            
            elif self.provider == "anthropic":
                response = self.client.messages.create(
                    model="claude-3-haiku-20240307",
                    max_tokens=400,
                    system="You are an expert email writing assistant. You write natural, conversational email replies. CRITICAL: NEVER start with 'Thank you for your email' or 'Hi [Name], Thank you for your email'. NEVER use 'Regarding your question' or 'I received your message'. Always answer questions directly and immediately, as if texting a friend. For 'what is your health condition?' respond with 'All good here! How are you?' - NO formal prefaces. ALWAYS end with 'Best regards,' on a separate line, followed by the sender name on the next line. DO NOT include email addresses in signatures.",
                    messages=[{"role": "user", "content": prompt}]
                )
                response_text = response.content[0].text.strip()
                cleaned_response = self._clean_formal_phrases(response_text, body)
                print(f"🔍 After cleanup - Original length: {len(response_text)}, Cleaned length: {len(cleaned_response)}")
                return cleaned_response
            
        except Exception as e:
            print(f"❌ AI response generation failed: {e}")
            import traceback
            traceback.print_exc()
            # Fall back to improved template response
            return self._template_response(email_data)
    
    def extract_action_items(self, email_data: Dict) -> List[str]:
        """Extract action items from email"""
        body = email_data.get('text_body', '')
        
        # Simple pattern matching for action items
        action_patterns = [
            r'please\s+(\w+\s+){1,5}',
            r'can you\s+(\w+\s+){1,5}',
            r'could you\s+(\w+\s+){1,5}',
            r'need to\s+(\w+\s+){1,5}',
            r'must\s+(\w+\s+){1,5}',
            r'should\s+(\w+\s+){1,5}',
        ]
        
        action_items = []
        for pattern in action_patterns:
            matches = re.finditer(pattern, body, re.IGNORECASE)
            for match in matches:
                action_items.append(match.group(0).strip())
        
        return action_items[:5]  # Limit to top 5
    
    def detect_urgency(self, email_data: Dict) -> tuple:
        """
        Detect urgency level of email
        
        Returns:
            Tuple of (urgency_score, reason) where score is 0-10
        """
        subject = email_data.get('subject', '').lower()
        body = email_data.get('text_body', '').lower()
        
        urgent_keywords = {
            'urgent': 10,
            'emergency': 10,
            'critical': 9,
            'asap': 8,
            'important': 7,
            'immediate': 9,
            'time-sensitive': 8,
            'deadline': 7,
            'priority': 6
        }
        
        max_score = 0
        reason = "Normal priority"
        
        for keyword, score in urgent_keywords.items():
            if keyword in subject:
                if score > max_score:
                    max_score = score
                    reason = f"Subject contains '{keyword}'"
            elif keyword in body:
                if score > max_score:
                    max_score = min(score, 7)  # Lower score if only in body
                    reason = f"Body contains '{keyword}'"
        
        return max_score, reason
    
    def _clean_formal_phrases(self, response_text: str, original_email_body: str = None) -> str:
        """
        Remove formal template phrases and repeated original email content from AI response
        VERY AGGRESSIVE - removes ANY trace of formal templates or repeated content
        """
        try:
            if not response_text:
                return response_text
            
            import re
            
            print(f"🧹 CLEANUP INPUT (first 300 chars): {response_text[:300]}")
            
            # Step 1: Process line-by-line FIRST to remove entire lines with formal phrases
            lines = response_text.split('\n')
            filtered_lines = []
            
            for line in lines:
                line_stripped = line.strip()
                if not line_stripped:
                    continue
                
                line_lower = line_stripped.lower()
                
                # Skip entire lines that contain formal phrases
                skip_line = False
                for phrase in [
                    'thank you for your email',
                    'thank you for asking',
                    'thanks for asking',
                    'i\'m doing well, thank you for asking',  # Specific pattern from user's example
                    'hi ', 'hello ', 'dear ',
                    'regarding',
                    'regarding your question',
                    'regarding the',
                    'i received your message',
                    'i have received your message',
                    'will respond accordingly',
                    # REMOVED: 'best regards' - we want to keep this for signature
                    'sincerely',
                    'i see you reached out',
                    'i see you reached out about',  # Specific pattern from user's example
                    'i see you asked about',
                    'i see you contacted',
                    'i see you reached',
                    'reached out about',
                    'reached out',
                    'let me look into this',
                    'get back to you',
                    'how can i help you today',
                    'how can i help',
                    'i see you reached out about'  # Ensure this is caught
                ]:
                    if phrase in line_lower:
                        skip_line = True
                        break
                
                if skip_line:
                    continue  # Skip this entire line
                
                # Also skip lines that are just repeating original content
                if original_email_body and original_email_body.strip():
                    original_lower = original_email_body.lower().strip()
                    original_words = set(re.sub(r'[^\w\s]', '', original_lower).split())
                    line_words = set(re.sub(r'[^\w\s]', '', line_lower).split())
                    if line_words and original_words:
                        overlap = line_words.intersection(original_words)
                        # If 60%+ of words overlap, skip this line
                        if len(overlap) >= len(line_words) * 0.6:
                            continue
                
                filtered_lines.append(line_stripped)
            
            # Step 2: Join and do aggressive regex cleanup
            cleaned = '\n'.join(filtered_lines).strip()
            
            # Remove ALL formal patterns - very aggressive regex (handle multiline)
            cleaned = re.sub(r'^(Hi|Hello|Dear)\s+\w+[,\s]*\n?', '', cleaned, flags=re.IGNORECASE | re.MULTILINE)
            cleaned = re.sub(r'(Hi|Hello|Dear)\s+\w+[,\s]*\n?', '', cleaned, flags=re.IGNORECASE | re.MULTILINE)
            cleaned = re.sub(r'Thank\s+you\s+for\s+your\s+email[.,]?\s*\n?', '', cleaned, flags=re.IGNORECASE | re.MULTILINE)
            cleaned = re.sub(r'Thank\s+you\s+for\s+asking[.,]?\s*\n?', '', cleaned, flags=re.IGNORECASE | re.MULTILINE)
            cleaned = re.sub(r'Thanks\s+for\s+asking[.,]?\s*\n?', '', cleaned, flags=re.IGNORECASE | re.MULTILINE)
            cleaned = re.sub(r'Thank\s+you\s+for\s+reaching\s+out[.,]?\s*\n?', '', cleaned, flags=re.IGNORECASE | re.MULTILINE)
            cleaned = re.sub(r'Thank\s+you\s+for\s+contacting[.,]?\s*\n?', '', cleaned, flags=re.IGNORECASE | re.MULTILINE)
            cleaned = re.sub(r'Regarding\s+(your\s+question|the)[:\s]*\n?', '', cleaned, flags=re.IGNORECASE | re.MULTILINE)
            cleaned = re.sub(r'Regarding\s+your\s+question[:\s]*\n?', '', cleaned, flags=re.IGNORECASE | re.MULTILINE)
            cleaned = re.sub(r'Let\s+me\s+look\s+into\s+(this|that)[.,]?\s*\n?', '', cleaned, flags=re.IGNORECASE | re.MULTILINE)
            cleaned = re.sub(r'get\s+back\s+to\s+you[.,]?\s*\n?', '', cleaned, flags=re.IGNORECASE | re.MULTILINE)
            cleaned = re.sub(r'I\s+(have\s+)?received\s+your\s+message[.,]?\s*\n?', '', cleaned, flags=re.IGNORECASE | re.MULTILINE)
            cleaned = re.sub(r'I\s+have\s+received\s+your\s+message\s+and\s+will\s+respond\s+accordingly[.,]?\s*\n?', '', cleaned, flags=re.IGNORECASE | re.MULTILINE)
            cleaned = re.sub(r'will\s+respond\s+accordingly[.,]?\s*\n?', '', cleaned, flags=re.IGNORECASE | re.MULTILINE)
            cleaned = re.sub(r'I\s+see\s+you\s+(reached\s+out|contacted)[.,]?\s*\n?', '', cleaned, flags=re.IGNORECASE | re.MULTILINE)
            cleaned = re.sub(r'I\s+see\s+you\s+reached\s+out\s+about[.,]?\s*\n?', '', cleaned, flags=re.IGNORECASE | re.MULTILINE)
            cleaned = re.sub(r'reached\s+out\s+about[.,]?\s*\n?', '', cleaned, flags=re.IGNORECASE | re.MULTILINE)
            cleaned = re.sub(r'How\s+can\s+I\s+help\s+you\s+today[.,]?\s*\n?', '', cleaned, flags=re.IGNORECASE | re.MULTILINE)
            cleaned = re.sub(r'How\s+can\s+I\s+help[.,]?\s*\n?', '', cleaned, flags=re.IGNORECASE | re.MULTILINE)
            # REMOVED: cleaned = re.sub(r'Best\s+regards[.,]?\s*\n?', '', cleaned, flags=re.IGNORECASE | re.MULTILINE)
            # We want to keep "Best regards," for the signature
            cleaned = re.sub(r'Sincerely[.,]?\s*\n?', '', cleaned, flags=re.IGNORECASE | re.MULTILINE)
            cleaned = re.sub(r'Regards[.,]?\s*\n?', '', cleaned, flags=re.IGNORECASE | re.MULTILINE)
            
            # Step 3: Remove repeated original email content
            if original_email_body and original_email_body.strip():
                original_lower = original_email_body.lower().strip()
                original_clean = re.sub(r'[^\w\s]', '', original_lower)
                original_words = original_clean.split()
                
                cleaned_lower = cleaned.lower()
                cleaned_clean = re.sub(r'[^\w\s]', '', cleaned_lower)
                
                # Check for word sequences of 3-7 words from original
                for seq_len in range(7, 2, -1):
                    for i in range(len(original_words) - seq_len + 1):
                        sequence = ' '.join(original_words[i:i+seq_len])
                        if sequence in cleaned_clean:
                            words_pattern = r'\b' + r'\s+'.join([re.escape(w) for w in original_words[i:i+seq_len]]) + r'\b'
                            cleaned = re.sub(words_pattern, '', cleaned, flags=re.IGNORECASE)
                            cleaned_clean = re.sub(re.escape(sequence), '', cleaned_clean, flags=re.IGNORECASE)
            
            # Step 4: Final cleanup - normalize whitespace but preserve signature formatting
            # First, normalize multiple newlines to double newline (for signature separation)
            cleaned = re.sub(r'\n\s*\n\s*\n+', '\n\n', cleaned)
            # Normalize spaces within lines (but keep newlines)
            lines = cleaned.split('\n')
            normalized_lines = []
            for line in lines:
                normalized_line = re.sub(r'[ \t]+', ' ', line.strip())
                if normalized_line:
                    normalized_lines.append(normalized_line)
            cleaned = '\n'.join(normalized_lines)
            
            # Remove email addresses from signature (keep name, remove email)
            # Pattern: email addresses on their own line or at end of line
            cleaned = re.sub(r'\n\s*[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\s*\n?', '', cleaned)
            cleaned = re.sub(r'\s+[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\s*$', '', cleaned)
            
            cleaned = cleaned.strip()
            
            # Step 4.5: Ensure "Best regards," and name are on separate lines
            # Handle various patterns and normalize to "Best regards,\nName"
            
            # Pattern 1: "Best regards, Name" -> "Best regards,\nName"
            cleaned = re.sub(r'(Best\s+regards,)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', r'\1\n\2', cleaned, flags=re.IGNORECASE)
            
            # Pattern 2: "Best regards Name" (without comma) -> "Best regards,\nName"
            cleaned = re.sub(r'(Best\s+regards)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', r'Best regards,\n\2', cleaned, flags=re.IGNORECASE)
            
            # Pattern 3: "Best Name" (missing "regards") -> "Best regards,\nName"
            # This handles cases where AI generates just "Best Name"
            cleaned = re.sub(r'\bBest\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*$', r'Best regards,\n\1', cleaned, flags=re.IGNORECASE | re.MULTILINE)
            
            # Pattern 4: "Best, Name" -> "Best regards,\nName"
            cleaned = re.sub(r'\bBest,\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', r'Best regards,\n\1', cleaned, flags=re.IGNORECASE)
            
            # Step 5: If after all cleanup we have nothing meaningful, return a simple acknowledgment
            if not cleaned or len(cleaned) < 5:
                if original_email_body and 'passed' in original_email_body.lower() and 'exam' in original_email_body.lower():
                    return "That's amazing! Congratulations!"
                return "Thanks for your message!"
            
            print(f"✨ CLEANUP OUTPUT (first 300 chars): {cleaned[:300]}")
            
            return cleaned
        except Exception as e:
            print(f"❌ Cleanup function error: {e}")
            import traceback
            traceback.print_exc()
            return response_text
    
    def analyze_email(self, email_data: Dict) -> Dict:
        """
        Comprehensive AI analysis of an email
        
        Args:
            email_data: Email data dictionary
            
        Returns:
            Dict with comprehensive analysis including category, urgency, spam detection, summary, etc.
        """
        try:
            # Category
            category = self.categorize_email(email_data)
            
            # Urgency
            urgency_score, urgency_reason = self.detect_urgency(email_data)
            
            # Spam detection
            is_spam, spam_confidence = self.is_spam(email_data)
            
            # Summary (including attachment info)
            summary = self.summarize_email(email_data)
            
            # Add attachment information to summary
            if email_data.get('has_attachments') and email_data.get('attachments'):
                attachments = email_data['attachments']
                attachment_summary = self._analyze_attachments(attachments)
                if attachment_summary:
                    summary = f"{summary} {attachment_summary}"
            
            # Action items
            action_items = self.extract_action_items(email_data)
            
            # Sentiment analysis (simple)
            sentiment = self._detect_sentiment(email_data)
            
            # Tags (including attachment-based tags)
            tags = self._generate_tags(email_data, category)
            
            # Key points
            key_points = action_items if action_items else []
            
            # Action required
            action_required = len(action_items) > 0 or urgency_score >= 7
            
            # Suggested response (generate for ALL emails, unless spam)
            suggested_response = ""
            should_generate_response = not is_spam
            
            if should_generate_response:
                try:
                    suggested_response = self.generate_response(email_data, tone="professional")
                except Exception as e:
                    print(f"⚠️  Response generation failed: {e}")
                    suggested_response = ""
            
            return {
                "category": category,
                "urgency_score": urgency_score,
                "is_spam": is_spam,
                "summary": summary,
                "sentiment": sentiment,
                "tags": tags,
                "key_points": key_points,
                "action_required": action_required,
                "suggested_response": suggested_response
            }
        
        except Exception as e:
            print(f"Error in analyze_email: {e}")
            return {
                "category": "other",
                "urgency_score": 5,
                "is_spam": False,
                "summary": email_data.get('subject', 'No summary available'),
                "sentiment": "neutral",
                "tags": [],
                "key_points": [],
                "action_required": False,
                "suggested_response": ""
            }
    
    def _analyze_attachments(self, attachments: List[Dict]) -> str:
        """Analyze attachments and return a summary"""
        if not attachments:
            return ""
        
        count = len(attachments)
        attachment_types = []
        important_types = []
        
        for att in attachments:
            content_type = att.get('content_type', '').lower()
            filename = att.get('filename', '').lower()
            
            # Categorize attachments
            if 'pdf' in content_type or filename.endswith('.pdf'):
                important_types.append('PDF document')
                attachment_types.append('document')
            elif any(ext in filename for ext in ['.doc', '.docx', '.txt', '.rtf']):
                important_types.append('text document')
                attachment_types.append('document')
            elif any(ext in filename for ext in ['.xls', '.xlsx', '.csv']):
                important_types.append('spreadsheet')
                attachment_types.append('document')
            elif any(ext in filename for ext in ['.ppt', '.pptx']):
                important_types.append('presentation')
                attachment_types.append('document')
            elif 'image' in content_type or any(ext in filename for ext in ['.jpg', '.jpeg', '.png', '.gif']):
                attachment_types.append('image')
            elif 'audio' in content_type or any(ext in filename for ext in ['.mp3', '.wav', '.m4a']):
                attachment_types.append('audio')
            elif 'video' in content_type or any(ext in filename for ext in ['.mp4', '.avi', '.mov']):
                attachment_types.append('video')
            elif filename.endswith('.zip') or filename.endswith('.rar'):
                important_types.append('archive')
                attachment_types.append('archive')
            else:
                attachment_types.append('file')
        
        # Build summary
        if important_types:
            types_str = ', '.join(set(important_types))
            return f"Contains {count} attachment(s): {types_str}."
        elif attachment_types:
            return f"Contains {count} attachment(s)."
        else:
            return f"Contains {count} file(s)."
    
    def _detect_sentiment(self, email_data: Dict) -> str:
        """Simple sentiment detection"""
        text = (email_data.get('subject', '') + ' ' + email_data.get('text_body', '')).lower()
        
        positive_words = ['thank', 'great', 'excellent', 'happy', 'pleased', 'wonderful', 'love', 'good']
        negative_words = ['sorry', 'problem', 'issue', 'error', 'fail', 'bad', 'disappoint', 'wrong']
        
        positive_count = sum(1 for word in positive_words if word in text)
        negative_count = sum(1 for word in negative_words if word in text)
        
        if positive_count > negative_count:
            return "positive"
        elif negative_count > positive_count:
            return "negative"
        else:
            return "neutral"
    
    def _generate_tags(self, email_data: Dict, category: str) -> List[str]:
        """Generate relevant tags for the email"""
        tags = [category]
        
        subject = email_data.get('subject', '').lower()
        body = email_data.get('text_body', '').lower()
        text = subject + ' ' + body
        
        # Add tags based on content
        tag_keywords = {
            'meeting': ['meeting', 'call', 'conference'],
            'deadline': ['deadline', 'due', 'by'],
            'invoice': ['invoice', 'payment', 'bill'],
            'report': ['report', 'summary', 'analysis'],
            'question': ['?', 'how', 'what', 'when', 'where', 'why'],
            'request': ['please', 'could you', 'can you', 'need'],
        }
        
        for tag, keywords in tag_keywords.items():
            if any(keyword in text for keyword in keywords):
                tags.append(tag)
        
        # Add attachment-based tags
        if email_data.get('has_attachments') and email_data.get('attachments'):
            tags.append('has-attachment')
            attachments = email_data['attachments']
            
            for att in attachments:
                filename = att.get('filename', '').lower()
                content_type = att.get('content_type', '').lower()
                
                if 'pdf' in content_type or filename.endswith('.pdf'):
                    tags.append('pdf')
                elif 'image' in content_type:
                    tags.append('image')
                elif any(ext in filename for ext in ['.doc', '.docx']):
                    tags.append('document')
                elif any(ext in filename for ext in ['.xls', '.xlsx', '.csv']):
                    tags.append('spreadsheet')
        
        return list(set(tags))[:7]  # Return max 7 unique tags
    
    def is_spam(self, email_data: Dict) -> tuple:
        """
        Detect if email is likely spam
        
        Returns:
            Tuple of (is_spam: bool, confidence: float)
        """
        subject = email_data.get('subject', '').lower()
        body = email_data.get('text_body', '').lower()
        from_email = email_data.get('from', '').lower()
        
        spam_indicators = 0
        total_checks = 0
        
        # Check 1: Spam keywords
        spam_keywords = ['viagra', 'lottery', 'winner', 'congratulations', 
                        'click here', 'limited time', 'act now', 'free money']
        total_checks += 1
        if any(keyword in subject or keyword in body for keyword in spam_keywords):
            spam_indicators += 1
        
        # Check 2: Excessive caps
        total_checks += 1
        if subject and sum(1 for c in subject if c.isupper()) / len(subject) > 0.5:
            spam_indicators += 1
        
        # Check 3: Suspicious links
        total_checks += 1
        if body.count('http') > 3 or 'bit.ly' in body or 'tinyurl' in body:
            spam_indicators += 1
        
        # Check 4: No personal greeting
        total_checks += 1
        greeting_words = ['dear', 'hello', 'hi', 'greetings']
        if not any(word in body[:100] for word in greeting_words):
            spam_indicators += 1
        
        confidence = spam_indicators / total_checks
        is_spam = confidence > 0.5
        
        return is_spam, confidence

