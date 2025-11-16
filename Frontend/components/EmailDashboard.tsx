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
import AttachmentList from '@/components/AttachmentList';
import AttachmentViewer from '@/components/AttachmentViewer';
import {
  Mail,
  RefreshCw,
  Send,
  Sparkles,
  Inbox,
  MailOpen,
  AlertCircle,
  Bot,
  ArrowLeft,
  MessageSquare,
  Filter,
  X,
  Calendar as CalendarIcon,
  LogOut,
  ChevronLeft,
  ChevronRight,
  FileText,
  X as XIcon,
  Check,
  Trash2,
  CheckCircle2,
  Clock,
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
import NotificationListener from './NotificationListener';
import { FRONTEND_VERSION } from '@/lib/version';

export default function EmailDashboard() {
  const router = useRouter();
  const [emails, setEmails] = useState<Email[]>([]);
  const [selectedEmail, setSelectedEmail] = useState<Email | null>(null);
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState<EmailStats | null>(null);
  const [healthStatus, setHealthStatus] = useState<{ status: string; email: string; ai_enabled: boolean; accounts_count?: number; version?: string } | null>(null);
  const [autoReplyEnabled, setAutoReplyEnabled] = useState<boolean>(false);
  const [customPrompt, setCustomPrompt] = useState<string>('');
  const [viewingAttachment, setViewingAttachment] = useState<{
    messageId: string;
    savedFilename: string;
    originalFilename: string;
    contentType: string;
  } | null>(null);
  const [customPromptValue, setCustomPromptValue] = useState<string>('');
  const [aiResponse, setAiResponse] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState('');
  const [replyBody, setReplyBody] = useState('');
  const [activeTab, setActiveTab] = useState('inbox');
  const [dateFilter, setDateFilter] = useState<string>('last30'); // Default to last 30 days for better email discovery
  const [customDateFrom, setCustomDateFrom] = useState<Date | undefined>(undefined);
  const [customDateTo, setCustomDateTo] = useState<Date | undefined>(undefined);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalEmails, setTotalEmails] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loadingEmails, setLoadingEmails] = useState(false);
  const [deletingAccount, setDeletingAccount] = useState<boolean>(false);
  const [vectorCount, setVectorCount] = useState<number>(0);
  const [emailFilter, setEmailFilter] = useState<'all' | 'auto-replied'>('all');
  const [emailAnalysis, setEmailAnalysis] = useState<any>(null);
  const [emailReply, setEmailReply] = useState<any>(null);
  const [loadingEmailDetails, setLoadingEmailDetails] = useState(false);
  const [emailDetailTab, setEmailDetailTab] = useState<'message' | 'analysis' | 'reply'>('message');
  const emailsPerPage = 20;

  // Load health status on mount
  useEffect(() => {
    checkHealth();
  }, []);

  // Load emails from MongoDB when inbox tab is active
  useEffect(() => {
    if (activeTab === 'inbox') {
      loadEmailsFromMongoDB();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, currentPage, dateFilter, customDateFrom, customDateTo]);

  // Fetch vector database count for chat tab badge
  useEffect(() => {
    const fetchVectorCount = async () => {
      try {
        console.log('🔍 Fetching vector count...');
        const response = await api.getVectorCount();
        console.log('📊 Vector count response:', response);
        if (response.success) {
          console.log(`✅ Vector count: ${response.count}`);
          setVectorCount(response.count);
        } else {
          console.warn('⚠️ Vector count fetch failed');
          setVectorCount(0);
        }
      } catch (error) {
        console.error('❌ Failed to fetch vector count:', error);
        setVectorCount(0);
      }
    };
    
    // Always fetch on mount, when switching to chat tab, or when emails are loaded
    fetchVectorCount();
    
    // Also refresh periodically (every 10 seconds) to catch new emails added to vector
    const interval = setInterval(fetchVectorCount, 10000);
    return () => clearInterval(interval);
  }, [activeTab, emails.length]);

  // Sync custom prompt value when switching to prompt tab
  useEffect(() => {
    if (activeTab === 'prompt') {
      // If custom prompt exists, use it; otherwise load default
      if (customPrompt) {
        setCustomPromptValue(customPrompt);
      } else {
        // Load default prompt if not already loaded
        if (!customPromptValue) {
          api.getDefaultPrompt().then(defaultPrompt => {
            setCustomPromptValue(defaultPrompt);
          }).catch(error => {
            console.error('Failed to load default prompt:', error);
          });
        }
      }
    }
  }, [activeTab, customPrompt]);

  // Clear reply body and AI response when a new email is selected
  useEffect(() => {
    if (selectedEmail) {
      setReplyBody('');
      setAiResponse('');
      setEmailAnalysis(null);
      setEmailReply(null);
      setEmailDetailTab('message'); // Reset to message tab when new email is selected
      
      // Load email details (AI analysis and reply) if message_id exists
      const messageId = selectedEmail.message_id || selectedEmail.id;
      if (messageId) {
        loadEmailDetails(messageId);
      }
    }
  }, [selectedEmail]);
  
  // Load email details (AI analysis and reply history)
  const loadEmailDetails = async (messageId: string) => {
    setLoadingEmailDetails(true);
    try {
      const response = await api.getEmailDetails(messageId);
      if (response.success) {
        setEmailAnalysis(response.analysis || null);
        setEmailReply(response.reply || null);
      }
    } catch (error) {
      console.error('Failed to load email details:', error);
      setEmailAnalysis(null);
      setEmailReply(null);
    } finally {
      setLoadingEmailDetails(false);
    }
  };

  const handleLogout = async () => {
    try {
      await api.logout();
      // Clear all local storage and cookies
      localStorage.clear();
      sessionStorage.clear();
      // Clear all cookies
      document.cookie.split(";").forEach((c) => {
        document.cookie = c
          .replace(/^ +/, "")
          .replace(/=.*/, "=;expires=" + new Date().toUTCString() + ";path=/");
      });
      // Force full page reload to clear all state
      window.location.href = '/login';
    } catch (error) {
      console.error('Logout error:', error);
      // Still clear everything and redirect even if logout API call fails
      localStorage.clear();
      sessionStorage.clear();
      window.location.href = '/login';
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
      
      // Also load custom prompt
      try {
        const prompt = await api.getActiveAccountCustomPrompt();
        setCustomPrompt(prompt);
        // If no custom prompt is set, load the default prompt
        if (!prompt) {
          try {
            const defaultPrompt = await api.getDefaultPrompt();
            setCustomPromptValue(defaultPrompt);
          } catch (defaultError) {
            console.error('Failed to load default prompt:', defaultError);
          }
        } else {
          setCustomPromptValue(prompt); // Initialize editor with current custom prompt
        }
      } catch (promptError: any) {
        console.error('Custom prompt load failed:', promptError);
        // Don't fail the whole health check if custom prompt fails
      }
    } catch (error: any) {
      console.error('Health check failed:', error);
      const errorMessage = error.message || String(error);
      if (errorMessage.includes('Cannot connect to backend')) {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
        console.error('⚠️ Backend connection failed. Please ensure:');
        console.error(`  1. Backend is running on ${apiUrl}`);
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

  const handleSaveCustomPrompt = async () => {
    try {
      // If the value matches the default prompt, save empty string to use default
      const defaultPrompt = await api.getDefaultPrompt();
      const promptToSave = customPromptValue.trim() === defaultPrompt.trim() ? '' : customPromptValue;
      
      await api.updateActiveAccountCustomPrompt(promptToSave);
      setCustomPrompt(promptToSave);
      
      if (promptToSave === '') {
        alert('Custom prompt cleared. Using default prompt.');
        // Reload default prompt in editor
        setCustomPromptValue(defaultPrompt);
      } else {
        alert('Custom prompt updated successfully!');
      }
    } catch (error) {
      console.error('Failed to save custom prompt:', error);
      alert(`Failed to save custom prompt: ${error}`);
    }
  };

  const handleDeleteAccount = async () => {
    if (!confirm('Are you sure you want to delete this account? This will permanently delete:\n- All emails in MongoDB\n- All data in Vector DB\n- The account itself\n\nThis action cannot be undone!')) {
      return;
    }

    setDeletingAccount(true);
    try {
      const activeAccount = await api.getActiveAccount();
      if (!activeAccount.success || !activeAccount.account) {
        throw new Error('No active account found');
      }

      const accountId = activeAccount.account.id;
      const result = await api.deleteAccount(accountId);

      if (result.success) {
        const remainingAccounts = result.remaining_accounts || 0;
        
        if (remainingAccounts === 0) {
          // Last account deleted - logout and redirect
          try {
            await api.logout();
          } catch (logoutError) {
            console.error('Logout error (continuing anyway):', logoutError);
          }
          
          // Clear all local storage and session data
          localStorage.clear();
          sessionStorage.clear();
          
          // Show alert and force redirect
          alert('Account deleted successfully. This was the last account. Logging out...');
          
          // Use window.location for a hard redirect
          window.location.href = '/login';
        } else {
          // Not the last account - reload
          alert(`Account deleted successfully. ${remainingAccounts} account(s) remaining.`);
          // Reload the page to refresh account state
          window.location.reload();
        }
      } else {
        throw new Error(result.message || 'Failed to delete account');
      }
    } catch (error) {
      console.error('Error deleting account:', error);
      alert(`Failed to delete account: ${error instanceof Error ? error.message : 'Unknown error'}`);
      setDeletingAccount(false);
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
    setCurrentPage(1); // Reset to first page when clearing dates
  };

  // Reset to page 1 when date filter changes
  useEffect(() => {
    setCurrentPage(1);
  }, [dateFilter, customDateFrom, customDateTo]);

  // Load emails from IMAP/Gmail API and upsert to MongoDB and vector DB
  const loadEmails = async (unreadOnly: boolean = false) => {
    setLoading(true);
    try {
      const { from, to } = getDateRange(dateFilter);
      
      // Backend now handles batch loading - request up to 1000 emails
      // Backend will automatically fetch all emails in the date range in batches
      const limit = 1000;
      
      const response = await api.getEmails(limit, unreadOnly, 'INBOX', from, to);
      
      // Check for errors in response
      const responseWithError = response as any;
      if (response.success === false || responseWithError.error) {
        console.error('Email loading error:', response);
        alert(`Failed to load emails: ${responseWithError.error || 'No active email account. Please add an account first.'}`);
        return;
      }
      
      const emailCount = response.count || 0;
      
      // Show appropriate message based on results
      if (emailCount === 0) {
        // Check if there are existing emails in MongoDB for this date range
        try {
          const { from, to } = getDateRange(dateFilter);
          const mongoResponse = await api.getMongoDBEmailsCount(from, to, false);
          
          if (mongoResponse.success && mongoResponse.count > 0) {
            // There are emails in MongoDB, just reload them
            const dateRangeText = dateFilter === 'today' 
              ? 'today' 
              : dateFilter === 'last7' 
                ? 'in the last 7 days'
                : dateFilter === 'last30'
                  ? 'in the last 30 days'
                  : dateFilter === 'thisMonth'
                    ? 'this month'
                    : dateFilter === 'thisYear'
                      ? 'this year'
                      : 'in the selected date range';
            
            // Reload from MongoDB to show existing emails
            await loadEmailsFromMongoDB();
            return; // Don't show alert, just reload from MongoDB
          }
        } catch (mongoError) {
          console.warn('Failed to check MongoDB for existing emails:', mongoError);
        }
        
        // No emails found in email account AND no emails in MongoDB
        const dateRangeText = dateFilter === 'today' 
          ? 'today' 
          : dateFilter === 'last7' 
            ? 'in the last 7 days'
            : dateFilter === 'last30'
              ? 'in the last 30 days'
              : dateFilter === 'thisMonth'
                ? 'this month'
                : dateFilter === 'thisYear'
                  ? 'this year'
                  : 'in the selected date range';
        
        alert(`No emails found ${dateRangeText}. Try selecting a different date range (e.g., "Last 7 Days" or "Last 30 Days") or check if your email account has emails.`);
      } else {
        // Show success message with method used
        const method = responseWithError.method || 'unknown';
        const methodText = method === 'gmail_api' ? 'Gmail API' : method === 'imap' ? 'IMAP' : method;
        alert(`✅ Loaded ${emailCount} email${emailCount === 1 ? '' : 's'} via ${methodText}. They have been saved to MongoDB and vector database.`);
        
        // Wait a moment for async save to complete, then reload from MongoDB
        // This ensures the newly loaded emails are visible in the inbox
        setTimeout(async () => {
          await loadEmailsFromMongoDB();
        }, 1000); // Wait 1 second for async MongoDB save to complete
      }
    } catch (error: any) {
      console.error('Failed to load emails:', error);
      const errorMessage = error.message || 'Failed to connect to backend. Please ensure the backend is running.';
      alert(`Error loading emails: ${errorMessage}`);
    } finally {
      setLoading(false);
    }
  };

  // Load emails from MongoDB with pagination (for inbox display)
  const loadEmailsFromMongoDB = async () => {
    setLoadingEmails(true);
    try {
      const { from, to } = getDateRange(dateFilter);
      const skip = (currentPage - 1) * emailsPerPage;
      
      console.log(`🔍 Loading emails from MongoDB: dateFilter=${dateFilter}, from=${from}, to=${to}, skip=${skip}, limit=${emailsPerPage}`);
      
      // Fetch emails first (required) - always show all emails
      const emailsResponse = await api.getMongoDBEmails(emailsPerPage, skip, from, to, false, false);
      
      console.log(`📧 MongoDB response:`, {
        success: emailsResponse.success,
        emailsCount: emailsResponse.emails?.length || 0,
        total: emailsResponse.total,
        count: emailsResponse.count
      });
      
      if (emailsResponse.success) {
        const emailsArray = emailsResponse.emails || [];
        console.log(`✅ Setting ${emailsArray.length} emails to state`);
        setEmails(emailsArray);
        
        // Try to get accurate count from count API (optional - fallback to emails response total)
        let accurateTotal = emailsResponse.total || 0;
        try {
          const countResponse = await api.getMongoDBEmailsCount(from, to, false);
          if (countResponse.success && countResponse.count !== undefined) {
            accurateTotal = countResponse.count;
          }
        } catch (countError) {
          // Count API failed, use total from emails response
          console.warn('Count API failed, using total from emails response:', countError);
        }
        
        setTotalEmails(accurateTotal);
        
        // Calculate has_more based on accurate total
        const hasMoreEmails = (skip + (emailsResponse.emails?.length || 0)) < accurateTotal;
        setHasMore(hasMoreEmails);
      } else {
        setEmails([]);
        setTotalEmails(0);
        setHasMore(false);
      }
    } catch (error: any) {
      console.error('❌ Failed to load emails from MongoDB:', error);
      console.error('Error details:', {
        message: error?.message,
        stack: error?.stack,
        response: error?.response
      });
      setEmails([]);
      setTotalEmails(0);
      setHasMore(false);
    } finally {
      setLoadingEmails(false);
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
      if (response.success && response.response) {
        const responseText = response.response.trim();
        console.log('AI Response received:', responseText);
        setAiResponse(responseText);
        setReplyBody(responseText);
        
        // Force React to update by using a small delay
        setTimeout(() => {
          setReplyBody(responseText);
        }, 0);
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
      
      <div className="container mx-auto p-4 sm:p-6 space-y-4 sm:space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl lg:text-4xl font-bold flex items-center gap-2 sm:gap-3">
            <Mail className="w-6 h-6 sm:w-8 sm:h-8 lg:w-10 lg:h-10 text-primary" />
            <span className="break-words">Email Agent Dashboard</span>
          </h1>
          <p className="text-muted-foreground mt-2 text-sm sm:text-base">
            AI-powered email management system
          </p>
          <div className="flex items-center gap-2 sm:gap-3 mt-1 flex-wrap">
            <Badge variant="outline" className="text-xs">
              FE: v{FRONTEND_VERSION}
            </Badge>
            {healthStatus?.version && (
              <Badge variant="outline" className="text-xs">
                BE: v{healthStatus.version}
              </Badge>
            )}
          </div>
        </div>
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2 sm:gap-4">
          {/* Account Manager - Hidden */}
          <div className="hidden">
            <AccountManager onAccountChange={handleAccountChange} />
          </div>

          {/* Status Card */}
          {healthStatus && (
            <Card>
              <CardContent className="pt-4 sm:pt-6">
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 sm:gap-2">
                  <div className="flex items-center gap-2 flex-wrap">
                    <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
                    <span className="text-xs sm:text-sm font-medium break-all">{healthStatus.email}</span>
                    {healthStatus.ai_enabled && (
                      <Badge variant="secondary" className="text-xs">
                        <Bot className="w-3 h-3 mr-1" />
                        AI Enabled
                      </Badge>
                    )}
                  </div>
                  <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2">
                    <Button
                      onClick={toggleAutoReply}
                      variant={autoReplyEnabled ? "default" : "outline"}
                      size="sm"
                      className={`${autoReplyEnabled ? "bg-green-600 hover:bg-green-700" : ""} w-full sm:w-auto`}
                    >
                      <Bot className="w-4 h-4 mr-2" />
                      <span className="hidden sm:inline">{autoReplyEnabled ? "Auto-Reply ON" : "Auto-Reply OFF"}</span>
                      <span className="sm:hidden">{autoReplyEnabled ? "ON" : "OFF"}</span>
                    </Button>
                    
                    {/* Custom Prompt Indicator */}
                    {customPrompt && (
                      <Badge variant="outline" className="flex items-center gap-1 text-xs">
                        <FileText className="w-3 h-3" />
                        <span className="hidden sm:inline">Custom Prompt Set</span>
                        <span className="sm:hidden">Custom</span>
                      </Badge>
                    )}

                    {/* Delete Account Button */}
                    <Button
                      onClick={handleDeleteAccount}
                      variant="destructive"
                      size="sm"
                      disabled={deletingAccount}
                      className="flex items-center gap-2 w-full sm:w-auto"
                      title="Delete this account and all its data"
                    >
                      {deletingAccount ? (
                        <>
                          <RefreshCw className="w-4 h-4 animate-spin" />
                          <span className="hidden sm:inline">Deleting...</span>
                          <span className="sm:hidden">Deleting</span>
                        </>
                      ) : (
                        <>
                          <Trash2 className="w-4 h-4" />
                          <span className="hidden sm:inline">Delete Account</span>
                          <span className="sm:hidden">Delete</span>
                        </>
                      )}
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Logout Button */}
          <Button
            variant="outline"
            size="sm"
            onClick={handleLogout}
            className="flex items-center gap-2 w-full sm:w-auto"
          >
            <LogOut className="w-4 h-4" />
            Logout
          </Button>
        </div>
      </div>

      {/* Main Content */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
        <TabsList className="grid w-full grid-cols-2 sm:grid-cols-3 gap-1 sm:gap-0">
          <TabsTrigger value="inbox" className="flex items-center gap-1 sm:gap-2 text-xs sm:text-sm">
            <Inbox className="w-3 h-3 sm:w-4 sm:h-4" />
            Inbox
          </TabsTrigger>
          <TabsTrigger value="chat" className="flex items-center gap-1 sm:gap-2 text-xs sm:text-sm">
            <MessageSquare className="w-3 h-3 sm:w-4 sm:h-4" />
            Chat
            {vectorCount > 0 && (
              <Badge variant="secondary" className="ml-1 h-4 sm:h-5 px-1 text-xs">
                {vectorCount}
              </Badge>
            )}
          </TabsTrigger>
          <TabsTrigger value="prompt" className="flex items-center gap-1 sm:gap-2 text-xs sm:text-sm">
            <FileText className="w-3 h-3 sm:w-4 sm:h-4" />
            <span className="hidden sm:inline">Custom Prompt</span>
            <span className="sm:hidden">Prompt</span>
            {customPrompt && (
              <Badge variant="secondary" className="ml-1 h-4 sm:h-5 px-1 text-xs">
                Set
              </Badge>
            )}
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
                <SelectTrigger className="w-full sm:w-[200px]">
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

              <Button 
                onClick={() => loadEmailsFromMongoDB()} 
                disabled={loadingEmails}
                variant="outline"
                size="sm"
              >
                <RefreshCw className={`w-4 h-4 mr-2 ${loadingEmails ? 'animate-spin' : ''}`} />
                Refresh
              </Button>

              <Button onClick={() => loadEmails(false)} disabled={loading}>
                <Mail className="w-4 h-4 mr-2" />
                Load Emails
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
                          className="w-full sm:w-[200px] justify-start text-left font-normal"
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
                          className="w-full sm:w-[200px] justify-start text-left font-normal"
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
                  <span>Emails {totalEmails > 0 && `(${totalEmails} total)`}</span>
                  {loadingEmails && (
                    <Badge variant="secondary" className="text-xs">
                      <RefreshCw className="w-3 h-3 mr-1 animate-spin" />
                      Loading...
                    </Badge>
                  )}
                </CardTitle>
                <CardDescription>
                  Showing {emails.length > 0 ? (currentPage - 1) * emailsPerPage + 1 : 0} - {Math.min(currentPage * emailsPerPage, totalEmails)} of {totalEmails} emails (20 per page)
                </CardDescription>
              </CardHeader>
              <CardContent>
                <ScrollArea className="h-[400px] sm:h-[500px] lg:h-[600px] pr-2 sm:pr-4">
                  {loadingEmails ? (
                    <div className="flex items-center justify-center h-[400px]">
                      <div className="text-center">
                        <RefreshCw className="w-8 h-8 animate-spin mx-auto mb-4 text-muted-foreground" />
                        <p className="text-muted-foreground">Loading emails...</p>
                      </div>
                    </div>
                  ) : emails.length === 0 ? (
                    <div className="flex items-center justify-center h-[400px]">
                      <div className="text-center">
                        <Mail className="w-12 h-12 mx-auto mb-4 text-muted-foreground opacity-50" />
                        <p className="text-muted-foreground">No emails found</p>
                        <p className="text-sm text-muted-foreground mt-2">Click "Load Emails" to fetch from your email account</p>
                      </div>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {emails.map((email, idx) => (
                      <Card
                        key={email.message_id || email.id || idx}
                        className={`cursor-pointer transition-colors hover:bg-accent ${
                          (selectedEmail?.message_id || selectedEmail?.id) === (email.message_id || email.id) ? 'bg-accent' : ''
                        }`}
                        onClick={async () => {
                          // Set selected email immediately for UI feedback
                          setSelectedEmail(email);
                          
                          // If email has message_id, fetch full body from MongoDB
                          if (email.message_id) {
                            try {
                              const fullEmail = await api.getSingleEmail(email.message_id);
                              if (fullEmail.success && fullEmail.email) {
                                // Update selected email with full body content
                                setSelectedEmail(fullEmail.email);
                              }
                            } catch (error) {
                              console.error('Failed to fetch email body:', error);
                              // Keep the email selected even if body fetch fails
                            }
                          }
                        }}
                      >
                        <CardContent className="p-4">
                          <div className="space-y-2">
                            <div className="flex items-start justify-between gap-2">
                              <h3 className="font-semibold line-clamp-1">
                                {email.subject || 'No Subject'}
                              </h3>
                              <Badge variant="outline" className="text-xs shrink-0">
                                #{(currentPage - 1) * emailsPerPage + idx + 1}
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
                    </div>
                  )}
                </ScrollArea>
                
                {/* Pagination Controls */}
                {!loadingEmails && emails.length > 0 && (
                  <div className="flex items-center justify-between mt-4 pt-4 border-t">
                    <div className="text-sm text-muted-foreground">
                      Page {currentPage} of {Math.ceil(totalEmails / emailsPerPage) || 1}
                    </div>
                    <div className="flex items-center gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                        disabled={currentPage === 1 || loadingEmails}
                      >
                        <ChevronLeft className="w-4 h-4" />
                        Previous
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setCurrentPage(prev => prev + 1)}
                        disabled={!hasMore || loadingEmails}
                      >
                        Next
                        <ChevronRight className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>
                )}
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
                  <ScrollArea className="h-[400px] sm:h-[500px] lg:h-[600px]">
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

                      {/* Tabs for Message, AI Analysis, and Reply */}
                      <Tabs value={emailDetailTab} onValueChange={(v) => setEmailDetailTab(v as 'message' | 'analysis' | 'reply')} className="mt-4">
                        <TabsList className="grid w-full grid-cols-3">
                          <TabsTrigger value="message" className="flex items-center gap-2">
                            <MailOpen className="w-4 h-4" />
                            <span className="hidden sm:inline">Message</span>
                          </TabsTrigger>
                          <TabsTrigger value="analysis" className="flex items-center gap-2">
                            <Sparkles className="w-4 h-4" />
                            <span className="hidden sm:inline">AI Analysis</span>
                            {loadingEmailDetails && (
                              <RefreshCw className="w-3 h-3 animate-spin" />
                            )}
                          </TabsTrigger>
                          <TabsTrigger value="reply" className="flex items-center gap-2">
                            <MessageSquare className="w-4 h-4" />
                            <span className="hidden sm:inline">Reply</span>
                            {emailReply && (
                              <CheckCircle2 className="w-3 h-3 text-green-600" />
                            )}
                          </TabsTrigger>
                        </TabsList>

                        {/* Message Tab */}
                        <TabsContent value="message" className="space-y-4 mt-4">
                          <div className="space-y-3">
                            <h4 className="font-semibold text-base flex items-center gap-2">
                              <MailOpen className="w-4 h-4" />
                              Message Content
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

                          {/* Attachments */}
                          {selectedEmail.message_id && (
                            <div className="space-y-3">
                              <h4 className="font-semibold text-base flex items-center gap-2">
                                <FileText className="w-4 h-4" />
                                Attachments
                              </h4>
                              <AttachmentList 
                                messageId={selectedEmail.message_id} 
                                compact={false}
                              />
                            </div>
                          )}
                        </TabsContent>

                        {/* AI Analysis Tab */}
                        <TabsContent value="analysis" className="space-y-4 mt-4">
                          {loadingEmailDetails ? (
                            <Card className="bg-gradient-to-br from-blue-50 to-purple-50 dark:from-blue-950/30 dark:to-purple-950/30 border-blue-200 dark:border-blue-800">
                              <CardContent className="pt-6">
                                <div className="flex items-center justify-center py-8">
                                  <RefreshCw className="w-5 h-5 animate-spin text-blue-600 dark:text-blue-400 mr-3" />
                                  <span className="text-sm text-blue-700 dark:text-blue-300">Loading analysis...</span>
                                </div>
                              </CardContent>
                            </Card>
                          ) : emailAnalysis ? (
                            <Card className="bg-gradient-to-br from-blue-50 via-purple-50 to-indigo-50 dark:from-blue-950/40 dark:via-purple-950/40 dark:to-indigo-950/40 border-blue-200 dark:border-blue-800">
                              <CardHeader className="pb-3">
                                <CardTitle className="text-base flex items-center gap-2 text-blue-700 dark:text-blue-300">
                                  <Sparkles className="w-4 h-4 text-blue-600 dark:text-blue-400" />
                                  AI Analysis
                                </CardTitle>
                              </CardHeader>
                              <CardContent className="space-y-4 text-sm">
                                <div className="flex items-center gap-2">
                                  <span className="font-semibold text-muted-foreground">Category:</span>
                                  <Badge className={`${getCategoryColor(emailAnalysis.category)} text-xs`}>
                                    {emailAnalysis.category}
                                  </Badge>
                                </div>
                                
                                {emailAnalysis.urgency_score !== undefined && (
                                  <div className={`flex items-center gap-2 p-3 rounded-md ${
                                    emailAnalysis.urgency_score > 6 
                                      ? 'bg-orange-50 dark:bg-orange-950/30 border border-orange-200 dark:border-orange-800' 
                                      : 'bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800'
                                  }`}>
                                    <AlertCircle className={`w-4 h-4 ${
                                      emailAnalysis.urgency_score > 6 
                                        ? 'text-orange-600 dark:text-orange-400' 
                                        : 'text-blue-600 dark:text-blue-400'
                                    }`} />
                                    <span className={`font-medium ${
                                      emailAnalysis.urgency_score > 6 
                                        ? 'text-orange-700 dark:text-orange-300' 
                                        : 'text-blue-700 dark:text-blue-300'
                                    }`}>
                                      Urgency Score: {emailAnalysis.urgency_score}/10
                                      {emailAnalysis.urgency_score > 6 && ' (High Urgency)'}
                                    </span>
                                  </div>
                                )}

                                {emailAnalysis.sentiment && (
                                  <div className="flex items-center gap-2">
                                    <span className="font-semibold text-muted-foreground">Sentiment:</span>
                                    <Badge variant="outline" className="text-xs">
                                      {emailAnalysis.sentiment}
                                    </Badge>
                                  </div>
                                )}

                                {emailAnalysis.is_spam !== undefined && (
                                  <div className="flex items-center gap-2">
                                    <span className="font-semibold text-muted-foreground">Spam:</span>
                                    <Badge variant={emailAnalysis.is_spam ? "destructive" : "outline"} className="text-xs">
                                      {emailAnalysis.is_spam ? "Yes" : "No"}
                                    </Badge>
                                  </div>
                                )}

                                {emailAnalysis.summary && (
                                  <div className="pt-3 border-t">
                                    <span className="font-semibold text-muted-foreground block mb-2">Summary:</span>
                                    <p className="text-foreground leading-relaxed">{emailAnalysis.summary}</p>
                                  </div>
                                )}

                                {emailAnalysis.key_points && emailAnalysis.key_points.length > 0 && (
                                  <div className="pt-3 border-t">
                                    <span className="font-semibold text-muted-foreground block mb-2">Key Points:</span>
                                    <ul className="list-disc list-inside space-y-1.5">
                                      {emailAnalysis.key_points.map((point: string, idx: number) => (
                                        <li key={idx} className="text-foreground">{point}</li>
                                      ))}
                                    </ul>
                                  </div>
                                )}

                                {emailAnalysis.tags && emailAnalysis.tags.length > 0 && (
                                  <div className="pt-3 border-t">
                                    <span className="font-semibold text-muted-foreground block mb-2">Tags:</span>
                                    <div className="flex flex-wrap gap-2">
                                      {emailAnalysis.tags.map((tag: string, idx: number) => (
                                        <Badge key={idx} variant="secondary" className="text-xs">
                                          {tag}
                                        </Badge>
                                      ))}
                                    </div>
                                  </div>
                                )}

                                {emailAnalysis.action_required !== undefined && (
                                  <div className="pt-3 border-t">
                                    <div className="flex items-center gap-2">
                                      <span className="font-semibold text-muted-foreground">Action Required:</span>
                                      <Badge variant={emailAnalysis.action_required ? "default" : "outline"} className="text-xs">
                                        {emailAnalysis.action_required ? "Yes" : "No"}
                                      </Badge>
                                    </div>
                                  </div>
                                )}

                                {emailAnalysis.suggested_response && (
                                  <div className="pt-3 border-t">
                                    <span className="font-semibold text-muted-foreground block mb-2">Suggested Response:</span>
                                    <div className="whitespace-pre-wrap text-foreground leading-relaxed bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 p-3 rounded-md">
                                      {emailAnalysis.suggested_response}
                                    </div>
                                  </div>
                                )}
                              </CardContent>
                            </Card>
                          ) : (
                            <Card className="bg-gradient-to-br from-blue-50 to-purple-50 dark:from-blue-950/30 dark:to-purple-950/30 border-blue-200 dark:border-blue-800">
                              <CardContent className="pt-6">
                                <div className="text-center py-8">
                                  <Sparkles className="w-12 h-12 mx-auto mb-4 text-blue-500 dark:text-blue-400 opacity-70" />
                                  <p className="text-blue-700 dark:text-blue-300">No AI analysis available for this email</p>
                                </div>
                              </CardContent>
                            </Card>
                          )}
                        </TabsContent>

                        {/* Reply Tab */}
                        <TabsContent value="reply" className="space-y-4 mt-4">
                          {/* Auto-Reply History */}
                          {emailReply ? (
                            <Card className="bg-gradient-to-br from-green-50 to-emerald-50 dark:from-green-950/30 dark:to-emerald-950/30 border-green-200 dark:border-green-800">
                              <CardHeader className="pb-3">
                                <CardTitle className="text-sm flex items-center gap-2 text-green-700 dark:text-green-300">
                                  <CheckCircle2 className="w-4 h-4" />
                                  Auto-Reply Sent
                                  {emailReply.success && (
                                    <Badge variant="outline" className="ml-2 bg-green-100 dark:bg-green-900 text-green-700 dark:text-green-300 border-green-300 dark:border-green-700">
                                      Success
                                    </Badge>
                                  )}
                                </CardTitle>
                              </CardHeader>
                              <CardContent className="space-y-3 text-sm">
                                <div className="flex items-center gap-2 text-muted-foreground">
                                  <Clock className="w-4 h-4" />
                                  <span>Sent: {new Date(emailReply.sent_at).toLocaleString()}</span>
                                </div>
                                {emailReply.to && (
                                  <div className="flex items-center gap-2">
                                    <span className="font-semibold text-muted-foreground">To:</span>
                                    <span className="text-foreground">{emailReply.to}</span>
                                  </div>
                                )}
                                {emailReply.subject && (
                                  <div className="flex items-center gap-2">
                                    <span className="font-semibold text-muted-foreground">Subject:</span>
                                    <span className="text-foreground">{emailReply.subject}</span>
                                  </div>
                                )}
                                <div className="pt-2 border-t">
                                  <span className="font-semibold text-muted-foreground block mb-2">Reply Body:</span>
                                  <div className="whitespace-pre-wrap text-foreground leading-relaxed bg-background p-3 rounded-md border">
                                    {emailReply.body}
                                  </div>
                                </div>
                              </CardContent>
                            </Card>
                          ) : (
                            <Card className="bg-muted/30">
                              <CardContent className="pt-6">
                                <div className="text-center py-4">
                                  <MessageSquare className="w-12 h-12 mx-auto mb-4 text-muted-foreground opacity-50" />
                                  <p className="text-muted-foreground mb-4">No auto-reply sent for this email</p>
                                </div>
                              </CardContent>
                            </Card>
                          )}

                          <Separator />

                          {/* Manual Reply Section */}
                          <div className="space-y-4">
                            <div className="flex items-center justify-between">
                              <h4 className="font-semibold text-base flex items-center gap-2">
                                <Send className="w-4 h-4" />
                                Send Reply
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
                              <button
                                onClick={handleSendReply}
                                disabled={loading || !replyBody.trim()}
                                className="w-full h-10 rounded-md bg-primary text-primary-foreground hover:bg-primary/90 text-sm font-medium transition-all disabled:pointer-events-none disabled:opacity-50"
                                style={{ 
                                  display: 'flex', 
                                  alignItems: 'center', 
                                  justifyContent: 'center',
                                  gap: '0.5rem',
                                  paddingLeft: '1rem',
                                  paddingRight: '1rem',
                                  width: '100%',
                                  textAlign: 'center'
                                }}
                              >
                                <Send className="w-4 h-4" style={{ flexShrink: 0, margin: 0 }} />
                                <span style={{ whiteSpace: 'nowrap', margin: 0, padding: 0 }}>Send Reply</span>
                              </button>
                            </div>
                          </div>
                        </TabsContent>
                      </Tabs>
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
          <EmailChat emails={emails} vectorCount={vectorCount} />
        </TabsContent>

        {/* Custom Prompt Tab */}
        <TabsContent value="prompt" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FileText className="w-5 h-5" />
                Custom AI Prompt
              </CardTitle>
              <CardDescription>
                Set a custom prompt to guide how the AI generates email responses. This prompt will override the default behavior and be used for all auto-replies and manual AI-generated responses for your account.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">Custom Prompt</label>
                <Textarea
                  value={customPromptValue || customPrompt}
                  onChange={(e) => setCustomPromptValue(e.target.value)}
                  placeholder={`Enter your custom prompt here...

Example:
You are a friendly customer service representative. Always be polite, concise, and helpful. Address the customer's concerns directly without unnecessary formalities.`}
                  className="min-h-[400px] font-mono text-sm resize-y"
                  rows={15}
                />
                <p className="text-xs text-muted-foreground">
                  The email context (From, Subject, Body) will be automatically appended to your prompt. The AI will still format responses with "Best regards," and your name at the end.
                </p>
              </div>
              
              <div className="flex items-center justify-between pt-4 border-t">
                <div className="text-sm text-muted-foreground">
                  {customPrompt ? (
                    <span className="flex items-center gap-2">
                      <Check className="w-4 h-4 text-green-500" />
                      Custom prompt is active
                    </span>
                  ) : (
                    <span className="flex items-center gap-2">
                      <FileText className="w-4 h-4 text-muted-foreground" />
                      Using default prompt (shown above)
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    onClick={async () => {
                      try {
                        const defaultPrompt = await api.getDefaultPrompt();
                        setCustomPromptValue(defaultPrompt);
                      } catch (error) {
                        console.error('Failed to load default prompt:', error);
                        alert('Failed to load default prompt');
                      }
                    }}
                    className="gap-2"
                  >
                    <RefreshCw className="w-4 h-4" />
                    Reset to Default
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => {
                      setCustomPromptValue(customPrompt || '');
                    }}
                    disabled={customPromptValue === (customPrompt || '')}
                  >
                    <XIcon className="w-4 h-4 mr-2" />
                    Undo Changes
                  </Button>
                  <Button
                    onClick={handleSaveCustomPrompt}
                    disabled={customPromptValue === (customPrompt || '')}
                    className="gap-2"
                  >
                    <Check className="w-4 h-4" />
                    Save Prompt
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
      </div>

      {/* Attachment Viewer Modal */}
      {viewingAttachment && (
        <AttachmentViewer
          messageId={viewingAttachment.messageId}
          savedFilename={viewingAttachment.savedFilename}
          originalFilename={viewingAttachment.originalFilename}
          contentType={viewingAttachment.contentType}
          onClose={() => setViewingAttachment(null)}
        />
      )}
    </>
  );
}

