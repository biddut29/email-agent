'use client';

import { useState, useEffect, useRef } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Badge } from '@/components/ui/badge';
import { Bot, Send, Trash2, Sparkles, User, Loader2 } from 'lucide-react';

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

interface EmailChatProps {
  emails: any[];
}

export default function EmailChat({ emails }: EmailChatProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  // Auto-scroll to bottom
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Update chat context when emails change
  useEffect(() => {
    if (emails.length > 0) {
      updateChatContext();
      loadSuggestions();
    }
  }, [emails]);

  const updateChatContext = async () => {
    try {
      await fetch(`${apiUrl}/api/chat/context`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ emails }),
      });
    } catch (error) {
      console.error('Failed to update chat context:', error);
    }
  };

  const loadSuggestions = async () => {
    try {
      const response = await fetch(`${apiUrl}/api/chat/suggestions`);
      const data = await response.json();
      if (data.success) {
        setSuggestions(data.suggestions);
      }
    } catch (error) {
      console.error('Failed to load suggestions:', error);
    }
  };

  const sendMessage = async (messageText?: string) => {
    const textToSend = messageText || input.trim();
    if (!textToSend) return;

    // Add user message
    const userMessage: Message = { role: 'user', content: textToSend };
    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      const response = await fetch(`${apiUrl}/api/chat/message`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: textToSend,
          include_context: true,
        }),
      });

      const data = await response.json();

      if (data.success) {
        const assistantMessage: Message = {
          role: 'assistant',
          content: data.response,
        };
        setMessages((prev) => [...prev, assistantMessage]);
      } else {
        throw new Error(data.response || 'Failed to get response');
      }
    } catch (error: any) {
      const errorMessage: Message = {
        role: 'assistant',
        content: `Sorry, I encountered an error: ${error.message}`,
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  const resetConversation = async () => {
    try {
      await fetch(`${apiUrl}/api/chat/reset`, {
        method: 'POST',
      });
      setMessages([]);
      loadSuggestions();
    } catch (error) {
      console.error('Failed to reset conversation:', error);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="h-[calc(100vh-250px)] flex flex-col">
      <Card className="flex-1 flex flex-col">
        <CardHeader className="border-b">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Bot className="w-5 h-5 text-primary" />
                Email Chat Assistant
              </CardTitle>
              <CardDescription>
                Ask me anything about your emails using Azure OpenAI
              </CardDescription>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={resetConversation}
              disabled={messages.length === 0}
            >
              <Trash2 className="w-4 h-4 mr-2" />
              Clear Chat
            </Button>
          </div>
        </CardHeader>

        <CardContent className="flex-1 flex flex-col p-0">
          {/* Messages Area */}
          <ScrollArea className="flex-1 p-4">
            {messages.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-center space-y-6 p-8">
                <div className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center">
                  <Bot className="w-8 h-8 text-primary" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold mb-2">
                    Start a conversation!
                  </h3>
                  <p className="text-sm text-muted-foreground mb-4">
                    {emails.length > 0
                      ? `I have access to ${emails.length} email${emails.length !== 1 ? 's' : ''}. Ask me anything!`
                      : 'Load some emails first, then ask me questions about them.'}
                  </p>
                </div>

                {/* Suggested Questions */}
                {suggestions.length > 0 && (
                  <div className="w-full max-w-md space-y-2">
                    <p className="text-xs text-muted-foreground font-medium">
                      Try asking:
                    </p>
                    <div className="grid gap-2">
                      {suggestions.map((suggestion, idx) => (
                        <Button
                          key={idx}
                          variant="outline"
                          size="sm"
                          className="text-left justify-start h-auto py-2 px-3"
                          onClick={() => sendMessage(suggestion)}
                        >
                          <Sparkles className="w-3 h-3 mr-2 shrink-0" />
                          <span className="text-xs">{suggestion}</span>
                        </Button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="space-y-4">
                {messages.map((message, idx) => (
                  <div
                    key={idx}
                    className={`flex gap-3 ${
                      message.role === 'user' ? 'justify-end' : 'justify-start'
                    }`}
                  >
                    {message.role === 'assistant' && (
                      <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
                        <Bot className="w-4 h-4 text-primary" />
                      </div>
                    )}

                    <div
                      className={`max-w-[80%] rounded-lg px-4 py-2 ${
                        message.role === 'user'
                          ? 'bg-primary text-primary-foreground'
                          : 'bg-muted'
                      }`}
                    >
                      <p className="text-sm whitespace-pre-wrap">
                        {message.content}
                      </p>
                    </div>

                    {message.role === 'user' && (
                      <div className="w-8 h-8 rounded-full bg-primary flex items-center justify-center shrink-0">
                        <User className="w-4 h-4 text-primary-foreground" />
                      </div>
                    )}
                  </div>
                ))}

                {loading && (
                  <div className="flex gap-3">
                    <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
                      <Bot className="w-4 h-4 text-primary" />
                    </div>
                    <div className="bg-muted rounded-lg px-4 py-2">
                      <div className="flex items-center gap-2">
                        <Loader2 className="w-4 h-4 animate-spin" />
                        <span className="text-sm text-muted-foreground">
                          Thinking...
                        </span>
                      </div>
                    </div>
                  </div>
                )}

                <div ref={messagesEndRef} />
              </div>
            )}
          </ScrollArea>

          {/* Input Area */}
          <div className="border-t p-4">
            {emails.length === 0 && (
              <div className="mb-3 p-3 bg-yellow-50 dark:bg-yellow-950 border border-yellow-200 dark:border-yellow-800 rounded-lg">
                <p className="text-xs text-yellow-800 dark:text-yellow-200 flex items-center gap-2">
                  <Sparkles className="w-3 h-3" />
                  Load emails in the Inbox tab first to enable chat
                </p>
              </div>
            )}

            <div className="flex gap-2">
              <Input
                placeholder={
                  emails.length > 0
                    ? 'Ask me about your emails...'
                    : 'Load emails first to chat'
                }
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyPress={handleKeyPress}
                disabled={loading || emails.length === 0}
                className="flex-1"
              />
              <Button
                onClick={() => sendMessage()}
                disabled={!input.trim() || loading || emails.length === 0}
              >
                {loading ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Send className="w-4 h-4" />
                )}
              </Button>
            </div>

            {messages.length > 0 && suggestions.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-2">
                <span className="text-xs text-muted-foreground">
                  Quick questions:
                </span>
                {suggestions.slice(0, 3).map((suggestion, idx) => (
                  <Badge
                    key={idx}
                    variant="secondary"
                    className="cursor-pointer hover:bg-secondary/80"
                    onClick={() => sendMessage(suggestion)}
                  >
                    {suggestion}
                  </Badge>
                ))}
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

