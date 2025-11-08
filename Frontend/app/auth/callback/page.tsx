'use client';

import { useEffect, Suspense, useState } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';

function AuthCallbackContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const handleCallback = async () => {
      try {
        const token = searchParams.get('token');
        
        if (!token) {
          console.error('No token found in callback URL');
          setError('No authentication token received. Please try logging in again.');
          setTimeout(() => {
            router.push('/login');
          }, 3000);
          return;
        }

        // Store token in localStorage
        localStorage.setItem('session_token', token);
        
        // Set cookie (for backend)
        document.cookie = `session_token=${token}; path=/; max-age=604800; SameSite=Lax`; // 7 days
        
        // Verify token was stored
        const storedToken = localStorage.getItem('session_token');
        if (storedToken !== token) {
          throw new Error('Failed to store authentication token');
        }

        // Small delay to ensure token is stored before redirect
        await new Promise(resolve => setTimeout(resolve, 100));
        
        // Redirect to dashboard
        router.push('/');
      } catch (err) {
        console.error('Callback error:', err);
        setError(err instanceof Error ? err.message : 'An error occurred during login. Please try again.');
        setTimeout(() => {
          router.push('/login');
        }, 3000);
      }
    };

    handleCallback();
  }, [searchParams, router]);

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <h1 className="text-2xl font-bold mb-4 text-red-600">Login Error</h1>
          <p className="text-muted-foreground mb-4">{error}</p>
          <p className="text-sm text-muted-foreground">Redirecting to login page...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-center min-h-screen">
      <div className="text-center">
        <h1 className="text-2xl font-bold mb-4">Completing login...</h1>
        <p className="text-muted-foreground">Please wait while we redirect you.</p>
      </div>
    </div>
  );
}

export default function AuthCallback() {
  return (
    <Suspense fallback={
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <h1 className="text-2xl font-bold mb-4">Loading...</h1>
          <p className="text-muted-foreground">Please wait.</p>
        </div>
      </div>
    }>
      <AuthCallbackContent />
    </Suspense>
  );
}

