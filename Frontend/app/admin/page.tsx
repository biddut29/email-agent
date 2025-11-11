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
  Settings
} from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

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

interface Stats {
  total: number;
  active: number;
  inactive: number;
}

export default function AdminPage() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [activeAccountId, setActiveAccountId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState<Stats>({ total: 0, active: 0, inactive: 0 });
  const [config, setConfig] = useState({
    azure_openai_key: '',
    azure_openai_endpoint: '',
    azure_openai_deployment: 'gpt-4.1-mini',
    azure_openai_api_version: '2024-12-01-preview',
    ai_provider: 'azure',
    mongodb_uri: 'mongodb://localhost:27017/',
    mongodb_db_name: 'email_agent',
    google_client_id: '',
    google_client_secret: '',
    google_redirect_uri: 'http://localhost:8000/api/auth/callback',
    session_secret: '',
    frontend_url: 'http://localhost:3000',
    cors_origins: 'http://localhost:3000,http://127.0.0.1:3000',
    auto_reply_enabled: true
  });
  const [configLoading, setConfigLoading] = useState(false);

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  useEffect(() => {
    loadAccounts();
    loadConfig();
  }, []);

  const loadAccounts = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${apiUrl}/api/accounts`);
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      const data = await response.json();
      console.log('Admin: Accounts loaded:', data);
      
      if (data.success) {
        const formattedAccounts = data.accounts.map((acc: any) => ({
          ...acc,
          id: typeof acc.id === 'string' ? parseInt(acc.id, 10) : acc.id
        }));
        
        setAccounts(formattedAccounts);
        setActiveAccountId(
          data.active_account_id 
            ? (typeof data.active_account_id === 'string' 
                ? parseInt(data.active_account_id, 10) 
                : data.active_account_id)
            : null
        );
        
        // Calculate stats
        const total = formattedAccounts.length;
        const active = formattedAccounts.filter((acc: Account) => acc.is_active).length;
        setStats({
          total,
          active,
          inactive: total - active
        });
      }
    } catch (error: any) {
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

  const loadConfig = async () => {
    try {
      const response = await fetch(`${apiUrl}/api/config`);
      if (response.ok) {
        const data = await response.json();
        if (data.success) {
          setConfig(data.config);
        }
      }
    } catch (error) {
      console.error('Failed to load config:', error);
    }
  };

  const saveConfig = async () => {
    setConfigLoading(true);
    try {
      const response = await fetch(`${apiUrl}/api/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
      });
      
      if (!response.ok) {
        throw new Error('Failed to save configuration');
      }
      
      alert('Configuration saved! Please restart the backend.');
    } catch (error: any) {
      alert(error.message || 'Failed to save configuration');
    } finally {
      setConfigLoading(false);
    }
  };

  const initFromEnv = async () => {
    if (!confirm('This will load current .env values into the database. Continue?')) {
      return;
    }
    
    try {
      const response = await fetch(`${apiUrl}/api/config/init-from-env`, {
        method: 'POST'
      });
      
      if (!response.ok) {
        throw new Error('Failed to initialize from .env');
      }
      
      alert('Configuration loaded from .env!');
      loadConfig();
    } catch (error: any) {
      alert(error.message || 'Failed to initialize from .env');
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
          <Button onClick={loadAccounts} variant="outline">
            <RefreshCw className="w-4 h-4 mr-2" />
            Refresh
          </Button>
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

        {/* Application Configuration */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Settings className="w-5 h-5" />
                <div>
                  <CardTitle>Application Configuration</CardTitle>
                  <CardDescription>
                    Manage settings (stored in database, not .env)
                  </CardDescription>
                </div>
              </div>
              <Button variant="outline" size="sm" onClick={initFromEnv}>
                Load from .env
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            <Tabs defaultValue="azure" className="w-full">
              <TabsList className="grid w-full grid-cols-4">
                <TabsTrigger value="azure">Azure OpenAI</TabsTrigger>
                <TabsTrigger value="mongodb">MongoDB</TabsTrigger>
                <TabsTrigger value="oauth">OAuth</TabsTrigger>
                <TabsTrigger value="other">Other</TabsTrigger>
              </TabsList>
              
              <TabsContent value="azure" className="space-y-4 mt-4">
                <div className="space-y-2">
                  <Label>Azure OpenAI Key</Label>
                  <Input type="password" value={config.azure_openai_key} onChange={(e) => setConfig({...config, azure_openai_key: e.target.value})} />
                </div>
                <div className="space-y-2">
                  <Label>Azure OpenAI Endpoint</Label>
                  <Input value={config.azure_openai_endpoint} onChange={(e) => setConfig({...config, azure_openai_endpoint: e.target.value})} />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Deployment</Label>
                    <Input value={config.azure_openai_deployment} onChange={(e) => setConfig({...config, azure_openai_deployment: e.target.value})} />
                  </div>
                  <div className="space-y-2">
                    <Label>API Version</Label>
                    <Input value={config.azure_openai_api_version} onChange={(e) => setConfig({...config, azure_openai_api_version: e.target.value})} />
                  </div>
                </div>
                <div className="space-y-2">
                  <Label>AI Provider</Label>
                  <Input value={config.ai_provider} onChange={(e) => setConfig({...config, ai_provider: e.target.value})} />
                </div>
              </TabsContent>
              
              <TabsContent value="mongodb" className="space-y-4 mt-4">
                <div className="space-y-2">
                  <Label>MongoDB URI</Label>
                  <Input value={config.mongodb_uri} onChange={(e) => setConfig({...config, mongodb_uri: e.target.value})} />
                </div>
                <div className="space-y-2">
                  <Label>Database Name</Label>
                  <Input value={config.mongodb_db_name} onChange={(e) => setConfig({...config, mongodb_db_name: e.target.value})} />
                </div>
              </TabsContent>
              
              <TabsContent value="oauth" className="space-y-4 mt-4">
                <div className="space-y-2">
                  <Label>Google Client ID</Label>
                  <Input value={config.google_client_id} onChange={(e) => setConfig({...config, google_client_id: e.target.value})} />
                </div>
                <div className="space-y-2">
                  <Label>Google Client Secret</Label>
                  <Input type="password" value={config.google_client_secret} onChange={(e) => setConfig({...config, google_client_secret: e.target.value})} />
                </div>
                <div className="space-y-2">
                  <Label>Redirect URI</Label>
                  <Input value={config.google_redirect_uri} onChange={(e) => setConfig({...config, google_redirect_uri: e.target.value})} />
                </div>
              </TabsContent>
              
              <TabsContent value="other" className="space-y-4 mt-4">
                <div className="space-y-2">
                  <Label>Session Secret</Label>
                  <Input type="password" value={config.session_secret} onChange={(e) => setConfig({...config, session_secret: e.target.value})} />
                </div>
                <div className="space-y-2">
                  <Label>Frontend URL</Label>
                  <Input value={config.frontend_url} onChange={(e) => setConfig({...config, frontend_url: e.target.value})} />
                </div>
                <div className="space-y-2">
                  <Label>CORS Origins (comma-separated)</Label>
                  <Input value={config.cors_origins} onChange={(e) => setConfig({...config, cors_origins: e.target.value})} />
                </div>
                <div className="flex items-center space-x-2">
                  <Switch checked={config.auto_reply_enabled} onCheckedChange={(checked: boolean) => setConfig({...config, auto_reply_enabled: checked})} />
                  <Label>Auto Reply Enabled</Label>
                </div>
              </TabsContent>
            </Tabs>
            
            <div className="flex justify-end gap-2 mt-6">
              <Button variant="outline" onClick={loadConfig} disabled={configLoading}>
                Reset
              </Button>
              <Button onClick={saveConfig} disabled={configLoading}>
                {configLoading ? 'Saving...' : 'Save Configuration'}
              </Button>
            </div>
          </CardContent>
        </Card>

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

