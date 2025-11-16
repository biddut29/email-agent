'use client';

import { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { Plus, Mail, Trash2, Check, ChevronDown, User } from 'lucide-react';

interface Account {
  id: number;
  email: string;
  imap_server: string;
  imap_port: number;
  smtp_server: string;
  smtp_port: number;
  is_active: boolean;
  created_at: string;
}

interface AccountManagerProps {
  onAccountChange?: () => void;
}

export default function AccountManager({ onAccountChange }: AccountManagerProps) {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [activeAccountId, setActiveAccountId] = useState<number | null>(null);
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);
  const [isLoginDialogOpen, setIsLoginDialogOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  
  // Form state
  const [newEmail, setNewEmail] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [imapServer, setImapServer] = useState('imap.gmail.com');
  const [smtpServer, setSmtpServer] = useState('smtp.gmail.com');
  
  // Login form state
  const [loginEmail, setLoginEmail] = useState('');
  const [loginPassword, setLoginPassword] = useState('');

  useEffect(() => {
    loadAccounts();
  }, []);

  const loadAccounts = async () => {
    try {
      const data = await api.getAccounts();
      console.log('Accounts API response:', data);
      
      if (data.success) {
        // Ensure account IDs are numbers (MongoDB might return strings)
        const formattedAccounts = data.accounts.map((acc: any) => ({
          ...acc,
          id: typeof acc.id === 'string' ? parseInt(acc.id, 10) : acc.id
        }));
        
        console.log('Formatted accounts:', formattedAccounts);
        console.log('Active account ID:', data.active_account_id);
        
        setAccounts(formattedAccounts);
        setActiveAccountId(
          data.active_account_id 
            ? (typeof data.active_account_id === 'string' 
                ? parseInt(data.active_account_id, 10) 
                : data.active_account_id)
            : null
        );
      } else {
        console.error('API returned success=false:', data);
      }
    } catch (error: any) {
      console.error('Failed to load accounts:', error);
    }
  };

  const handleAddAccount = async () => {
    if (!newEmail || !newPassword) {
      alert('Please enter email and password');
      return;
    }

    setLoading(true);
    try {
      const data = await api.addAccount(
        newEmail,
        newPassword,
        imapServer,
        993,
        smtpServer,
        587
      );
      
      if (data.success) {
        if (data.account?.updated) {
          alert(`Account ${newEmail} already existed. Password and settings have been updated!`);
        } else {
          alert(`Account ${newEmail} added successfully!`);
        }
        setIsAddDialogOpen(false);
        setNewEmail('');
        setNewPassword('');
        setImapServer('imap.gmail.com');
        setSmtpServer('smtp.gmail.com');
        loadAccounts();
        onAccountChange?.();
      } else {
        alert(`Failed to add account: ${data.error || 'Unknown error'}`);
      }
    } catch (error: any) {
      console.error('Error adding account:', error);
      alert(`Error: ${error.message || 'Network error. Please check if the backend is running.'}`);
    } finally {
      setLoading(false);
    }
  };

  const handleLogin = async () => {
    if (!loginEmail || !loginPassword) {
      alert('Please enter email and password');
      return;
    }

    setLoading(true);
    try {
      const data = await api.addAccount(
        loginEmail,
        loginPassword,
        'imap.gmail.com',
        993,
        'smtp.gmail.com',
        587
      );
      
      if (data.success) {
        if (data.account?.updated) {
          alert(`✅ Logged in successfully! Account ${loginEmail} is now active.`);
        } else {
          alert(`✅ Account ${loginEmail} added and activated!`);
        }
        setIsLoginDialogOpen(false);
        setLoginEmail('');
        setLoginPassword('');
        loadAccounts();
        onAccountChange?.();
      } else {
        alert(`Failed to login: ${data.error || 'Unknown error'}`);
      }
    } catch (error: any) {
      console.error('Error logging in:', error);
      alert(`Error: ${error.message || 'Network error. Please check if the backend is running.'}`);
    } finally {
      setLoading(false);
    }
  };

  const handleSwitchAccount = async (accountId: number) => {
    setLoading(true);
    try {
      const data = await api.activateAccount(accountId);

      if (data.success) {
        setActiveAccountId(accountId);
        onAccountChange?.();
        alert(data.message || 'Account switched successfully');
      } else {
        alert(`Failed to switch account: ${data.error || 'Unknown error'}`);
      }
    } catch (error: any) {
      alert(`Failed to switch account: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteAccount = async (accountId: number, email: string) => {
    if (!confirm(`Are you sure you want to delete ${email}?`)) {
      return;
    }

    setLoading(true);
    try {
      const data = await api.deleteAccount(accountId);

      if (data.success) {
        alert(data.message || 'Account deleted successfully');
        loadAccounts();
        onAccountChange?.();
      } else {
        alert('Failed to delete account');
      }
    } catch (error: any) {
      alert(`Failed to delete account: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  const activeAccount = accounts.find(acc => acc.id === activeAccountId);

  return (
    <div className="flex items-center gap-2">
      {/* Active Account Dropdown */}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="outline" className="min-w-[200px] justify-between">
            <div className="flex items-center gap-2">
              <User className="w-4 h-4" />
              <span className="truncate">
                {activeAccount ? activeAccount.email : 'No account'}
              </span>
            </div>
            <ChevronDown className="w-4 h-4 ml-2" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-[250px]">
          <DropdownMenuLabel>Email Accounts ({accounts.length})</DropdownMenuLabel>
          <DropdownMenuSeparator />
          
          {accounts.map((account) => (
            <DropdownMenuItem
              key={account.id}
              onClick={() => handleSwitchAccount(account.id)}
              className="flex items-center justify-between cursor-pointer"
            >
              <div className="flex items-center gap-2">
                <Mail className="w-4 h-4" />
                <span className="truncate">{account.email}</span>
              </div>
              {account.id === activeAccountId && (
                <Check className="w-4 h-4 text-green-600" />
              )}
            </DropdownMenuItem>
          ))}
          
          {accounts.length === 0 && (
            <div className="px-2 py-4 text-sm text-muted-foreground text-center">
              No accounts added yet
            </div>
          )}
          
          <DropdownMenuSeparator />
          <DropdownMenuItem
            onClick={() => setIsLoginDialogOpen(true)}
            className="cursor-pointer"
          >
            <div className="flex items-center gap-2">
              <User className="w-4 h-4" />
              <span>Login with existing account</span>
            </div>
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      {/* Login Dialog */}
      <Dialog open={isLoginDialogOpen} onOpenChange={setIsLoginDialogOpen}>
        <DialogTrigger asChild>
          <Button variant="default" size="sm">
            Login
          </Button>
        </DialogTrigger>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>Login with Existing Account</DialogTitle>
            <DialogDescription>
              Enter your email and password to login. If the account exists, it will be updated and activated.
            </DialogDescription>
          </DialogHeader>
          
          <div className="grid gap-4 py-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Email Address</label>
              <Input
                type="email"
                placeholder="your-email@gmail.com"
                value={loginEmail}
                onChange={(e) => setLoginEmail(e.target.value)}
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">App Password</label>
              <Input
                type="password"
                placeholder="16-character app password"
                value={loginPassword}
                onChange={(e) => setLoginPassword(e.target.value)}
              />
              <p className="text-xs text-muted-foreground">
                Generate an app password in your Google Account settings
              </p>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setIsLoginDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleLogin} disabled={loading}>
              {loading ? 'Logging in...' : 'Login'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Add Account Dialog */}
      <Dialog open={isAddDialogOpen} onOpenChange={setIsAddDialogOpen}>
        <DialogTrigger asChild>
          <Button variant="outline" size="icon">
            <Plus className="w-4 h-4" />
          </Button>
        </DialogTrigger>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>Add New Email Account</DialogTitle>
            <DialogDescription>
              Add a new Gmail account to manage multiple emails
            </DialogDescription>
          </DialogHeader>
          
          <div className="grid gap-4 py-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Email Address</label>
              <Input
                type="email"
                placeholder="your-email@gmail.com"
                value={newEmail}
                onChange={(e) => setNewEmail(e.target.value)}
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">App Password</label>
              <Input
                type="password"
                placeholder="16-character app password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
              />
              <p className="text-xs text-muted-foreground">
                Generate an app password in your Google Account settings
              </p>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">IMAP Server</label>
                <Input
                  value={imapServer}
                  onChange={(e) => setImapServer(e.target.value)}
                />
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium">SMTP Server</label>
                <Input
                  value={smtpServer}
                  onChange={(e) => setSmtpServer(e.target.value)}
                />
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setIsAddDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleAddAccount} disabled={loading}>
              {loading ? 'Adding...' : 'Add Account'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Accounts List Dialog */}
      <Dialog>
        <DialogTrigger asChild>
          <Button variant="ghost" size="sm">
            Manage
          </Button>
        </DialogTrigger>
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle>Manage Email Accounts</DialogTitle>
            <DialogDescription>
              Switch between accounts or delete them
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-2 max-h-[400px] overflow-y-auto">
            {accounts.map((account) => (
              <Card
                key={account.id}
                className={account.id === activeAccountId ? 'ring-2 ring-primary' : ''}
              >
                <CardContent className="pt-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <Mail className="w-5 h-5" />
                      <div>
                        <p className="font-medium">{account.email}</p>
                        <p className="text-xs text-muted-foreground">
                          {account.imap_server}
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      {account.id === activeAccountId && (
                        <Badge variant="default">Active</Badge>
                      )}
                      {account.id !== activeAccountId && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleSwitchAccount(account.id)}
                          disabled={loading}
                        >
                          Switch
                        </Button>
                      )}
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleDeleteAccount(account.id, account.email)}
                        disabled={loading || accounts.length === 1}
                      >
                        <Trash2 className="w-4 h-4 text-destructive" />
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}

            {accounts.length === 0 && (
              <div className="text-center py-8 text-muted-foreground">
                <Mail className="w-12 h-12 mx-auto mb-4 opacity-50" />
                <p>No accounts added yet</p>
                <p className="text-sm mt-2">Click the + button to add your first account</p>
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

