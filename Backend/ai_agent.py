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
        if config.USE_AZURE_OPENAI and self.provider == "azure":
            try:
                from openai import AzureOpenAI
                
                # Check if Azure OpenAI credentials are configured
                if not config.AZURE_OPENAI_KEY or not config.AZURE_OPENAI_ENDPOINT:
                    print("⚠ Azure OpenAI credentials not configured. Check .env file for AZURE_OPENAI_KEY and AZURE_OPENAI_ENDPOINT")
                else:
                    self.client = AzureOpenAI(
                        api_key=config.AZURE_OPENAI_KEY,
                        api_version=config.AZURE_OPENAI_API_VERSION,
                        azure_endpoint=config.AZURE_OPENAI_ENDPOINT
                    )
                    self.azure_deployment = config.AZURE_OPENAI_DEPLOYMENT
                    print(f"✓ Azure OpenAI client initialized (deployment: {self.azure_deployment})")
                    print(f"  Endpoint: {config.AZURE_OPENAI_ENDPOINT[:50]}...")
            except ImportError:
                print("⚠ OpenAI package not installed. Run: pip install openai")
                self.client = None
            except Exception as e:
                print(f"⚠ Could not initialize Azure OpenAI client: {e}")
                import traceback
                traceback.print_exc()
                self.client = None
        
        # Initialize regular OpenAI client
        elif self.provider == "openai":
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
            return self._ai_generate_response(email_data, tone)
        else:
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
            
            prompt = f"""You are an intelligent email assistant. Your task is to analyze the email below and generate a thoughtful, contextual response.

ANALYSIS PROCESS:
1. First, carefully read and understand the SUBJECT line - what is the main topic?
2. Then, analyze the BODY content - what is the sender actually saying, asking, or requesting?
3. Identify the intent: Is it a question? A request? Information sharing? A greeting? A complaint?
4. Consider the context and tone of the original message
5. Generate an appropriate response that directly addresses what they said

EMAIL TO ANALYZE:
From: {from_name} ({from_email})
Subject: {subject}
Body: {body}

CRITICAL REQUIREMENTS:
- DO NOT use generic phrases like "Thank you for your email regarding [subject]"
- DO NOT give a static/template response
- DO analyze what they're actually saying and respond to THAT
- DO be specific and address their actual message content
- DO match the tone - if they're casual, be friendly; if formal, be professional
- DO answer questions if asked, acknowledge requests, respond to greetings naturally
- Keep it concise (3-5 sentences) but meaningful and contextual
- Sign as "{sender_name}" from {sender_email}
- Do NOT include subject line or placeholders

Think about what they're really saying, then write a natural, helpful response:

Response:"""
            
            if self.provider == "azure":
                response = self.client.chat.completions.create(
                    model=self.azure_deployment,
                    messages=[
                        {"role": "system", "content": "You are an intelligent email assistant that analyzes emails deeply and generates thoughtful, contextual responses. Always read the subject and body carefully, understand the intent, and respond appropriately - never use generic templates."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.8,  # Slightly higher for more natural responses
                    max_tokens=400  # Increased for more detailed responses
                )
                return response.choices[0].message.content.strip()
            
            elif self.provider == "openai":
                response = self.client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "You are an intelligent email assistant that analyzes emails deeply and generates thoughtful, contextual responses. Always read the subject and body carefully, understand the intent, and respond appropriately - never use generic templates."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.8,
                    max_tokens=400
                )
                return response.choices[0].message.content.strip()
            
            elif self.provider == "anthropic":
                response = self.client.messages.create(
                    model="claude-3-haiku-20240307",
                    max_tokens=400,
                    system="You are an intelligent email assistant that analyzes emails deeply and generates thoughtful, contextual responses. Always read the subject and body carefully, understand the intent, and respond appropriately - never use generic templates.",
                    messages=[{"role": "user", "content": prompt}]
                )
                return response.content[0].text.strip()
            
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

