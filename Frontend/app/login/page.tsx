'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Mail, Loader2, Lock } from 'lucide-react';
import api from '@/lib/api';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default function LoginPage() {
  const [loading, setLoading] = useState(false);
  const [loginMethod, setLoginMethod] = useState<'sso' | 'password'>('sso');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const router = useRouter();

  useEffect(() => {
    // Check if already logged in
    const token = localStorage.getItem('session_token');
    if (token) {
      // Verify token is valid
      api.getCurrentUser()
        .then(() => {
          router.push('/');
        })
        .catch(() => {
          // Token invalid, clear it
          localStorage.removeItem('session_token');
        });
    }
  }, [router]);

  const handleGoogleLogin = async () => {
    setLoading(true);
    setError('');
    try {
      const response = await fetch(`${API_BASE_URL}/api/auth/login`);
      const data = await response.json();
      
      if (data.success && data.auth_url) {
        // Redirect to Google OAuth
        window.location.href = data.auth_url;
      } else {
        setError('Failed to initiate login');
        setLoading(false);
      }
    } catch (error) {
      console.error('Login error:', error);
      setError('Failed to connect to server');
      setLoading(false);
    }
  };

  const handlePasswordLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    
    if (!email || !password) {
      setError('Please enter both email and password');
      setLoading(false);
      return;
    }
    
    try {
      const result = await api.loginWithPassword(email, password);
      if (result.success) {
        router.push('/');
      } else {
        setError('Login failed. Please check your credentials.');
        setLoading(false);
      }
    } catch (error: any) {
      console.error('Password login error:', error);
      setError(error.message || 'Login failed. Please check your credentials.');
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-900 dark:to-gray-800 p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <div className="mx-auto mb-4 w-16 h-16 bg-primary rounded-full flex items-center justify-center">
            <Mail className="w-8 h-8 text-primary-foreground" />
          </div>
          <CardTitle className="text-2xl">Email Agent</CardTitle>
          <CardDescription>
            Sign in to access your emails
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Login Method Tabs */}
          <div className="flex gap-2 border-b">
            <button
              onClick={() => {
                setLoginMethod('sso');
                setError('');
              }}
              className={`flex-1 py-2 px-4 text-sm font-medium transition-colors ${
                loginMethod === 'sso'
                  ? 'border-b-2 border-primary text-primary'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              Sign in with Google
            </button>
            <button
              onClick={() => {
                setLoginMethod('password');
                setError('');
              }}
              className={`flex-1 py-2 px-4 text-sm font-medium transition-colors ${
                loginMethod === 'password'
                  ? 'border-b-2 border-primary text-primary'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              App Password
            </button>
          </div>

          {/* Error Message */}
          {error && (
            <div className="p-3 text-sm text-destructive bg-destructive/10 rounded-md border border-destructive/20">
              {error}
            </div>
          )}

          {/* SSO Login */}
          {loginMethod === 'sso' && (
            <div className="space-y-4">
              <Button
                onClick={handleGoogleLogin}
                disabled={loading}
                className="w-full"
                size="lg"
              >
                {loading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Connecting...
                  </>
                ) : (
                  <>
                    <svg className="mr-2 h-4 w-4" viewBox="0 0 24 24">
                      <path
                        fill="currentColor"
                        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                      />
                      <path
                        fill="currentColor"
                        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                      />
                      <path
                        fill="currentColor"
                        d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                      />
                      <path
                        fill="currentColor"
                        d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                      />
                    </svg>
                    Sign in with Google
                  </>
                )}
              </Button>
              <p className="text-xs text-muted-foreground text-center">
                Use your Google account for secure OAuth authentication
              </p>
            </div>
          )}

          {/* Password Login */}
          {loginMethod === 'password' && (
            <form onSubmit={handlePasswordLogin} className="space-y-4">
              <div className="space-y-2">
                <label htmlFor="email" className="text-sm font-medium">
                  Email Address
                </label>
                <Input
                  id="email"
                  type="email"
                  placeholder="your.email@gmail.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  disabled={loading}
                  required
                />
              </div>
              <div className="space-y-2">
                <label htmlFor="password" className="text-sm font-medium">
                  App Password
                </label>
                <Input
                  id="password"
                  type="password"
                  placeholder="Enter your app password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  disabled={loading}
                  required
                />
                <p className="text-xs text-muted-foreground">
                  Use a Gmail App Password, not your regular password. 
                  <a 
                    href="https://support.google.com/accounts/answer/185833" 
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="text-primary hover:underline ml-1"
                  >
                    Learn how to create one
                  </a>
                </p>
              </div>
              <Button
                type="submit"
                disabled={loading}
                className="w-full"
                size="lg"
              >
                {loading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Signing in...
                  </>
                ) : (
                  <>
                    <Lock className="mr-2 h-4 w-4" />
                    Sign in with App Password
                  </>
                )}
              </Button>
            </form>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

