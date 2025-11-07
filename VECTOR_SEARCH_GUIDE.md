# 🔍 Vector Database & Semantic Search Guide

Your Email Agent now includes **ChromaDB** for powerful semantic search capabilities!

## 🎯 What is Vector Search?

Traditional search looks for exact keyword matches. Vector search understands **meaning** using AI embeddings.

### Example:
```
Traditional: "budget proposal" → Only finds emails with those exact words
Semantic: "financial plan" → Finds emails about budgets, proposals, finances, spending, etc.
```

## ✨ Features Added

### 1. **Automatic Email Indexing**
- ✅ Every email is automatically converted to embeddings
- ✅ Stored in ChromaDB (in-memory)
- ✅ Ready for instant semantic search

### 2. **Semantic Search**
Find emails by meaning, not keywords:
- "urgent deadlines" → Finds all urgent emails about deadlines
- "meeting notes" → Finds meeting summaries, agendas, notes
- "project updates" → Finds status reports, progress emails

### 3. **Similar Email Detection**
- Find emails similar to a given email
- Detect potential duplicates
- Group related conversations

### 4. **Smart Chat Context**
- Chat AI uses vector search to find relevant emails
- Only sends pertinent emails to AI (saves tokens!)
- More accurate responses

## 🚀 How It Works

### Auto-Indexing
```python
# When you load emails:
1. Emails fetched from Gmail
2. Email content + metadata → Text
3. Text → Vector embeddings (AI)
4. Embeddings stored in ChromaDB
```

### Semantic Search Process
```python
1. User query: "project deadlines"
2. Query → Vector embedding
3. Find similar vectors in database
4. Return most relevant emails
```

## 📊 API Endpoints

### 1. Semantic Search
```bash
POST /api/search/semantic
{
  "query": "urgent project deadlines",
  "n_results": 10
}
```

**Response:**
```json
{
  "success": true,
  "query": "urgent project deadlines",
  "results": [
    {
      "id": "email_hash",
      "distance": 0.15,
      "metadata": {
        "subject": "Q4 Project Deadline - URGENT",
        "from": "manager@company.com",
        "category": "urgent"
      },
      "document": "Full email content..."
    }
  ],
  "count": 10
}
```

### 2. Find Similar Emails
```bash
POST /api/search/similar/{email_id}?n_results=5
```

Finds emails similar to a specific email.

### 3. Get Vector Stats
```bash
GET /api/search/stats
```

**Response:**
```json
{
  "success": true,
  "total_emails": 150,
  "collection_name": "emails"
}
```

### 4. Clear Vector Store
```bash
DELETE /api/search/clear
```

Clears all indexed emails (useful when switching accounts).

## 💡 Use Cases

### 1. Natural Language Search
Instead of remembering exact keywords:
