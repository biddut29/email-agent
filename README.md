# 🤖 Email Agent - AI-Powered Email Management System

A full-stack email management system with AI capabilities, featuring automated email analysis, smart responses, and a modern web interface.

## 🌟 Features

### Backend (Python)
- 📥 **Email Retrieval**: IMAP integration with Gmail
- 📤 **Email Sending**: SMTP support with attachments
- 🤖 **Azure OpenAI Integration**: GPT-4 powered features
- 🏷️ **Smart Categorization**: Automatic email classification
- 📊 **Email Analytics**: Statistics and insights
- 🔍 **Advanced Search**: Search by sender, subject, keywords
- ⚡ **RESTful API**: FastAPI-based backend
- 🛡️ **Spam Detection**: AI-powered spam filtering
- 📝 **Auto-Summarization**: Email content summaries
- ✨ **AI Response Generation**: Context-aware email replies

### Frontend (Next.js)
- 💎 **Modern UI**: Built with Shadcn UI components
- 🎨 **Tailwind CSS**: Beautiful, responsive design
- 🌙 **Dark Mode**: Full dark mode support
- ⚡ **Real-time Updates**: Live email management
- 📱 **Responsive**: Mobile-friendly interface
- 🔄 **Interactive Dashboard**: Intuitive email management
- 💬 **AI Chat**: Conversational email assistant powered by Azure OpenAI

## 🏗️ Architecture

```
Email Agent/
├── Backend/                 # Python FastAPI backend
│   ├── config.py           # Configuration (Azure OpenAI, Gmail)
│   ├── email_receiver.py   # IMAP email retrieval
│   ├── email_sender.py     # SMTP email sending
│   ├── ai_agent.py         # Azure OpenAI integration
│   ├── email_agent.py      # Main orchestrator
│   ├── api_server.py       # FastAPI REST API
│   └── requirements.txt    # Python dependencies
│
└── Frontend/               # Next.js 15 frontend
    ├── app/               # Next.js app directory
    ├── components/        # React components
    ├── lib/              # Utilities and API client
    └── package.json      # Node dependencies
```

## 🚀 Quick Start

### Prerequisites

- Python 3.9+
- Node.js 18+
- Gmail account with App Password
- Azure OpenAI access (already configured)

### 1. Backend Setup

```bash
cd Backend

# Install dependencies
pip install -r requirements.txt

# Configuration is already set in config.py with:
# - Email: bidduttest@gmail.com
# - Azure OpenAI endpoint and key configured

# Start the API server
python api_server.py
```

Backend will run at: **http://localhost:8000**

API docs: **http://localhost:8000/docs**

### 2. Frontend Setup

```bash
cd Frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

Frontend will run at: **http://localhost:3000**

### 3. Access the Application

Open your browser and navigate to:
- **Dashboard**: http://localhost:3000
- **API Docs**: http://localhost:8000/docs

## 📖 Usage Guide

### Using the Web Interface

1. **Load Emails**
   - Click "Load Emails" to fetch recent emails
   - Switch to "Unread" tab for unread emails only

2. **View Email Details**
   - Click any email in the list
   - See full content and AI analysis
   - View categorization, urgency, and summary

3. **Generate AI Response**
   - Select an email
   - Click "Generate AI Response"
   - AI creates a contextual reply
   - Edit if needed and send

4. **Search Emails**
   - Go to Search tab
   - Enter keywords, sender, or subject
   - View filtered results

5. **Chat with Your Emails** ⭐ NEW!
   - Go to Chat tab
   - Ask questions about your emails
   - Get AI-powered insights and responses
   - Draft replies conversationally

6. **View Statistics**
   - Go to Statistics tab
   - Click "Load Statistics"
   - See email analytics and insights

### Using the Python CLI

```bash
cd Backend
python email_agent.py
```

Interactive menu options:
1. Process inbox
2. Process unread emails only
3. Search by sender
4. Search by subject
5. Generate AI responses
6. Send new email
7. Show statistics
8. Export emails
9. Exit

### Using the API Directly

```bash
# Get emails
curl http://localhost:8000/api/emails?limit=10

# Get unread emails
curl http://localhost:8000/api/emails/unread

# Generate AI response
curl -X POST http://localhost:8000/api/emails/generate-response?email_id=123

# Send email
curl -X POST http://localhost:8000/api/emails/send \
  -H "Content-Type: application/json" \
  -d '{"to":"recipient@example.com","subject":"Hello","body":"Test email"}'
```

## 🔑 Configuration

### Backend Configuration (`Backend/config.py`)

```python
# Email Settings (Already configured)
EMAIL_ADDRESS = "bidduttest@gmail.com"
EMAIL_PASSWORD = "lvvftahuyrbldpcd"

# Azure OpenAI (Already configured)
USE_AZURE_OPENAI = True
AZURE_OPENAI_ENDPOINT = "https://email-agent-test-ai-foundry.cognitiveservices.azure.com"
AZURE_OPENAI_KEY = "EU8IZT..."
AZURE_OPENAI_DEPLOYMENT = "gpt-4.1-mini"

# Agent Settings
DEFAULT_MAILBOX = "INBOX"
MAX_EMAILS_TO_PROCESS = 10
AUTO_RESPOND = False
DRAFT_MODE = True
```

### Frontend Configuration (`Frontend/.env.local`)

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## 🤖 AI Capabilities

### Email Categorization
- Urgent
- Important  
- Spam
- Promotional
- Personal
- Work
- Newsletter
- Other

### AI Analysis Features
- **Urgency Detection**: 0-10 score with reasoning
- **Spam Detection**: Confidence-based spam filtering
- **Summarization**: Concise email summaries
- **Action Items**: Extracted tasks and to-dos
- **Response Generation**: Context-aware replies

## 📊 API Endpoints

### Emails
- `GET /api/emails` - Get emails
- `GET /api/emails/unread` - Get unread emails
- `GET /api/emails/{email_id}` - Get single email
- `POST /api/emails/send` - Send email
- `POST /api/emails/reply` - Reply to email
- `PUT /api/emails/{email_id}/read` - Mark as read

### AI Features
- `POST /api/emails/analyze` - Analyze email with AI
- `POST /api/emails/generate-response` - Generate AI response

### Search & Stats
- `POST /api/emails/search` - Search emails
- `GET /api/statistics` - Get statistics
- `GET /api/folders` - List email folders
- `GET /api/health` - Health check

## 🛠️ Development

### Backend Development

```bash
cd Backend

# Install dev dependencies
pip install -r requirements.txt

# Run with auto-reload
uvicorn api_server:app --reload

# Run CLI
python email_agent.py
```

### Frontend Development

```bash
cd Frontend

# Install dependencies
npm install

# Run dev server
npm run dev

# Add Shadcn components
npx shadcn@latest add [component-name]

# Build for production
npm run build
```

## 🔒 Security Notes

- ✅ Azure OpenAI credentials configured
- ✅ Gmail App Password (not main password)
- ✅ 2-Factor Authentication enabled
- ⚠️ Don't commit sensitive credentials to git
- ⚠️ Use environment variables in production

## 🐛 Troubleshooting

### Backend Issues

**Connection Error**
```bash
# Check Gmail IMAP/SMTP is enabled
# Verify app password is correct
# Ensure 2FA is enabled on Gmail account
```

**Azure OpenAI Error**
```bash
# Credentials are already configured
# Check Azure endpoint is accessible
# Verify deployment name is correct
```

### Frontend Issues

**API Connection Failed**
```bash
# Ensure backend is running on port 8000
# Check .env.local has correct API URL
# Verify CORS is enabled in backend
```

**Component Not Found**
```bash
# Install missing Shadcn component
npx shadcn@latest add [component-name]
```

## 📚 Tech Stack

### Backend
- **Python 3.9+**
- **FastAPI** - Modern web framework
- **Azure OpenAI** - GPT-4 integration
- **IMAP/SMTP** - Email protocols
- **Uvicorn** - ASGI server

### Frontend
- **Next.js 15** - React framework
- **TypeScript** - Type safety
- **Shadcn UI** - Component library
- **Tailwind CSS v4** - Styling
- **Lucide React** - Icons

## 📝 License

MIT License

## 🙏 Credits

- Azure OpenAI for AI capabilities
- Shadcn UI for beautiful components
- Next.js team for amazing framework
- FastAPI for the excellent Python framework

## 📧 Support

For issues or questions:
1. Check the troubleshooting section
2. Review API documentation at `/docs`
3. Check backend/frontend README files

---

**Made with ❤️ using Azure OpenAI GPT-4**

