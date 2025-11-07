"""
Test script for Chat Agent
Run this to test the chat functionality
"""

from chat_agent import ChatAgent
from email_receiver import EmailReceiver
import config


def main():
    print("="*80)
    print("EMAIL CHAT AGENT - TEST")
    print("="*80)
    
    # Initialize chat agent
    print("\n1. Initializing Chat Agent...")
    chat = ChatAgent()
    
    if not chat.client:
        print("❌ Chat agent failed to initialize. Check Azure OpenAI configuration.")
        return
    
    # Connect to email and load some emails
    print("\n2. Loading email context...")
    receiver = EmailReceiver()
    
    if not receiver.connect():
        print("❌ Failed to connect to email server.")
        return
    
    emails = receiver.get_emails(limit=5)
    receiver.disconnect()
    
    print(f"✓ Loaded {len(emails)} emails")
    
    # Set context
    chat.set_email_context(emails)
    
    # Get suggestions
    print("\n3. Getting suggested questions...")
    suggestions = chat.suggest_questions()
    print("\nSuggested questions:")
    for idx, suggestion in enumerate(suggestions, 1):
        print(f"  {idx}. {suggestion}")
    
    # Test conversation
    print("\n4. Testing conversation...")
    print("\n" + "="*80)
    
    test_questions = [
        "How many emails do I have?",
        "What's the subject of the first email?",
        "Are there any urgent emails?"
    ]
    
    for question in test_questions:
        print(f"\n👤 You: {question}")
        result = chat.chat(question)
        
        if result.get('error'):
            print(f"❌ Error: {result['response']}")
        else:
            print(f"🤖 AI: {result['response']}")
            if result.get('tokens_used'):
                print(f"   (Tokens used: {result['tokens_used']})")
    
    print("\n" + "="*80)
    print("✅ Chat Agent Test Complete!")
    print("="*80)


if __name__ == "__main__":
    main()

