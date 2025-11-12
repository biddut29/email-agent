'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { api, Email, EmailStats } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { format, subDays, startOfMonth, startOfYear } from 'date-fns';
import {
  Mail,
  RefreshCw,
  Send,
  Sparkles,
  Search,
  TrendingUp,
  Inbox,
  MailOpen,
  AlertCircle,
  Bot,
  ArrowLeft,
  MessageSquare,
  Filter,
  X,
  Calendar as CalendarIcon,
  Database,
  LogOut,
} from 'lucide-react';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Calendar } from '@/components/ui/calendar';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import EmailChat from './EmailChat';
import AccountManager from './AccountManager';
import VectorViewer from './VectorViewer';
import NotificationListener from './NotificationListener';
import MongoDBViewer from './MongoDBViewer';

export default function EmailDashboard() {
  const router = useRouter();
  const [emails, setEmails] = useState<Email[]>([]);
  const [selectedEmail, setSelectedEmail] = useState<Email | null>(null);
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState<EmailStats | null>(null);
  const [healthStatus, setHealthStatus] = useState<any>(null);
  const [autoReplyEnabled, setAutoReplyEnabled] = useState<boolean>(false);
  const [aiResponse, setAiResponse] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState('');
  const [replyBody, setReplyBody] = useState('');
  const [activeTab, setActiveTab] = useState('mongodb');
  const [dateFilter, setDateFilter] = useState<string>('today');
  const [customDateFrom, setCustomDateFrom] = useState<Date | undefined>(undefined);
  const [customDateTo, setCustomDateTo] = useState<Date | undefined>(undefined);

  // Load health status on mount
  useEffect(() => {
    checkHealth();
  }, []);

  const handleLogout = async () => {
    try {
      await api.logout();
      router.push('/login');
    } catch (error) {
      console.error('Logout error:', error);
      // Still redirect to login even if logout API call fails
      router.push('/login');
    }
  };

  const checkHealth = async () => {
    try {
      const health = await api.healthCheck();
      setHealthStatus(health);
      
      // Also check auto-reply status
      try {
        const autoReplyStatus = await api.getAutoReplyStatus();
        setAutoReplyEnabled(autoReplyStatus.auto_reply_enabled);
      } catch (autoReplyError: any) {
        console.error('Auto-reply status check failed:', autoReplyError);
        // Don't fail the whole health check if auto-reply status fails
      }
    } catch (error: any) {
      console.error('Health check failed:', error);
      const errorMessage = error.message || String(error);
      if (errorMessage.includes('Cannot connect to backend')) {
        console.error('⚠️ Backend connection failed. Please ensure:');
        console.error('  1. Backend is running on http://localhost:8000');
        console.error('  2. No firewall is blocking the connection');
        console.error('  3. CORS is properly configured');
      }
      setHealthStatus(null);
    }
  };

  const toggleAutoReply = async () => {
    try {
      const response = await api.toggleAutoReply(!autoReplyEnabled);
      setAutoReplyEnabled(response.auto_reply_enabled);
      alert(response.message);
    } catch (error) {
      console.error('Failed to toggle auto-reply:', error);
      alert(`Failed to toggle auto-reply: ${error}`);
    }
  };

  const getDateRange = (filter: string): { from?: string; to?: string } => {
    const today = new Date();
    
    switch (filter) {
      case 'today':
        return { 
          from: format(today, 'yyyy-MM-dd'),
          to: format(today, 'yyyy-MM-dd')
        };
      case 'last7':
        return { from: format(subDays(today, 7), 'yyyy-MM-dd') };
      case 'last30':
        return { from: format(subDays(today, 30), 'yyyy-MM-dd') };
      case 'thisMonth':
        return { from: format(startOfMonth(today), 'yyyy-MM-dd') };
      case 'thisYear':
        return { from: format(startOfYear(today), 'yyyy-MM-dd') };
      case 'custom':
        return {
          from: customDateFrom ? format(customDateFrom, 'yyyy-MM-dd') : undefined,
          to: customDateTo ? format(customDateTo, 'yyyy-MM-dd') : undefined,
        };
      default:
        return {};
    }
  };

  const clearCustomDates = () => {
    setCustomDateFrom(undefined);
    setCustomDateTo(undefined);
  };

  const loadEmails = async (unreadOnly: boolean = false) => {
    setLoading(true);
    try {
      const { from, to } = getDateRange(dateFilter);
      
      // Use lower limit for faster loading (reduced from 200 to 50)
      const limit = 50;
      
      const response = await api.getEmails(limit, unreadOnly, 'INBOX', from, to);
      
      // Check for errors in response (response may have error property even if not in type)
      const responseWithError = response as any;
      if (response.success === false || responseWithError.error) {
        console.error('Email loading error:', response);
        alert(`Failed to load emails: ${responseWithError.error || 'No active email account. Please add an account first.'}`);
        setEmails([]);
        return;
      }
      
      // Handle response - check if emails array exists
      if (response.emails && Array.isArray(response.emails)) {
        setEmails(response.emails);
        console.log(`✓ Loaded ${response.emails.length} emails`);
      } else {
        console.warn('Unexpected response format:', response);
        setEmails([]);
      }
    } catch (error: any) {
      console.error('Failed to load emails:', error);
      // Show user-friendly error message
      const errorMessage = error.message || 'Failed to connect to backend. Please ensure the backend is running.';
      alert(`Error loading emails: ${errorMessage}`);
      setEmails([]);
    } finally {
      setLoading(false);
    }
  };

  const loadToVector = async () => {
    setLoading(true);
    try {
      const { from, to } = getDateRange(dateFilter);
      const response = await api.loadToVector(from, to);
      
      if (response.success) {
        alert(`✅ ${response.message}\n\nMongoDB: ${response.mongo_count} emails\nVector DB: ${response.vector_count} emails indexed`);
      } else {
        alert(`⚠️ ${response.message}`);
      }
    } catch (error) {
      console.error('Failed to load to vector:', error);
      alert(`❌ Failed to load to vector database: ${error}`);
    } finally {
      setLoading(false);
    }
  };

  const loadStatistics = async () => {
    setLoading(true);
    try {
      const response = await api.getStatistics();
      setStats(response.statistics);
    } catch (error) {
      console.error('Failed to load statistics:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateAIResponse = async () => {
    if (!selectedEmail) return;

    setLoading(true);
    try {
      // Use message_id if available (for MongoDB/Gmail API emails), otherwise use id
      const emailIdentifier = selectedEmail.message_id || selectedEmail.id || '';
      const response = await api.generateResponse(
        emailIdentifier, 
        'professional', 
        selectedEmail.message_id || undefined
      );
      if (response.success) {
        setAiResponse(response.response);
        setReplyBody(response.response);
      } else {
        alert('Failed to generate AI response');
      }
    } catch (error: any) {
      console.error('Failed to generate AI response:', error);
      alert(`Failed to generate AI response: ${error.message || 'Unknown error'}`);
    } finally {
      setLoading(false);
    }
  };

  const handleSendReply = async () => {
    if (!selectedEmail || !replyBody.trim()) return;

    setLoading(true);
    try {
      // Use message_id if available (for MongoDB/Gmail API emails), otherwise use id
      const messageId = selectedEmail.message_id || selectedEmail.id;
      if (!messageId) {
        alert('Error: Email ID not found');
        return;
      }

      // Use sendReply for MongoDB emails (uses message_id), fallback to replyToEmail for IMAP
      if (selectedEmail.message_id) {
        const response = await api.sendReply(selectedEmail.message_id, replyBody);
        if (response.success) {
          alert(`Reply sent successfully to ${response.to}!`);
          setReplyBody('');
          setAiResponse('');
        } else {
          alert('Failed to send reply');
        }
      } else {
        // Fallback for IMAP emails
        await api.replyToEmail(selectedEmail.id, replyBody);
        alert('Reply sent successfully!');
        setReplyBody('');
        setAiResponse('');
      }
    } catch (error: any) {
      console.error('Failed to send reply:', error);
      alert(`Failed to send reply: ${error.message || 'Unknown error'}`);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;

    setLoading(true);
    try {
      const response = await api.searchEmails({ query: searchQuery });
      setEmails(response.emails);
    } catch (error) {
      console.error('Search failed:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleAccountChange = () => {
    // Reload emails when account changes
    setEmails([]);
    setSelectedEmail(null);
    checkHealth();
  };

  const getCategoryColor = (category: string) => {
    const colors: Record<string, string> = {
      'work': 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
      'personal': 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
      'finance': 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
      'marketing': 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200',
      'social': 'bg-pink-100 text-pink-800 dark:bg-pink-900 dark:text-pink-200',
      'urgent': 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
      'important': 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200',
      'spam': 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200',
      'promotional': 'bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-200',
      'newsletter': 'bg-cyan-100 text-cyan-800 dark:bg-cyan-900 dark:text-cyan-200',
      'other': 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200',
    };
    return colors[category.toLowerCase()] || colors['other'];
  };

  const formatDate = (dateString: string) => {
    try {
      return new Date(dateString).toLocaleString();
    } catch {
      return dateString;
    }
  };

  return (
    <>
      {/* Real-time notification listener */}
      <NotificationListener />
      
      <div className="container mx-auto p-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
        <div>
          <h1 className="text-4xl font-bold flex items-center gap-3">
            <Mail className="w-10 h-10 text-primary" />
            Email Agent Dashboard
          </h1>
          <p className="text-muted-foreground mt-2">
            AI-powered email management system
          </p>
        </div>
        <div className="flex items-center gap-4">
          {/* Account Manager - Hidden */}
          <div className="hidden">
            <AccountManager onAccountChange={handleAccountChange} />
          </div>

          {/* Logout Button */}
          <Button
            variant="outline"
            size="sm"
            onClick={handleLogout}
            className="flex items-center gap-2"
          >
            <LogOut className="w-4 h-4" />
            Logout
          </Button>

          {/* Status Card */}
          {healthStatus && (
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
                    <span className="text-sm font-medium">{healthStatus.email}</span>
                    {healthStatus.ai_enabled && (
                      <Badge variant="secondary" className="ml-2">
                        <Bot className="w-3 h-3 mr-1" />
                        AI Enabled
                      </Badge>
                    )}
                    {healthStatus.accounts_count > 1 && (
                      <Badge variant="outline" className="ml-2">
                        {healthStatus.accounts_count} accounts
                      </Badge>
                    )}
                  </div>
                  <Button
                    onClick={toggleAutoReply}
                    variant={autoReplyEnabled ? "default" : "outline"}
                    size="sm"
                    className={autoReplyEnabled ? "bg-green-600 hover:bg-green-700" : ""}
                  >
                    <Bot className="w-4 h-4 mr-2" />
                    {autoReplyEnabled ? "Auto-Reply ON" : "Auto-Reply OFF"}
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>

      {/* Main Content */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="mongodb" className="flex items-center gap-2">
            <Send className="w-4 h-4" />
            Auto Replies
          </TabsTrigger>
          <TabsTrigger value="inbox" className="flex items-center gap-2">
            <Inbox className="w-4 h-4" />
            Inbox
          </TabsTrigger>
          <TabsTrigger value="chat" className="flex items-center gap-2">
            <MessageSquare className="w-4 h-4" />
            Chat
            {emails.length > 0 && (
              <Badge variant="secondary" className="ml-1 h-5 px-1 text-xs">
                {emails.length}
              </Badge>
            )}
          </TabsTrigger>
          <TabsTrigger value="vector" className="flex items-center gap-2">
            <Database className="w-4 h-4" />
            Vector DB
          </TabsTrigger>
        </TabsList>

        {/* Inbox Tab */}
        <TabsContent value="inbox" className="space-y-4">
          {/* Simple Filter Bar */}
          <div className="space-y-3">
            <div className="flex flex-wrap gap-3 items-center p-4 bg-muted/50 rounded-lg">
              <div className="flex items-center gap-2">
                <Filter className="w-4 h-4 text-muted-foreground" />
                <label className="text-sm font-medium">Time Period:</label>
              </div>
              
              <Select value={dateFilter} onValueChange={setDateFilter}>
                <SelectTrigger className="w-[200px]">
                  <SelectValue placeholder="Select time period" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="today">Today</SelectItem>
                  <SelectItem value="last7">Last 7 Days</SelectItem>
                  <SelectItem value="last30">Last 30 Days</SelectItem>
                  <SelectItem value="thisMonth">This Month</SelectItem>
                  <SelectItem value="thisYear">This Year</SelectItem>
                  <SelectItem value="custom">Custom Range...</SelectItem>
                </SelectContent>
              </Select>

              <Button onClick={() => loadEmails(false)} disabled={loading}>
                <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
                Load Emails
              </Button>

              <Button onClick={loadToVector} disabled={loading} variant="secondary">
                <Database className="w-4 h-4 mr-2" />
                Load to Vector
              </Button>

              {dateFilter !== 'custom' && (
                <Badge variant="secondary" className="ml-auto">
                  {dateFilter === 'today' && '📅 Today'}
                  {dateFilter === 'last7' && '📅 Last 7 Days'}
                  {dateFilter === 'last30' && '📅 Last 30 Days'}
                  {dateFilter === 'thisMonth' && '📅 This Month'}
                  {dateFilter === 'thisYear' && '📅 This Year'}
                </Badge>
              )}
            </div>

            {/* Custom Date Range Picker - Shows when "Custom" is selected */}
            {dateFilter === 'custom' && (
              <div className="p-4 border rounded-lg bg-card">
                <div className="flex flex-wrap gap-3 items-end">
                  {/* From Date */}
                  <div className="flex flex-col gap-2">
                    <label className="text-sm font-medium">From Date</label>
                    <Popover>
                      <PopoverTrigger asChild>
                        <Button
                          variant="outline"
                          className="w-[200px] justify-start text-left font-normal"
                        >
                          <CalendarIcon className="mr-2 h-4 w-4" />
                          {customDateFrom ? format(customDateFrom, 'PPP') : 'Pick a date'}
                        </Button>
                      </PopoverTrigger>
                      <PopoverContent className="w-auto p-0" align="start">
                        <Calendar
                          mode="single"
                          selected={customDateFrom}
                          onSelect={setCustomDateFrom}
                          initialFocus
                        />
                      </PopoverContent>
                    </Popover>
                  </div>

                  {/* To Date */}
                  <div className="flex flex-col gap-2">
                    <label className="text-sm font-medium">To Date</label>
                    <Popover>
                      <PopoverTrigger asChild>
                        <Button
                          variant="outline"
                          className="w-[200px] justify-start text-left font-normal"
                        >
                          <CalendarIcon className="mr-2 h-4 w-4" />
                          {customDateTo ? format(customDateTo, 'PPP') : 'Pick a date'}
                        </Button>
                      </PopoverTrigger>
                      <PopoverContent className="w-auto p-0" align="start">
                        <Calendar
                          mode="single"
                          selected={customDateTo}
                          onSelect={setCustomDateTo}
                          initialFocus
                        />
                      </PopoverContent>
                    </Popover>
                  </div>

                  {/* Clear Custom Dates Button */}
                  {(customDateFrom || customDateTo) && (
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={clearCustomDates}
                      title="Clear custom dates"
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  )}
                </div>

                {/* Custom Date Range Summary */}
                {(customDateFrom || customDateTo) && (
                  <div className="mt-3 p-3 bg-blue-50 dark:bg-blue-950 rounded-md">
                    <p className="text-sm text-blue-900 dark:text-blue-100">
                      📅 Custom Range: {customDateFrom && `from ${format(customDateFrom, 'MMM d, yyyy')}`}
                      {customDateFrom && customDateTo && ' '}
                      {customDateTo && `to ${format(customDateTo, 'MMM d, yyyy')}`}
                    </p>
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Email List */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center justify-between">
                  <span>Emails ({emails.length})</span>
                  {emails.length >= 200 && (
                    <Badge variant="secondary" className="text-xs">
                      Limited to 200 (max reached)
                    </Badge>
                  )}
                  {emails.length < 200 && emails.length > 0 && (
                    <Badge variant="outline" className="text-xs">
                      All emails loaded
                    </Badge>
                  )}
                </CardTitle>
                <CardDescription>Click to view details</CardDescription>
              </CardHeader>
              <CardContent>
                <ScrollArea className="h-[600px] pr-4">
                  <div className="space-y-3">
                    {emails.map((email, idx) => (
                      <Card
                        key={email.id}
                        className={`cursor-pointer transition-colors hover:bg-accent ${
                          selectedEmail?.id === email.id ? 'bg-accent' : ''
                        }`}
                        onClick={() => setSelectedEmail(email)}
                      >
                        <CardContent className="p-4">
                          <div className="space-y-2">
                            <div className="flex items-start justify-between gap-2">
                              <h3 className="font-semibold line-clamp-1">
                                {email.subject || 'No Subject'}
                              </h3>
                              <Badge variant="outline" className="text-xs shrink-0">
                                #{idx + 1}
                              </Badge>
                            </div>
                            
                            <p className="text-sm text-muted-foreground line-clamp-1">
                              From: {email.from}
                            </p>
                            
                            <div className="flex items-center gap-2 flex-wrap">
                              <div className="flex items-center gap-1 text-xs text-muted-foreground">
                                <CalendarIcon className="w-3 h-3" />
                                {formatDate(email.date)}
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
                    {emails.length === 0 && (
                      <div className="text-center py-16">
                        <div className="w-16 h-16 mx-auto rounded-full bg-muted flex items-center justify-center mb-4">
                          <Mail className="w-8 h-8 text-muted-foreground opacity-50" />
                        </div>
                        <p className="text-base font-medium text-foreground mb-2">No emails loaded</p>
                        <p className="text-sm text-muted-foreground">Click "Load Emails" to fetch your emails</p>
                      </div>
                    )}
                  </div>
                </ScrollArea>
              </CardContent>
            </Card>

            {/* Email Detail */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  {selectedEmail && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setSelectedEmail(null)}
                    >
                      <ArrowLeft className="w-4 h-4" />
                    </Button>
                  )}
                  Email Details
                </CardTitle>
              </CardHeader>
              <CardContent>
                {selectedEmail ? (
                  <ScrollArea className="h-[600px]">
                    <div className="space-y-6">
                      {/* Email Header */}
                      <div className="space-y-4">
                        <div>
                          <h2 className="text-2xl font-bold mb-3 leading-tight">
                            {selectedEmail.subject || '(No Subject)'}
                          </h2>
                          <Separator />
                        </div>
                        <div className="grid gap-3 text-sm">
                          <div className="flex items-start gap-3">
                            <span className="font-semibold text-muted-foreground min-w-[60px]">From:</span>
                            <span className="flex-1">{selectedEmail.from}</span>
                          </div>
                          <div className="flex items-start gap-3">
                            <span className="font-semibold text-muted-foreground min-w-[60px]">To:</span>
                            <span className="flex-1">{selectedEmail.to}</span>
                          </div>
                          <div className="flex items-start gap-3">
                            <span className="font-semibold text-muted-foreground min-w-[60px]">Date:</span>
                            <span className="flex-1 flex items-center gap-2">
                              <CalendarIcon className="w-4 h-4" />
                              {formatDate(selectedEmail.date)}
                            </span>
                          </div>
                        </div>
                      </div>

                      {selectedEmail.ai_analysis && (
                        <Card className="bg-gradient-to-br from-primary/5 to-primary/10 border-primary/20">
                          <CardHeader className="pb-3">
                            <CardTitle className="text-base flex items-center gap-2">
                              <Sparkles className="w-4 h-4 text-primary" />
                              AI Analysis
                            </CardTitle>
                          </CardHeader>
                          <CardContent className="space-y-3 text-sm">
                            <div className="flex items-center gap-2">
                              <span className="font-semibold text-muted-foreground">Category:</span>
                              <Badge className={`${getCategoryColor(selectedEmail.ai_analysis.category)} text-xs`}>
                                {selectedEmail.ai_analysis.category}
                              </Badge>
                            </div>
                            {selectedEmail.ai_analysis.urgency_score > 6 && (
                              <div className="flex items-center gap-2 p-2 rounded-md bg-orange-50 dark:bg-orange-950/30 border border-orange-200 dark:border-orange-800">
                                <AlertCircle className="w-4 h-4 text-orange-600 dark:text-orange-400" />
                                <span className="font-medium text-orange-700 dark:text-orange-300">
                                  High Urgency ({selectedEmail.ai_analysis.urgency_score}/10)
                                </span>
                              </div>
                            )}
                            {selectedEmail.ai_analysis.summary && (
                              <div className="pt-2 border-t">
                                <span className="font-semibold text-muted-foreground block mb-1.5">Summary:</span>
                                <p className="text-foreground leading-relaxed">{selectedEmail.ai_analysis.summary}</p>
                              </div>
                            )}
                          </CardContent>
                        </Card>
                      )}

                      {/* Email Body */}
                      <div className="space-y-3">
                        <h4 className="font-semibold text-base flex items-center gap-2">
                          <MailOpen className="w-4 h-4" />
                          Message
                        </h4>
                        <Card className="bg-muted/30">
                          <CardContent className="pt-6">
                            <div className="whitespace-pre-wrap text-sm leading-relaxed text-foreground">
                              {selectedEmail.text_body || (
                                <span className="text-muted-foreground italic">No text content available</span>
                              )}
                            </div>
                          </CardContent>
                        </Card>
                      </div>

                      <Separator />

                      {/* Reply Section */}
                      <div className="space-y-4">
                        <div className="flex items-center justify-between">
                          <h4 className="font-semibold text-base flex items-center gap-2">
                            <MessageSquare className="w-4 h-4" />
                            Reply
                          </h4>
                          <Button
                            onClick={handleGenerateAIResponse}
                            disabled={loading}
                            variant="outline"
                            size="sm"
                            className="gap-2"
                          >
                            <Sparkles className="w-4 h-4" />
                            Generate AI Response
                          </Button>
                        </div>

                        {aiResponse && (
                          <Card className="bg-gradient-to-br from-green-50 to-emerald-50 dark:from-green-950/30 dark:to-emerald-950/30 border-green-200 dark:border-green-800">
                            <CardHeader className="pb-3">
                              <CardTitle className="text-sm flex items-center gap-2 text-green-700 dark:text-green-300">
                                <Sparkles className="w-4 h-4" />
                                AI Generated Response
                              </CardTitle>
                            </CardHeader>
                            <CardContent>
                              <div className="whitespace-pre-wrap text-sm leading-relaxed text-green-900 dark:text-green-100">
                                {aiResponse}
                              </div>
                              <Button
                                variant="ghost"
                                size="sm"
                                className="mt-3 text-xs"
                                onClick={() => setReplyBody(aiResponse)}
                              >
                                Use this response
                              </Button>
                            </CardContent>
                          </Card>
                        )}

                        <div className="space-y-3">
                          <label className="text-sm font-semibold block">Your Reply:</label>
                          <Textarea
                            placeholder="Type your reply here..."
                            value={replyBody}
                            onChange={(e) => setReplyBody(e.target.value)}
                            rows={8}
                            className="resize-none font-mono text-sm"
                          />
                          <Button
                            onClick={handleSendReply}
                            disabled={loading || !replyBody.trim()}
                            className="w-full gap-2"
                            size="lg"
                          >
                            <Send className="w-4 h-4" />
                            Send Reply
                          </Button>
                        </div>
                      </div>
                    </div>
                  </ScrollArea>
                ) : (
                  <div className="h-[600px] flex items-center justify-center">
                    <div className="text-center space-y-4">
                      <div className="w-20 h-20 mx-auto rounded-full bg-muted flex items-center justify-center">
                        <Mail className="w-10 h-10 text-muted-foreground opacity-50" />
                      </div>
                      <div className="space-y-2">
                        <p className="text-lg font-semibold text-foreground">No email selected</p>
                        <p className="text-sm text-muted-foreground">Click on an email from the list to view its details</p>
                      </div>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Chat Tab */}
        <TabsContent value="chat" className="space-y-4">
          <EmailChat emails={emails} />
        </TabsContent>

        {/* Vector Database Tab */}
        <TabsContent value="vector">
          <VectorViewer />
        </TabsContent>

        {/* Auto Replies Tab */}
        <TabsContent value="mongodb">
          <MongoDBViewer />
        </TabsContent>
      </Tabs>
      </div>
    </>
  );
}

