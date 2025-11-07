# 💬 Email Chat Assistant - User Guide

Your Email Agent now includes an AI-powered chat feature using **Azure OpenAI GPT-4.1-mini**!

## 🎯 What is Email Chat?

The Email Chat Assistant lets you have natural conversations about your emails. Instead of manually browsing through emails, just ask questions in plain English and get intelligent responses powered by Azure OpenAI.

## ✨ Key Features

### 🤖 Conversational AI
- Natural language understanding
- Context-aware responses
- Remembers conversation history
- Powered by Azure OpenAI GPT-4.1-mini

### 📧 Email-Aware
- Accesses all loaded emails
- Understands email content, senders, subjects
- Uses AI analysis data (urgency, categories, summaries)
- Provides specific email references

### 💡 Smart Suggestions
- Auto-generates relevant questions
- Context-based recommendations
- Quick-start conversation prompts

## 🚀 How to Use

### Step 1: Load Emails
```
1. Go to the "Inbox" tab
2. Click "Load Emails"
3. Wait for emails to load
```

### Step 2: Open Chat
```
1. Click on the "Chat" tab
2. You'll see suggested questions
3. Start chatting!
```

### Step 3: Ask Questions
Type any question about your emails:
- "What are my most urgent emails?"
- "Summarize emails from John"
- "Are there any emails I need to respond to?"
- "Find emails about the project deadline"
- "Draft a reply to the latest email"

## 💬 Example Conversations

### Finding Urgent Emails
```
You: What are my most urgent emails?

AI: I found 2 urgent emails:

Email 1: From Sarah Johnson about "Project Deadline - URGENT"
- Urgency: 9/10
- Summary: Sarah needs the Q4 report by end of week
- Action: Respond with timeline

Email 2: From IT Support about "Security Update Required"
- Urgency: 8/10  
- Summary: Critical security patch needed within 24 hours
- Action: Schedule maintenance window
```

### Summarizing Emails
```
You: Summarize today's emails

AI: You received 6 emails today:

📬 Work (3):
- Team meeting notes from Mike
- Budget approval from Finance
- Project update from Sarah (URGENT)

📧 Personal (2):
- Newsletter from TechNews
- Promotion email from Amazon

🚨 Spam (1):
- Lottery winner notification (marked as spam)

Priority action: Respond to Sarah's urgent project email.
```

### Drafting Replies
```
You: Draft a reply to the email from Sarah

AI: Here's a professional reply:

---
Hi Sarah,

Thank you for the urgent update on the project deadline. I've reviewed the requirements and can deliver the Q4 report by Friday EOD.

I'll prioritize this and send you a draft by Wednesday for review. Please let me know if you need any specific sections highlighted.

Best regards
---

Would you like me to adjust the tone or add anything?
```

## 🎨 Interface Features

### Message Types
- **Your Messages**: Blue bubbles on the right
- **AI Responses**: Gray bubbles on the left with bot icon
- **Loading State**: Animated "Thinking..." indicator

### Quick Actions
- **Suggested Questions**: Click to ask instantly
- **Clear Chat**: Reset conversation history
- **Auto-Scroll**: Always see latest messages

### Smart Context
- Chat updates when you load new emails
- Badge shows number of emails in context
- Seamless integration with email list

## 📝 Example Questions You Can Ask

### Email Discovery
- "Show me all emails from [sender]"
- "What emails did I receive today?"
- "Find emails mentioning [keyword]"
- "Which emails have attachments?"

### Analysis & Insights
- "What's the most important email?"
- "Summarize my unread emails"
- "Are there any urgent emails?"
- "What emails need responses?"

### Email Management
- "Draft a reply to [sender]"
- "Summarize the email about [topic]"
- "What action items are in my emails?"
- "Who has emailed me the most?"

### Content Search
- "Find emails about the budget"
- "Show me emails from last week"
- "What did John say about the project?"
- "Are there any meeting invitations?"

## 🛠️ Technical Details

### Backend (Python)
- **File**: `Backend/chat_agent.py`
- **API**: Azure OpenAI GPT-4.1-mini
- **Endpoints**: `/api/chat/*`
- **Context**: Uses loaded email data
- **History**: Maintains last 20 messages

### Frontend (Next.js)
- **Component**: `Frontend/components/EmailChat.tsx`
- **UI**: Shadcn components
- **Real-time**: Instant responses
- **Responsive**: Works on all devices

### API Endpoints

#### POST `/api/chat/message`
Send a message to the chat agent
```json
{
  "message": "What are my urgent emails?",
  "include_context": true
}
```

#### POST `/api/chat/context`
Update email context
```json
{
  "emails": [...]
}
```

#### POST `/api/chat/reset`
Clear conversation history

#### GET `/api/chat/suggestions`
Get suggested questions

#### GET `/api/chat/history`
Get conversation history

## ⚙️ Configuration

The chat feature uses your existing Azure OpenAI configuration from `.env`:

```bash
# Backend/.env
USE_AZURE_OPENAI=True
AZURE_OPENAI_ENDPOINT=https://your-endpoint.cognitiveservices.azure.com
AZURE_OPENAI_KEY=your-key-here
AZURE_OPENAI_DEPLOYMENT=gpt-4.1-mini
```

## 🎯 Best Practices

### For Best Results:
1. **Load emails first** - Chat needs context
2. **Be specific** - "Email from John about budget" vs "emails"
3. **Ask follow-ups** - Chat remembers conversation
4. **Use suggestions** - Quick-start questions
5. **Clear when needed** - Reset for new topics

### Tips:
- ✅ "Summarize the email from Sarah about the deadline"
- ✅ "What are my top 3 urgent emails?"
- ✅ "Draft a professional reply"
- ❌ "emails" (too vague)
- ❌ "stuff" (no context)

## 🔒 Privacy & Security

- ✅ Emails stay on your Gmail server
- ✅ Only loaded emails sent to AI
- ✅ Conversation history stored in memory
- ✅ No permanent storage of messages
- ✅ Reset clears all history

## 🐛 Troubleshooting

### "Chat agent not initialized"
**Solution**: Check Azure OpenAI credentials in `.env`

### "Load some emails first"
**Solution**: Go to Inbox tab and click "Load Emails"

### Chat responses are slow
**Solution**: Normal for GPT-4, responses typically take 2-5 seconds

### Chat gives generic responses
**Solution**: Ensure emails are loaded and context is updated

## 🚀 Advanced Usage

### Context Management
The chat automatically updates its context when you:
- Load new emails
- Switch folders
- Refresh the inbox

### Conversation Flow
```
1. Load emails (context created)
2. Ask question (uses context)
3. Get response (with email references)
4. Ask follow-up (remembers context)
5. Clear chat (reset conversation)
```

### Integration with Email Actions
After chatting, you can:
- Click on suggested email numbers to view
- Use generated drafts in reply interface
- Take actions based on AI insights

## 🎓 Learning the System

### Start Simple
```
1. "What emails do I have?"
2. "Tell me about Email 1"
3. "Are there any urgent ones?"
```

### Get More Specific
```
1. "Summarize emails from my manager"
2. "What project deadlines are mentioned?"
3. "Draft replies to urgent emails"
```

### Advanced Queries
```
1. "Compare the two budget proposals"
2. "Extract all meeting times from today's emails"
3. "What's the consensus on the new policy?"
```

## 📊 Chat Statistics

Each chat response includes:
- **Token Usage**: API consumption tracking
- **Response Time**: Typically 2-5 seconds
- **Context Size**: Number of emails used
- **Conversation Length**: Message count

## 🎉 Use Cases

### Daily Email Triage
```
Morning routine:
1. Load overnight emails
2. Ask: "What's urgent?"
3. Ask: "Summarize the rest"
4. Take action on priorities
```

### Quick Research
```
Finding information:
1. "Find all emails about [topic]"
2. "What did [person] say about [subject]?"
3. "When was [event] mentioned?"
```

### Response Assistance
```
Drafting replies:
1. "Draft a reply to [sender]"
2. "Make it more formal"
3. "Add deadline information"
4. Copy and use in email
```

## 🆘 Getting Help

If you encounter issues:
1. Check Backend terminal for errors
2. Verify Azure OpenAI is responding
3. Ensure emails are loaded
4. Try resetting the chat
5. Reload the page

## 🎊 Enjoy Your AI Email Assistant!

The Email Chat feature transforms how you interact with your inbox. Instead of searching through emails manually, just ask and let AI do the work!

**Pro Tip**: The more specific your question, the better the response. Happy chatting! 🚀

