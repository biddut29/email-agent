# Email Agent - Backend

A powerful Python-based email agent with AI capabilities for automated email management.

## Features

- 📥 **Email Retrieval**: Fetch emails via IMAP from Gmail
- 📤 **Email Sending**: Send emails via SMTP with attachments support
- 🤖 **AI Analysis**: 
  - Email categorization (urgent, spam, personal, work, etc.)
  - Automatic summarization
  - Urgency detection
  - Spam detection
  - Action item extraction
- 🔄 **Auto-Response**: AI-generated email responses
- 🔍 **Email Search**: Search by sender, subject, or custom criteria
- 📊 **Statistics**: Email analytics and insights
- 💾 **Export**: Export emails to JSON

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Email Credentials

Edit `config.py`:

```python
EMAIL_ADDRESS = "your-email@gmail.com"
EMAIL_PASSWORD = "your-app-password"  # Gmail App Password

# Optional: Add AI API keys
OPENAI_API_KEY = "your-openai-key"  # For AI features
```

### 3. Gmail App Password Setup

1. Go to [Google Account Settings](https://myaccount.google.com/)
2. Security → 2-Step Verification (enable if not already)
3. App Passwords → Generate new app password
4. Copy the password to `config.py`

## Usage

### Basic Usage

```python
from email_agent import EmailAgent

# Initialize agent
agent = EmailAgent(ai_enabled=True)
agent.start()

# Process inbox
agent.process_inbox(limit=10, unread_only=True)

# Show statistics
agent.print_statistics()

# Generate AI responses
agent.auto_respond_to_emails(tone="professional")

agent.stop()
```

### Interactive Mode

```bash
python email_agent.py
```

This launches an interactive CLI with options to:
- Process inbox
- Search emails
- Generate AI responses
- Send emails
- View statistics
- Export data

### API Server

Run the FastAPI server:

```bash
python api_server.py
```

API will be available at `http://localhost:8000`

API Documentation: `http://localhost:8000/docs`

## API Endpoints

- `GET /api/emails` - Get emails
- `GET /api/emails/unread` - Get unread emails
- `POST /api/emails/send` - Send an email
- `POST /api/emails/reply` - Reply to an email
- `POST /api/emails/analyze` - AI analysis of an email
- `GET /api/emails/search` - Search emails
- `GET /api/statistics` - Get email statistics

## Project Structure

```
Backend/
├── config.py              # Configuration
├── email_receiver.py      # IMAP email retrieval
├── email_sender.py        # SMTP email sending
├── ai_agent.py           # AI-powered features
├── email_agent.py        # Main orchestrator
├── api_server.py         # FastAPI REST API
└── requirements.txt      # Dependencies
```

## AI Features

The agent supports multiple AI providers:

### OpenAI (GPT)

```python
agent = EmailAgent(ai_enabled=True, ai_provider="openai")
```

### Anthropic (Claude)

```python
agent = EmailAgent(ai_enabled=True, ai_provider="anthropic")
```

### Rule-Based (No API Key Required)

```python
agent = EmailAgent(ai_enabled=False)
```

## Configuration Options

In `config.py`:

- `EMAIL_ADDRESS`: Your Gmail address
- `EMAIL_PASSWORD`: Your Gmail app password
- `AUTO_RESPOND`: Enable/disable automatic responses
- `DRAFT_MODE`: Create drafts instead of sending
- `MAX_EMAILS_TO_PROCESS`: Default email processing limit
- `EMAIL_CATEGORIES`: Custom email categories

## Security Notes

- Never commit `config.py` with real credentials
- Use environment variables in production
- Enable 2-Factor Authentication on Gmail
- Use app-specific passwords, not your main password

## Troubleshooting

### Connection Issues
- Verify Gmail IMAP/SMTP is enabled
- Check app password is correct
- Ensure 2FA is enabled

### AI Features Not Working
- Install AI libraries: `pip install openai` or `pip install anthropic`
- Add API keys to `config.py`
- Check API key validity

## License

MIT License

