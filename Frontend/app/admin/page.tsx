'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { 
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { 
  Mail, 
  CheckCircle, 
  XCircle, 
  Calendar,
  Database,
  Users,
  Activity,
  Trash2,
  RefreshCw,
  Bot,
  Search
} from 'lucide-react';
import { Switch } from '@/components/ui/switch';

interface Account {
  id: number;
  email: string;
  imap_server: string;
  imap_port: number;
  smtp_server: string;
  smtp_port: number;
  is_active: boolean;
  auto_reply_enabled?: boolean;
  custom_prompt?: string;
  created_at: string;
}

interface Stats {
  total: number;
  active: number;
  inactive: number;
}

export default function AdminPage() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState<Stats>({ total: 0, active: 0, inactive: 0 });
  const [globalAutoReply, setGlobalAutoReply] = useState(false);
  const [cleaningVector, setCleaningVector] = useState(false);
  const [deletingAll, setDeletingAll] = useState(false);
  const [editingPromptAccountId, setEditingPromptAccountId] = useState<number | null>(null);
  const [customPromptValue, setCustomPromptValue] = useState<string>('');

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  useEffect(() => {
    loadAccounts();
    loadGlobalAutoReply();
  }, []);

  const loadAccounts = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${apiUrl}/api/accounts`);
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      const data = await response.json();
      
      if (data.success) {
        const formattedAccounts = data.accounts.map((acc: Account & { id?: string | number }) => ({
          ...acc,
          id: typeof acc.id === 'string' ? parseInt(acc.id, 10) : acc.id
        })) as Account[];
        
        setAccounts(formattedAccounts);
        
        // Calculate stats
        const total = formattedAccounts.length;
        const active = formattedAccounts.filter((acc: Account) => acc.is_active).length;
        setStats({
          total,
          active,
          inactive: total - active
        });
      }
    } catch (error) {
      console.error('Failed to load accounts:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteAccount = async (accountId: number, email: string) => {
    if (!confirm(`Are you sure you want to delete account: ${email}?`)) {
      return;
    }

    try {
      const response = await fetch(`${apiUrl}/api/accounts/${accountId}`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        throw new Error('Failed to delete account');
      }

      alert('Account deleted successfully');
      loadAccounts(); // Reload accounts
    } catch (error) {
      console.error('Error deleting account:', error);
      alert('Failed to delete account');
    }
  };

  const handleActivateAccount = async (accountId: number, email: string) => {
    try {
      // Toggle mode - allows multiple active accounts
      const response = await fetch(`${apiUrl}/api/accounts/${accountId}/activate?toggle=true`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error('Failed to toggle account status');
      }

      const data = await response.json();
      const status = data.is_active ? 'activated' : 'deactivated';
      alert(`Account ${email} has been ${status}`);
      loadAccounts(); // Reload accounts
    } catch (error) {
      console.error('Error toggling account:', error);
      alert('Failed to toggle account status');
    }
  };

  const loadGlobalAutoReply = async () => {
    try {
      const response = await fetch(`${apiUrl}/api/auto-reply/status`);
      if (response.ok) {
        const data = await response.json();
        setGlobalAutoReply(data.auto_reply_enabled || false);
      }
    } catch (error) {
      console.error('Failed to load global auto-reply status:', error);
    }
  };

  const handleToggleGlobalAutoReply = async (enabled: boolean) => {
    try {
      const response = await fetch(`${apiUrl}/api/auto-reply/toggle?enabled=${enabled}`, {
        method: 'POST',
      });

      if (!response.ok) {
        throw new Error('Failed to toggle global auto-reply');
      }

      setGlobalAutoReply(enabled);
      alert(`Global auto-reply ${enabled ? 'enabled' : 'disabled'}`);
    } catch (error) {
      console.error('Error toggling global auto-reply:', error);
      alert('Failed to toggle global auto-reply');
    }
  };

  const handleToggleAccountAutoReply = async (accountId: number, enabled: boolean, email: string) => {
    try {
      const response = await fetch(`${apiUrl}/api/accounts/${accountId}/auto-reply?enabled=${enabled}`, {
        method: 'PUT',
      });

      if (!response.ok) {
        throw new Error('Failed to toggle account auto-reply');
      }

      // Update local state
      setAccounts(accounts.map(acc => 
        acc.id === accountId ? { ...acc, auto_reply_enabled: enabled } : acc
      ));
      
      alert(`Auto-reply ${enabled ? 'enabled' : 'disabled'} for ${email}`);
    } catch (error) {
      console.error('Error toggling account auto-reply:', error);
      alert('Failed to toggle account auto-reply');
    }
  };

  const handleSaveCustomPrompt = async (accountId: number) => {
    try {
      const response = await fetch(`${apiUrl}/api/accounts/${accountId}/custom-prompt`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ custom_prompt: customPromptValue })
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(errorData.detail || 'Failed to update custom prompt');
      }

      const data = await response.json();
      alert('Custom prompt updated successfully!');
      setEditingPromptAccountId(null);
      setCustomPromptValue('');
      loadAccounts();
    } catch (error) {
      console.error('Error updating custom prompt:', error);
      alert(`Failed to update custom prompt: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  };

  const handleEditCustomPrompt = (account: Account) => {
    setEditingPromptAccountId(account.id);
    setCustomPromptValue(account.custom_prompt || '');
  };

  const handleCancelEditPrompt = () => {
    setEditingPromptAccountId(null);
    setCustomPromptValue('');
  };

  const handleRemoveSentEmails = async () => {
    if (!confirm('This will remove all sent emails (auto-replies) from the vector database. This will improve chat search results. Continue?')) {
      return;
    }

    setCleaningVector(true);
    try {
      const response = await fetch(`${apiUrl}/api/search/remove-sent-emails`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(errorData.detail || 'Failed to remove sent emails');
      }

      const data = await response.json();
      const deletedCount = data.deleted || 0;
      
      if (deletedCount > 0) {
        alert(`Successfully removed ${deletedCount} sent email(s) from vector database. Chat search will now only show incoming emails.`);
      } else {
        alert('No sent emails found in vector database. Everything is clean!');
      }
    } catch (error) {
      console.error('Error removing sent emails:', error);
      alert(`Failed to remove sent emails: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setCleaningVector(false);
    }
  };

  const handleDeleteAllAccounts = async () => {
    const confirmMessage = `⚠️ DANGER: This will PERMANENTLY DELETE:\n\n` +
      `- ALL accounts\n` +
      `- ALL emails in MongoDB\n` +
      `- ALL replies in MongoDB\n` +
      `- ALL vector database data\n\n` +
      `This action CANNOT be undone!\n\n` +
      `Type "DELETE ALL" to confirm:`;
    
    const userInput = prompt(confirmMessage);
    
    if (userInput !== "DELETE ALL") {
      alert("Deletion cancelled. You must type 'DELETE ALL' to confirm.");
      return;
    }

    setDeletingAll(true);
    try {
      const response = await fetch(`${apiUrl}/api/accounts/all`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(errorData.detail || 'Failed to delete all accounts');
      }

      const data = await response.json();
      
      if (data.success) {
        alert(
          `All data deleted successfully!\n\n` +
          `- Accounts: ${data.accounts_deleted}\n` +
          `- Emails: ${data.emails_deleted}\n` +
          `- Replies: ${data.replies_deleted}\n` +
          `- Vector DB: ${data.vector_cleared ? 'Cleared' : 'Not cleared'}\n\n` +
          `You will be logged out and redirected to login page.`
        );
        
        // Clear local storage and redirect to login
        localStorage.clear();
        sessionStorage.clear();
        window.location.href = '/login';
      } else {
        throw new Error(data.message || 'Failed to delete all accounts');
      }
    } catch (error) {
      console.error('Error deleting all accounts:', error);
      alert(`Failed to delete all accounts: ${error instanceof Error ? error.message : 'Unknown error'}`);
      setDeletingAll(false);
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-background p-8 flex items-center justify-center">
        <div className="text-center">
          <RefreshCw className="w-8 h-8 animate-spin mx-auto mb-4" />
          <p className="text-muted-foreground">Loading admin panel...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background p-8">
      <div className="max-w-7xl mx-auto space-y-8">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-4xl font-bold">Admin Portal</h1>
            <p className="text-muted-foreground mt-2">
              Manage email accounts and view system statistics
            </p>
          </div>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <Bot className="w-4 h-4" />
              <span className="text-sm font-medium">Global Auto-Reply:</span>
              <Switch 
                checked={globalAutoReply} 
                onCheckedChange={handleToggleGlobalAutoReply}
              />
              <span className="text-sm text-muted-foreground">
                {globalAutoReply ? 'ON' : 'OFF'}
              </span>
            </div>
            <Button 
              onClick={handleRemoveSentEmails} 
              variant="outline"
              disabled={cleaningVector}
              className="text-orange-600 hover:text-orange-700 hover:bg-orange-50"
            >
              {cleaningVector ? (
                <>
                  <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                  Cleaning...
                </>
              ) : (
                <>
                  <Search className="w-4 h-4 mr-2" />
                  Clean Vector DB
                </>
              )}
            </Button>
            <Button 
              onClick={handleDeleteAllAccounts} 
              variant="destructive"
              disabled={deletingAll}
              className="text-red-600 hover:text-red-700 hover:bg-red-50 border-red-300"
            >
              {deletingAll ? (
                <>
                  <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                  Deleting All...
                </>
              ) : (
                <>
                  <Trash2 className="w-4 h-4 mr-2" />
                  Delete All Accounts
                </>
              )}
            </Button>
            <Button onClick={loadAccounts} variant="outline">
              <RefreshCw className="w-4 h-4 mr-2" />
              Refresh
            </Button>
          </div>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Total Accounts</CardTitle>
              <Users className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.total}</div>
              <p className="text-xs text-muted-foreground">
                Registered email accounts
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Active Accounts</CardTitle>
              <Activity className="h-4 w-4 text-green-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-green-500">{stats.active}</div>
              <p className="text-xs text-muted-foreground">
                Currently monitoring
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Inactive Accounts</CardTitle>
              <Database className="h-4 w-4 text-orange-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-orange-500">{stats.inactive}</div>
              <p className="text-xs text-muted-foreground">
                Not being monitored
              </p>
            </CardContent>
          </Card>
        </div>

        {/* Accounts Table */}
        <Card>
          <CardHeader>
            <CardTitle>Registered Accounts</CardTitle>
            <CardDescription>
              View and manage all email accounts in the system
            </CardDescription>
          </CardHeader>
          <CardContent>
            {accounts.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                <Mail className="w-12 h-12 mx-auto mb-4 opacity-50" />
                <p>No accounts found</p>
              </div>
            ) : (
              <div className="rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-[100px]">ID</TableHead>
                      <TableHead>Email</TableHead>
                      <TableHead>IMAP Server</TableHead>
                      <TableHead>SMTP Server</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Auto-Reply</TableHead>
                      <TableHead>Custom Prompt</TableHead>
                      <TableHead>Created</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {accounts.map((account) => (
                      <TableRow key={account.id}>
                        <TableCell className="font-medium">
                          {account.id}
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center">
                            <Mail className="w-4 h-4 mr-2 text-muted-foreground" />
                            {account.email}
                          </div>
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {account.imap_server}:{account.imap_port}
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {account.smtp_server}:{account.smtp_port}
                        </TableCell>
                        <TableCell>
                          {account.is_active ? (
                            <Badge variant="default" className="flex items-center gap-1 w-fit">
                              <CheckCircle className="w-3 h-3" />
                              Active
                            </Badge>
                          ) : (
                            <Badge variant="secondary" className="flex items-center gap-1 w-fit">
                              <XCircle className="w-3 h-3" />
                              Inactive
                            </Badge>
                          )}
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <Switch 
                              checked={account.auto_reply_enabled !== false} 
                              onCheckedChange={(checked) => 
                                handleToggleAccountAutoReply(account.id, checked, account.email)
                              }
                            />
                            <span className="text-sm text-muted-foreground">
                              {account.auto_reply_enabled !== false ? 'ON' : 'OFF'}
                            </span>
                          </div>
                        </TableCell>
                        <TableCell>
                          {editingPromptAccountId === account.id ? (
                            <div className="space-y-2">
                              <textarea
                                value={customPromptValue}
                                onChange={(e) => setCustomPromptValue(e.target.value)}
                                placeholder="Enter custom prompt for AI responses..."
                                className="w-full min-h-[80px] p-2 text-sm border rounded-md resize-y"
                                rows={3}
                              />
                              <div className="flex gap-2">
                                <Button
                                  size="sm"
                                  variant="default"
                                  onClick={() => handleSaveCustomPrompt(account.id)}
                                  className="h-7 text-xs"
                                >
                                  Save
                                </Button>
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={handleCancelEditPrompt}
                                  className="h-7 text-xs"
                                >
                                  Cancel
                                </Button>
                              </div>
                            </div>
                          ) : (
                            <div className="space-y-1">
                              {account.custom_prompt ? (
                                <p className="text-xs text-muted-foreground line-clamp-2">
                                  {account.custom_prompt.substring(0, 50)}
                                  {account.custom_prompt.length > 50 ? '...' : ''}
                                </p>
                              ) : (
                                <p className="text-xs text-muted-foreground italic">No custom prompt</p>
                              )}
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => handleEditCustomPrompt(account)}
                                className="h-6 text-xs"
                              >
                                {account.custom_prompt ? 'Edit' : 'Set Prompt'}
                              </Button>
                            </div>
                          )}
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          <div className="flex items-center">
                            <Calendar className="w-3 h-3 mr-1" />
                            {formatDate(account.created_at)}
                          </div>
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex items-center justify-end gap-2">
                            <Button
                              variant={account.is_active ? "default" : "outline"}
                              size="sm"
                              onClick={() => handleActivateAccount(account.id, account.email)}
                              className={account.is_active 
                                ? "bg-green-600 hover:bg-green-700 text-white" 
                                : "text-green-600 hover:text-green-700 hover:bg-green-50"
                              }
                            >
                              <CheckCircle className="w-4 h-4 mr-1" />
                              {account.is_active ? 'Deactivate' : 'Activate'}
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleDeleteAccount(account.id, account.email)}
                              className="text-destructive hover:text-destructive"
                            >
                              <Trash2 className="w-4 h-4" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

