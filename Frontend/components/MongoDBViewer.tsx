'use client';

import { useState, useEffect, useRef } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Database, RefreshCw, ChevronLeft, ChevronRight, Mail, Calendar, Brain, Sparkles, AlertTriangle, CheckCircle2, Clock, Send } from 'lucide-react';
import { Textarea } from '@/components/ui/textarea';
import api from '@/lib/api';
import type { Email } from '@/lib/api';

interface AIAnalysis {
  category: string;
  urgency_score: number;
  is_spam: boolean;
  summary: string;
  sentiment: string;
  tags: string[];
  key_points: string[];
  action_required: boolean;
  suggested_response: string;
  analyzed_at: string;
}

interface ReplyData {
  email_message_id: string;
  account_id: number;
  to: string;
  subject: string;
  body: string;
  sent_at: string;
  success: boolean;
}

export default function MongoDBViewer() {
  const [emails, setEmails] = useState<Email[]>([]);
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState<{total_emails: number; oldest_email?: string; newest_email?: string} | null>(null);
  const [page, setPage] = useState(1);
  const [totalEmails, setTotalEmails] = useState(0);
  const [selectedEmail, setSelectedEmail] = useState<Email | null>(null);
  const [aiAnalysis, setAiAnalysis] = useState<AIAnalysis | null>(null);
  const [replyData, setReplyData] = useState<ReplyData | null>(null);
  const [loadingAnalysis, setLoadingAnalysis] = useState(false);
  const [loadingReply, setLoadingReply] = useState(false);
  const [activeTab, setActiveTab] = useState<'details' | 'analysis' | 'reply'>('details');
  const [replyText, setReplyText] = useState('');
  const [sendingReply, setSendingReply] = useState(false);
  const [refetching, setRefetching] = useState(false);
  const [activeAccountId, setActiveAccountId] = useState<number | null>(null);
  
  const EMAILS_PER_PAGE = 10;
  
  // Refs to prevent duplicate API calls
  const loadingRef = useRef(false);
  const statsLoadingRef = useRef(false);
  const previousAccountIdRef = useRef<number | null>(null);

  // Track active account and refresh stats when it changes
  useEffect(() => {
    const checkAccountChange = async () => {
      try {
        const response = await api.getCurrentUser();
        if (response && response.success && response.user && response.user.account_id) {
          const newAccountId = response.user.account_id;
          
          // If account changed, refresh stats and emails
          if (previousAccountIdRef.current !== null && previousAccountIdRef.current !== newAccountId) {
            console.log(`Account changed from ${previousAccountIdRef.current} to ${newAccountId}, refreshing stats...`);
            await Promise.all([loadStats(), loadEmails()]);
          }
          
          previousAccountIdRef.current = newAccountId;
          setActiveAccountId(newAccountId);
        } else {
          previousAccountIdRef.current = null;
          setActiveAccountId(null);
        }
      } catch (error) {
        console.error('Failed to get active account:', error);
      }
    };
    
    // Check immediately on mount
    checkAccountChange();
    
    // Check for account changes every 2 seconds
    const interval = setInterval(checkAccountChange, 2000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    // Prevent duplicate calls during React StrictMode double renders
    if (loadingRef.current || statsLoadingRef.current) {
      console.log('Skipping duplicate load (already loading)');
      return;
    }
    
    console.log('MongoDBViewer mounted or page changed:', page);
    
    // Load data
    const loadData = async () => {
      await Promise.all([loadStats(), loadEmails()]);
    };
    loadData();
    
    // Cleanup: reset refs on unmount or page change
    return () => {
      // Don't reset here - let them complete naturally
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page]);

  const loadStats = async () => {
    // Prevent duplicate calls
    if (statsLoadingRef.current) {
      return;
    }
    
    statsLoadingRef.current = true;
    try {
      console.log('Fetching MongoDB stats...');
      const statsData = await api.getMongoDBStats();
      console.log('MongoDB stats:', statsData);
      setStats(statsData);
    } catch (error) {
      console.error('Failed to load MongoDB stats:', error);
      // Don't alert on every error to avoid spam
    } finally {
      statsLoadingRef.current = false;
    }
  };

  const loadEmails = async () => {
    // Prevent duplicate calls
    if (loadingRef.current) {
      return;
    }
    
    loadingRef.current = true;
    setLoading(true);
    try {
      const skip = (page - 1) * EMAILS_PER_PAGE;
      console.log('Fetching MongoDB emails:', { limit: EMAILS_PER_PAGE, skip });
      const response = await api.getMongoDBEmails(EMAILS_PER_PAGE, skip);
      console.log('MongoDB response:', response);
      
      if (response.success) {
        setEmails(response.emails);
        setTotalEmails(response.total);
        console.log('Loaded emails:', response.emails.length, 'of', response.total);
      } else {
        console.error('Response not successful:', response);
      }
    } catch (error) {
      console.error('Failed to load emails from MongoDB:', error);
      // Don't alert on every error to avoid spam
    } finally {
      setLoading(false);
      loadingRef.current = false;
    }
  };

  // Load both AI analysis and reply in one batch request (much faster!)
  const loadEmailDetails = async (messageId: string) => {
    setLoadingAnalysis(true);
    setLoadingReply(true);
    setAiAnalysis(null);
    setReplyData(null);
    setReplyText(''); // Clear previous reply text
    
    try {
      console.log('Fetching email details (batch) for message:', messageId);
      const response = await api.getEmailDetails(messageId);
      console.log('Email details response:', response);
      
      if (response.success) {
        // Set AI analysis
        if (response.analysis) {
          setAiAnalysis(response.analysis);
          // Pre-fill reply text with AI suggestion
          if (response.analysis.suggested_response) {
            setReplyText(response.analysis.suggested_response);
          }
        } else {
          console.log('No AI analysis found for this email');
        }
        
        // Set reply data
        if (response.reply) {
          setReplyData(response.reply);
        } else {
          console.log('No reply found for this email');
        }
      }
    } catch (error) {
      console.error('Failed to load email details:', error);
    } finally {
      setLoadingAnalysis(false);
      setLoadingReply(false);
    }
  };

  // Re-fetch email from IMAP to update body
  const handleRefetchEmail = async (messageId: string) => {
    if (!messageId) return;
    
    setRefetching(true);
    try {
      const response = await api.refetchEmailFromIMAP(messageId);
      
      if (response.success) {
        const bodyExtracted = response.body_extracted || (response.text_body_length > 0 || response.html_body_length > 0);
        
        if (bodyExtracted) {
          alert(`Email re-fetched successfully! Body extracted: ${response.text_body_length} text chars, ${response.html_body_length} HTML chars`);
        } else {
          alert(`Email re-fetched but body is still empty. The email may have no body content, or it's in an unusual format. Check backend logs for details.`);
        }
        
        // Reload the email list to get updated data
        await loadEmails();
        
        // Reload the full email with body from MongoDB
        if (selectedEmail && selectedEmail.message_id === messageId) {
          try {
            const fullEmailResponse = await api.getSingleEmail(messageId);
            if (fullEmailResponse.success && fullEmailResponse.email) {
              // Update the selected email with new body
              setSelectedEmail(fullEmailResponse.email);
              // Also reload details (AI analysis, reply)
              loadEmailDetails(messageId);
            }
          } catch (err) {
            console.error('Error loading full email after refetch:', err);
            // Fallback: just reload details
            loadEmailDetails(messageId);
          }
        }
      } else {
        alert(`Failed to re-fetch email: ${response.message || 'Unknown error'}`);
      }
    } catch (error: any) {
      console.error('Error re-fetching email:', error);
      alert(`Error: ${error.message || 'Failed to re-fetch email'}`);
    } finally {
      setRefetching(false);
    }
  };

  // Keep individual functions for backward compatibility if needed
  const loadAIAnalysis = async (messageId: string) => {
    setLoadingAnalysis(true);
    setAiAnalysis(null);
    setReplyText(''); // Clear previous reply text
    try {
      console.log('Fetching AI analysis for message:', messageId);
      const response = await api.getEmailAIAnalysis(messageId);
      console.log('AI analysis response:', response);
      
      if (response.success && response.analysis) {
        setAiAnalysis(response.analysis);
        // Pre-fill reply text with AI suggestion
        if (response.analysis.suggested_response) {
          setReplyText(response.analysis.suggested_response);
        }
      } else {
        console.log('No AI analysis found for this email');
      }
    } catch (error) {
      console.error('Failed to load AI analysis:', error);
    } finally {
      setLoadingAnalysis(false);
    }
  };

  const loadReply = async (messageId: string) => {
    setLoadingReply(true);
    setReplyData(null);
    try {
      console.log('Fetching reply data for message:', messageId);
      const response = await api.getEmailReply(messageId);
      console.log('Reply data response:', response);
      
      if (response.success && response.reply) {
        setReplyData(response.reply);
      } else {
        console.log('No reply found for this email');
      }
    } catch (error) {
      console.error('Failed to load reply:', error);
    } finally {
      setLoadingReply(false);
    }
  };

  const sendReply = async () => {
    if (!selectedEmail || !replyText.trim()) {
      alert('Please enter a reply message');
      return;
    }

    setSendingReply(true);
    try {
      const response = await api.sendReply(selectedEmail.message_id, replyText);
      if (response.success) {
        alert(`✅ Reply sent to ${response.to}\n\nSubject: ${response.subject}`);
        setReplyText(''); // Clear reply text after sending
      } else {
        alert(`Failed to send reply: ${response.message}`);
      }
    } catch (error) {
      console.error('Failed to send reply:', error);
      alert(`Error sending reply: ${error}`);
    } finally {
      setSendingReply(false);
    }
  };

  // Load AI analysis and reply when email is selected (batch load for speed)
  useEffect(() => {
    if (selectedEmail?.message_id) {
      // Load full email body (the list view excludes bodies for performance)
      // Only load if body is missing (to avoid unnecessary API calls)
      const needsBodyLoad = !selectedEmail.text_body && !selectedEmail.html_body;
      
      if (needsBodyLoad) {
        const loadFullEmail = async () => {
          try {
            const fullEmailResponse = await api.getSingleEmail(selectedEmail.message_id);
            if (fullEmailResponse.success && fullEmailResponse.email) {
              // Update selectedEmail with full body
              setSelectedEmail(fullEmailResponse.email);
            }
          } catch (error) {
            console.error('Error loading full email body:', error);
          }
        };
        
        loadFullEmail();
      }
      
      loadEmailDetails(selectedEmail.message_id); // Load AI analysis and reply
    } else {
      setAiAnalysis(null);
      setReplyData(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedEmail?.message_id]);

  const totalPages = Math.ceil(totalEmails / EMAILS_PER_PAGE);

  const getCategoryColor = (category: string) => {
    const colors: Record<string, string> = {
      'work': 'bg-blue-100 text-blue-800',
      'personal': 'bg-green-100 text-green-800',
      'finance': 'bg-yellow-100 text-yellow-800',
      'marketing': 'bg-purple-100 text-purple-800',
      'social': 'bg-pink-100 text-pink-800',
      'other': 'bg-gray-100 text-gray-800',
    };
    return colors[category] || colors['other'];
  };

  return (
    <div className="space-y-6">
      {/* Stats Header */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Send className="w-5 h-5" />
                Auto Reply History
              </CardTitle>
              <CardDescription>View emails and AI-generated auto-replies</CardDescription>
            </div>
            <div className="flex gap-2">
              <Button onClick={() => { loadStats(); loadEmails(); }} disabled={loading} variant="outline">
                <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
                Refresh
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <p className="text-sm text-muted-foreground">Total Emails</p>
              <p className="text-2xl font-bold">{stats?.total_emails || 0}</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Current Page</p>
              <p className="text-2xl font-bold">{page} of {totalPages}</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Showing</p>
              <p className="text-2xl font-bold">{emails.length} emails</p>
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-2 gap-6">
        {/* Email List */}
        <Card>
          <CardHeader>
            <CardTitle>Stored Emails ({totalEmails})</CardTitle>
            <CardDescription>
              Page {page} of {totalPages}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ScrollArea className="h-[600px] pr-4">
              <div className="space-y-3">
                {emails.map((email, idx) => (
                  <Card
                    key={idx}
                    className={`cursor-pointer transition-colors hover:bg-accent ${
                      selectedEmail === email ? 'bg-accent' : ''
                    }`}
                    onClick={() => {
                      setSelectedEmail(email);
                      // loadEmailDetails will be called automatically by useEffect
                    }}
                  >
                    <CardContent className="p-4">
                      <div className="space-y-2">
                        <div className="flex items-start justify-between gap-2">
                          <h3 className="font-semibold line-clamp-1">
                            {email.subject || 'No Subject'}
                          </h3>
                          <Badge variant="outline" className="text-xs shrink-0">
                            #{(page - 1) * EMAILS_PER_PAGE + idx + 1}
                          </Badge>
                        </div>
                        
                        <p className="text-sm text-muted-foreground line-clamp-1">
                          From: {email.from}
                        </p>
                        
                        <div className="flex items-center gap-2 flex-wrap">
                          <div className="flex items-center gap-1 text-xs text-muted-foreground">
                            <Calendar className="w-3 h-3" />
                            {email.date}
                          </div>
                          
                          {email.ai_analysis && (
                            <>
                              <Badge className={getCategoryColor(email.ai_analysis.category)}>
                                {email.ai_analysis.category}
                              </Badge>
                              
                              {email.ai_analysis.urgency_score >= 7 && (
                                <Badge variant="destructive" className="text-xs">
                                  Urgent
                                </Badge>
                              )}
                              
                              {email.ai_analysis.is_spam && (
                                <Badge variant="secondary" className="text-xs">
                                  Spam
                                </Badge>
                              )}
                            </>
                          )}
                          
                          {email.has_attachments && (
                            <Badge variant="outline" className="text-xs">
                              📎 {email.attachments?.length || 0}
                            </Badge>
                          )}
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
                
                {emails.length === 0 && !loading && (
                  <div className="text-center py-12 text-muted-foreground">
                    <Mail className="w-12 h-12 mx-auto mb-4 opacity-50" />
                    <p>No emails found in MongoDB</p>
                    <p className="text-sm mt-2">Load some emails to see them here</p>
                  </div>
                )}
                
                {loading && (
                  <div className="text-center py-12">
                    <RefreshCw className="w-8 h-8 mx-auto animate-spin text-primary" />
                    <p className="mt-4 text-muted-foreground">Loading emails...</p>
                  </div>
                )}
              </div>
            </ScrollArea>
            
            {/* Pagination */}
            {totalPages > 1 && (
              <div className="mt-4 flex items-center justify-center gap-2">
                <Button
                  onClick={() => setPage(1)}
                  disabled={page === 1 || loading}
                  variant="outline"
                  size="sm"
                >
                  First
                </Button>
                <Button
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                  disabled={page === 1 || loading}
                  variant="outline"
                  size="sm"
                >
                  <ChevronLeft className="w-4 h-4" />
                </Button>
                <span className="text-sm px-4">
                  {page} / {totalPages}
                </span>
                <Button
                  onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages || loading}
                  variant="outline"
                  size="sm"
                >
                  <ChevronRight className="w-4 h-4" />
                </Button>
                <Button
                  onClick={() => setPage(totalPages)}
                  disabled={page === totalPages || loading}
                  variant="outline"
                  size="sm"
                >
                  Last
                </Button>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Email Detail with AI Analysis Tabs */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Mail className="w-5 h-5" />
              Email Viewer
            </CardTitle>
            <CardDescription>
              {selectedEmail ? 'View email content and AI analysis' : 'Select an email to view details'}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {selectedEmail ? (
              <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as 'details' | 'analysis' | 'reply')} className="w-full">
                <TabsList className="grid w-full grid-cols-3">
                  <TabsTrigger value="details" className="flex items-center gap-2">
                    <Mail className="w-4 h-4" />
                    Email Details
                  </TabsTrigger>
                  <TabsTrigger value="analysis" className="flex items-center gap-2">
                    <Brain className="w-4 h-4" />
                    AI Analysis
                    {aiAnalysis && <Badge variant="secondary" className="ml-1">✓</Badge>}
                  </TabsTrigger>
                  <TabsTrigger value="reply" className="flex items-center gap-2">
                    <Send className="w-4 h-4" />
                    Reply
                    {replyData && <Badge variant="secondary" className="ml-1">✓</Badge>}
                  </TabsTrigger>
                </TabsList>

                <TabsContent value="details" className="mt-4">
                  <ScrollArea className="h-[550px]">
                    <div className="space-y-4 pr-4">
                      <div>
                        <label className="text-sm font-semibold text-muted-foreground">Subject</label>
                        <p className="text-sm mt-1 font-medium">{selectedEmail.subject}</p>
                      </div>
                      
                      <div>
                        <label className="text-sm font-semibold text-muted-foreground">From</label>
                        <p className="text-sm mt-1">{selectedEmail.from}</p>
                      </div>
                      
                      <div>
                        <label className="text-sm font-semibold text-muted-foreground">To</label>
                        <p className="text-sm mt-1">{selectedEmail.to}</p>
                      </div>
                      
                      <div>
                        <label className="text-sm font-semibold text-muted-foreground">Date</label>
                        <p className="text-sm mt-1 flex items-center gap-2">
                          <Calendar className="w-4 h-4" />
                          {selectedEmail.date}
                        </p>
                      </div>
                      
                      <div>
                        <div className="flex items-center justify-between mb-2">
                          <label className="text-sm font-semibold text-muted-foreground">Body</label>
                          {(!selectedEmail.text_body || selectedEmail.text_body.trim() === '') && (
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleRefetchEmail(selectedEmail.message_id)}
                              disabled={refetching}
                              className="h-7"
                            >
                              <RefreshCw className={`w-3 h-3 mr-1 ${refetching ? 'animate-spin' : ''}`} />
                              {refetching ? 'Re-fetching...' : 'Re-fetch from IMAP'}
                            </Button>
                          )}
                        </div>
                        <div className="mt-2 p-4 bg-muted rounded-md">
                          {selectedEmail.text_body ? (
                            <p className="text-sm whitespace-pre-wrap">
                              {selectedEmail.text_body}
                            </p>
                          ) : (
                            <div className="text-sm text-muted-foreground">
                              <p className="mb-2">No text content</p>
                              <p className="text-xs italic">
                                This email may have no body content (subject-only email). 
                                If you believe it should have content, try clicking "Re-fetch from IMAP" above.
                              </p>
                            </div>
                          )}
                        </div>
                      </div>
                      
                      {selectedEmail.has_attachments && selectedEmail.attachments && (
                        <div>
                          <label className="text-sm font-semibold text-muted-foreground">Attachments ({selectedEmail.attachments.length})</label>
                          <div className="mt-2 space-y-2">
                            {selectedEmail.attachments.map((att, i) => (
                              <div key={i} className="flex items-center gap-2 p-3 bg-muted rounded-md border">
                                <span className="text-xl">📎</span>
                                <div className="flex-1">
                                  <p className="text-sm font-medium">{att.filename || 'Unknown'}</p>
                                  {att.content_type && (
                                    <p className="text-xs text-muted-foreground">{att.content_type}</p>
                                  )}
                                </div>
                                {att.size && (
                                  <Badge variant="outline" className="text-xs">
                                    {att.size}
                                  </Badge>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </ScrollArea>
                </TabsContent>

                <TabsContent value="analysis" className="mt-4">
                  <ScrollArea className="h-[550px]">
                    <div className="space-y-4 pr-4">
                      {loadingAnalysis ? (
                        <div className="flex items-center justify-center py-12">
                          <RefreshCw className="w-8 h-8 animate-spin text-primary" />
                          <p className="ml-3 text-muted-foreground">Loading AI analysis...</p>
                        </div>
                      ) : aiAnalysis ? (
                        <>
                          {/* Analysis Header */}
                          <div className="flex items-center gap-2 p-4 bg-gradient-to-r from-purple-50 to-blue-50 border border-purple-200 rounded-lg">
                            <Sparkles className="w-5 h-5 text-purple-600" />
                            <div className="flex-1">
                              <h3 className="font-semibold text-purple-900">AI-Powered Email Analysis</h3>
                              <p className="text-xs text-purple-700 flex items-center gap-1 mt-1">
                                <Clock className="w-3 h-3" />
                                Analyzed: {new Date(aiAnalysis.analyzed_at).toLocaleString()}
                              </p>
                            </div>
                          </div>

                          {/* Category and Urgency */}
                          <div className="grid grid-cols-2 gap-4">
                            <div className="p-4 border rounded-lg">
                              <label className="text-sm font-semibold text-muted-foreground">Category</label>
                              <div className="mt-2">
                                <Badge className={`${getCategoryColor(aiAnalysis.category)} text-base px-3 py-1`}>
                                  {aiAnalysis.category.toUpperCase()}
                                </Badge>
                              </div>
                            </div>
                            <div className="p-4 border rounded-lg">
                              <label className="text-sm font-semibold text-muted-foreground">Urgency Score</label>
                              <div className="mt-2 flex items-center gap-2">
                                <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
                                  <div 
                                    className={`h-full ${
                                      aiAnalysis.urgency_score >= 7 ? 'bg-red-500' : 
                                      aiAnalysis.urgency_score >= 4 ? 'bg-yellow-500' : 
                                      'bg-green-500'
                                    }`}
                                    style={{ width: `${aiAnalysis.urgency_score * 10}%` }}
                                  />
                                </div>
                                <span className="font-bold text-lg">{aiAnalysis.urgency_score}/10</span>
                              </div>
                            </div>
                          </div>

                          {/* Flags */}
                          <div className="flex gap-2">
                            {aiAnalysis.is_spam && (
                              <Badge variant="destructive" className="flex items-center gap-1">
                                <AlertTriangle className="w-3 h-3" />
                                Spam Detected
                              </Badge>
                            )}
                            {aiAnalysis.action_required && (
                              <Badge variant="default" className="flex items-center gap-1 bg-orange-500">
                                <CheckCircle2 className="w-3 h-3" />
                                Action Required
                              </Badge>
                            )}
                          </div>

                          {/* Summary */}
                          {aiAnalysis.summary && (
                            <div>
                              <label className="text-sm font-semibold text-muted-foreground flex items-center gap-2">
                                <Sparkles className="w-4 h-4" />
                                Summary
                              </label>
                              <div className="mt-2 p-4 bg-blue-50 border border-blue-200 rounded-lg">
                                <p className="text-sm leading-relaxed">{aiAnalysis.summary}</p>
                              </div>
                            </div>
                          )}

                          {/* Sentiment */}
                          {aiAnalysis.sentiment && (
                            <div>
                              <label className="text-sm font-semibold text-muted-foreground">Sentiment</label>
                              <Badge variant="outline" className="mt-2">
                                {aiAnalysis.sentiment}
                              </Badge>
                            </div>
                          )}

                          {/* Tags */}
                          {aiAnalysis.tags && aiAnalysis.tags.length > 0 && (
                            <div>
                              <label className="text-sm font-semibold text-muted-foreground">Tags</label>
                              <div className="mt-2 flex flex-wrap gap-2">
                                {aiAnalysis.tags.map((tag, i) => (
                                  <Badge key={i} variant="secondary">
                                    #{tag}
                                  </Badge>
                                ))}
                              </div>
                            </div>
                          )}

                          {/* Key Points */}
                          {aiAnalysis.key_points && aiAnalysis.key_points.length > 0 && (
                            <div>
                              <label className="text-sm font-semibold text-muted-foreground">Key Points</label>
                              <ul className="mt-2 space-y-2">
                                {aiAnalysis.key_points.map((point, i) => (
                                  <li key={i} className="flex items-start gap-2 text-sm">
                                    <span className="text-blue-600 mt-1">•</span>
                                    <span>{point}</span>
                                  </li>
                                ))}
                              </ul>
                            </div>
                          )}

                          {/* Suggested Response */}
                          {aiAnalysis.suggested_response && (
                            <div>
                              <label className="text-sm font-semibold text-muted-foreground flex items-center gap-2">
                                <Brain className="w-4 h-4" />
                                AI-Suggested Response
                              </label>
                              <div className="mt-2 space-y-3">
                                <Textarea
                                  value={replyText}
                                  onChange={(e) => setReplyText(e.target.value)}
                                  placeholder="Edit the suggested reply before sending..."
                                  className="min-h-[150px] bg-green-50 border-green-200 focus:border-green-400"
                                />
                                <div className="flex items-center justify-between">
                                  <p className="text-xs text-muted-foreground">
                                    ✏️ You can edit the AI suggestion before sending
                                  </p>
                                  <Button
                                    onClick={sendReply}
                                    disabled={sendingReply || !replyText.trim()}
                                    className="bg-green-600 hover:bg-green-700"
                                  >
                                    {sendingReply ? (
                                      <>
                                        <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                                        Sending...
                                      </>
                                    ) : (
                                      <>
                                        <Send className="w-4 h-4 mr-2" />
                                        Send Reply
                                      </>
                                    )}
                                  </Button>
                                </div>
                              </div>
                            </div>
                          )}
                        </>
                      ) : (
                        <div className="flex items-center justify-center py-12 text-muted-foreground">
                          <div className="text-center">
                            <Brain className="w-16 h-16 mx-auto mb-4 opacity-30" />
                            <p className="font-semibold">No AI Analysis Available</p>
                            <p className="text-sm mt-2">This email has not been analyzed yet.</p>
                            <p className="text-xs mt-1 text-muted-foreground">
                              New emails are automatically analyzed by the monitoring system.
                            </p>
                          </div>
                        </div>
                      )}
                    </div>
                  </ScrollArea>
                </TabsContent>

                <TabsContent value="reply" className="mt-4">
                  <ScrollArea className="h-[550px]">
                    <div className="space-y-4 pr-4">
                      {loadingReply ? (
                        <div className="flex items-center justify-center py-12">
                          <RefreshCw className="w-8 h-8 animate-spin text-primary" />
                          <p className="ml-3 text-muted-foreground">Loading reply data...</p>
                        </div>
                      ) : replyData ? (
                        <>
                          {/* Reply Header */}
                          <div className="flex items-center gap-2 p-4 bg-gradient-to-r from-green-50 to-emerald-50 border border-green-200 rounded-lg">
                            <Send className="w-5 h-5 text-green-600" />
                            <div className="flex-1">
                              <h3 className="font-semibold text-green-900">Reply Sent Successfully</h3>
                              <p className="text-xs text-green-700 flex items-center gap-1 mt-1">
                                <Clock className="w-3 h-3" />
                                Sent: {new Date(replyData.sent_at).toLocaleString()}
                              </p>
                            </div>
                            {replyData.success && (
                              <Badge variant="default" className="bg-green-600">
                                <CheckCircle2 className="w-3 h-3 mr-1" />
                                Delivered
                              </Badge>
                            )}
                          </div>

                          {/* Reply Details */}
                          <div className="space-y-4">
                            <div>
                              <label className="text-sm font-semibold text-muted-foreground">To</label>
                              <p className="text-sm mt-1 font-medium">{replyData.to}</p>
                            </div>
                            
                            <div>
                              <label className="text-sm font-semibold text-muted-foreground">Subject</label>
                              <p className="text-sm mt-1 font-medium">{replyData.subject}</p>
                            </div>
                            
                            <div>
                              <label className="text-sm font-semibold text-muted-foreground">Reply Body</label>
                              <div className="mt-2 p-4 bg-muted rounded-md border border-green-200">
                                <p className="text-sm whitespace-pre-wrap leading-relaxed">{replyData.body}</p>
                              </div>
                            </div>

                            <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
                              <div className="flex items-center gap-2 text-sm text-blue-900">
                                <CheckCircle2 className="w-4 h-4" />
                                <span className="font-semibold">Reply Status:</span>
                                <span>
                                  {replyData.success 
                                    ? 'This reply was successfully sent to the recipient.' 
                                    : 'There was an issue sending this reply.'}
                                </span>
                              </div>
                            </div>
                          </div>
                        </>
                      ) : (
                        <div className="flex items-center justify-center py-12 text-muted-foreground">
                          <div className="text-center">
                            <Send className="w-16 h-16 mx-auto mb-4 opacity-30" />
                            <p className="font-semibold">No Reply Sent</p>
                            <p className="text-sm mt-2">No reply has been sent for this email yet.</p>
                            <p className="text-xs mt-1 text-muted-foreground">
                              Auto-replies are sent automatically if enabled, or you can send a manual reply from the AI Analysis tab.
                            </p>
                          </div>
                        </div>
                      )}
                    </div>
                  </ScrollArea>
                </TabsContent>
              </Tabs>
            ) : (
              <div className="h-[600px] flex items-center justify-center text-muted-foreground">
                <div className="text-center">
                  <Mail className="w-16 h-16 mx-auto mb-4 opacity-30" />
                  <p>Select an email to view details and AI analysis</p>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

