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
  const [dateFilter, setDateFilter] = useState<string>('all');
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
        return { from: format(today, 'yyyy-MM-dd') };
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
      case 'all':
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
      
      // Use higher limit for filtered queries to get all emails in the date range
      const limit = (dateFilter !== 'all' || unreadOnly) ? 200 : 20;
      
      const response = await api.getEmails(limit, unreadOnly, 'INBOX', from, to);
      setEmails(response.emails);
    } catch (error) {
      console.error('Failed to load emails:', error);
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
      const response = await api.generateResponse(selectedEmail.id, 'professional');
      setAiResponse(response.response);
      setReplyBody(response.response);
    } catch (error) {
      console.error('Failed to generate AI response:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSendReply = async () => {
    if (!selectedEmail || !replyBody.trim()) return;

    setLoading(true);
    try {
      await api.replyToEmail(selectedEmail.id, replyBody);
      alert('Reply sent successfully!');
      setReplyBody('');
      setAiResponse('');
    } catch (error) {
      console.error('Failed to send reply:', error);
      alert('Failed to send reply');
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
      urgent: 'destructive',
      important: 'default',
      spam: 'secondary',
      promotional: 'outline',
      personal: 'default',
      work: 'default',
      newsletter: 'secondary',
    };
    return colors[category] || 'outline';
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
        <TabsList className="grid w-full grid-cols-7">
          <TabsTrigger value="mongodb" className="flex items-center gap-2">
            <Database className="w-4 h-4" />
            MongoDB
          </TabsTrigger>
          <TabsTrigger value="inbox" className="flex items-center gap-2">
            <Inbox className="w-4 h-4" />
            Inbox
          </TabsTrigger>
          <TabsTrigger value="unread" className="flex items-center gap-2">
            <MailOpen className="w-4 h-4" />
            Unread
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
          <TabsTrigger value="search" className="flex items-center gap-2">
            <Search className="w-4 h-4" />
            Search
          </TabsTrigger>
          <TabsTrigger value="stats" className="flex items-center gap-2">
            <TrendingUp className="w-4 h-4" />
            Statistics
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
                  <SelectItem value="all">All Emails</SelectItem>
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

              {dateFilter !== 'all' && dateFilter !== 'custom' && (
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
                  {dateFilter !== 'all' && emails.length >= 200 && (
                    <Badge variant="secondary" className="text-xs">
                      Limited to 200 (max reached)
                    </Badge>
                  )}
                  {dateFilter !== 'all' && emails.length < 200 && emails.length > 0 && (
                    <Badge variant="outline" className="text-xs">
                      All emails loaded
                    </Badge>
                  )}
                </CardTitle>
                <CardDescription>Click to view details</CardDescription>
              </CardHeader>
              <CardContent>
                <ScrollArea className="h-[600px]">
                  <div className="space-y-2">
                    {emails.map((email) => (
                      <Card
                        key={email.id}
                        className={`cursor-pointer transition-all hover:shadow-md ${
                          selectedEmail?.id === email.id ? 'ring-2 ring-primary' : ''
                        }`}
                        onClick={() => setSelectedEmail(email)}
                      >
                        <CardContent className="pt-4">
                          <div className="space-y-2">
                            <div className="flex items-start justify-between">
                              <h3 className="font-semibold line-clamp-1">{email.subject}</h3>
                              {email.ai_analysis?.category && (
                                <Badge variant={getCategoryColor(email.ai_analysis.category) as any}>
                                  {email.ai_analysis.category}
                                </Badge>
                              )}
                            </div>
                            <p className="text-sm text-muted-foreground line-clamp-1">
                              {email.from}
                            </p>
                            <p className="text-xs text-muted-foreground">
                              {formatDate(email.date)}
                            </p>
                            {email.has_attachments && (
                              <Badge variant="outline" className="text-xs">
                                📎 {email.attachments.length} attachment(s)
                              </Badge>
                            )}
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                    {emails.length === 0 && (
                      <div className="text-center py-12 text-muted-foreground">
                        <Mail className="w-12 h-12 mx-auto mb-4 opacity-50" />
                        <p>No emails loaded. Click "Load Emails" to fetch.</p>
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
                    <div className="space-y-4">
                      <div>
                        <h3 className="text-2xl font-bold">{selectedEmail.subject}</h3>
                        <Separator className="my-4" />
                        <div className="space-y-2 text-sm">
                          <p><strong>From:</strong> {selectedEmail.from}</p>
                          <p><strong>To:</strong> {selectedEmail.to}</p>
                          <p><strong>Date:</strong> {formatDate(selectedEmail.date)}</p>
                        </div>
                      </div>

                      {selectedEmail.ai_analysis && (
                        <Card className="bg-muted/50">
                          <CardHeader>
                            <CardTitle className="text-sm flex items-center gap-2">
                              <Sparkles className="w-4 h-4" />
                              AI Analysis
                            </CardTitle>
                          </CardHeader>
                          <CardContent className="space-y-2 text-sm">
                            <div className="flex items-center gap-2">
                              <span className="font-semibold">Category:</span>
                              <Badge variant={getCategoryColor(selectedEmail.ai_analysis.category) as any}>
                                {selectedEmail.ai_analysis.category}
                              </Badge>
                            </div>
                            {selectedEmail.ai_analysis.urgency_score > 6 && (
                              <div className="flex items-center gap-2 text-orange-600">
                                <AlertCircle className="w-4 h-4" />
                                <span>High Urgency ({selectedEmail.ai_analysis.urgency_score}/10)</span>
                              </div>
                            )}
                            {selectedEmail.ai_analysis.summary && (
                              <div>
                                <span className="font-semibold">Summary:</span>
                                <p className="mt-1">{selectedEmail.ai_analysis.summary}</p>
                              </div>
                            )}
                          </CardContent>
                        </Card>
                      )}

                      <div>
                        <h4 className="font-semibold mb-2">Message:</h4>
                        <Card>
                          <CardContent className="pt-4">
                            <div className="whitespace-pre-wrap text-sm">
                              {selectedEmail.text_body || 'No text content'}
                            </div>
                          </CardContent>
                        </Card>
                      </div>

                      <Separator />

                      <div className="space-y-3">
                        <div className="flex gap-2">
                          <Button
                            onClick={handleGenerateAIResponse}
                            disabled={loading}
                            className="flex-1"
                          >
                            <Sparkles className="w-4 h-4 mr-2" />
                            Generate AI Response
                          </Button>
                        </div>

                        {aiResponse && (
                          <Card className="bg-green-50 dark:bg-green-950">
                            <CardHeader>
                              <CardTitle className="text-sm">AI Generated Response</CardTitle>
                            </CardHeader>
                            <CardContent>
                              <p className="text-sm whitespace-pre-wrap">{aiResponse}</p>
                            </CardContent>
                          </Card>
                        )}

                        <div className="space-y-2">
                          <label className="text-sm font-semibold">Your Reply:</label>
                          <Textarea
                            placeholder="Type your reply here..."
                            value={replyBody}
                            onChange={(e) => setReplyBody(e.target.value)}
                            rows={6}
                          />
                          <Button
                            onClick={handleSendReply}
                            disabled={loading || !replyBody.trim()}
                            className="w-full"
                          >
                            <Send className="w-4 h-4 mr-2" />
                            Send Reply
                          </Button>
                        </div>
                      </div>
                    </div>
                  </ScrollArea>
                ) : (
                  <div className="h-[600px] flex items-center justify-center text-muted-foreground">
                    <div className="text-center">
                      <Mail className="w-16 h-16 mx-auto mb-4 opacity-50" />
                      <p>Select an email to view details</p>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Unread Tab */}
        <TabsContent value="unread">
          <Button onClick={() => loadEmails(true)} disabled={loading}>
            <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Load Unread Emails
          </Button>
          <p className="text-sm text-muted-foreground mt-2">
            Same view as inbox, but filtered for unread emails only
          </p>
        </TabsContent>

        {/* Chat Tab */}
        <TabsContent value="chat" className="space-y-4">
          <EmailChat emails={emails} />
        </TabsContent>

        {/* Search Tab */}
        <TabsContent value="search" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Search Emails</CardTitle>
              <CardDescription>Search by keywords, sender, or subject</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex gap-2">
                <Input
                  placeholder="Enter search query..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
                />
                <Button onClick={handleSearch} disabled={loading}>
                  <Search className="w-4 h-4 mr-2" />
                  Search
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Statistics Tab */}
        <TabsContent value="stats" className="space-y-4">
          <Button onClick={loadStatistics} disabled={loading}>
            <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Load Statistics
          </Button>

          {stats && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">Total Emails</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-3xl font-bold">{stats.total_emails}</p>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">With Attachments</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-3xl font-bold">{stats.with_attachments}</p>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">Avg Urgency</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-3xl font-bold">{stats.average_urgency.toFixed(1)}/10</p>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">Spam Detected</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-3xl font-bold text-red-600">{stats.spam_count}</p>
                </CardContent>
              </Card>

              <Card className="md:col-span-2 lg:col-span-4">
                <CardHeader>
                  <CardTitle>Categories</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    {Object.entries(stats.categories).map(([category, count]) => (
                      <div key={category} className="text-center p-4 border rounded-lg">
                        <Badge variant={getCategoryColor(category) as any} className="mb-2">
                          {category}
                        </Badge>
                        <p className="text-2xl font-bold">{count}</p>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </div>
          )}
        </TabsContent>

        {/* Vector Database Tab */}
        <TabsContent value="vector">
          <VectorViewer />
        </TabsContent>

        {/* MongoDB Storage Tab */}
        <TabsContent value="mongodb">
          <MongoDBViewer />
        </TabsContent>
      </Tabs>
      </div>
    </>
  );
}

