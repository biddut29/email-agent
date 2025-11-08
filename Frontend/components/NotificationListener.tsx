'use client';

import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { Mail, AlertCircle, Sparkles } from 'lucide-react';
import { api } from '@/lib/api';

interface EmailNotification {
  type: string;
  account_id?: number;  // Add account_id for filtering
  email?: {
    subject: string;
    from: string;
    date: string;
    category: string;
    is_spam: boolean;
    urgency_score: number;
  };
  timestamp: string;
  count?: number;
}

export default function NotificationListener() {
  const [connected, setConnected] = useState(false);
  const [eventSource, setEventSource] = useState<EventSource | null>(null);
  const [activeAccountId, setActiveAccountId] = useState<number | null>(null);

  // Fetch active account ID
  useEffect(() => {
    const fetchActiveAccount = async () => {
      try {
        const response = await api.getCurrentUser();
        if (response && response.success && response.user && response.user.account_id) {
          setActiveAccountId(response.user.account_id);
          console.log('Active account ID set to:', response.user.account_id);
        } else {
          console.log('No active account found or user not authenticated');
          setActiveAccountId(null);
        }
      } catch (error) {
        console.error('Failed to get active account:', error);
        setActiveAccountId(null);
      }
    };
    
    fetchActiveAccount();
    
    // Refresh active account periodically (every 5 seconds)
    const interval = setInterval(fetchActiveAccount, 5000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    // Connect to SSE endpoint
    const es = new EventSource('http://localhost:8000/api/notifications/stream');

    es.onopen = () => {
      console.log('✓ Connected to notification stream');
      setConnected(true);
    };

    es.onerror = (error) => {
      console.error('✗ Notification stream error:', error);
      setConnected(false);
    };

    es.onmessage = (event) => {
      try {
        const notification: EmailNotification = JSON.parse(event.data);

        // Ignore keepalive messages
        if (notification.type === 'keepalive') {
          return;
        }

        // Handle new email notification
        if (notification.type === 'new_email' && notification.email) {
          // Filter notifications by active account
          if (activeAccountId !== null) {
            if (notification.account_id !== activeAccountId) {
              // Ignore notifications from other accounts
              console.log(`Ignoring notification for account ${notification.account_id} (active: ${activeAccountId})`);
              return;
            }
            console.log(`Showing notification for account ${notification.account_id} (matches active account)`);
          } else {
            // If no active account, show all notifications (fallback)
            console.log('No active account set, showing all notifications');
          }
          
          const email = notification.email;
          
          // Show different notifications based on email type
          if (email.is_spam) {
            toast.error('Spam Email Detected', {
              description: `From: ${email.from}\n${email.subject}`,
              icon: <AlertCircle className="w-4 h-4" />,
              duration: 3000,
            });
          } else if (email.urgency_score >= 8) {
            toast.warning('Urgent Email Received!', {
              description: `From: ${email.from}\n${email.subject}`,
              icon: <Sparkles className="w-4 h-4 text-orange-500" />,
              duration: 5000,
            });
          } else {
            toast.success('New Email Received', {
              description: `From: ${email.from}\n${email.subject}`,
              icon: <Mail className="w-4 h-4" />,
              duration: 4000,
            });
          }

          // Play notification sound (optional)
          playNotificationSound();
        }
      } catch (error) {
        console.error('Failed to parse notification:', error);
      }
    };

    setEventSource(es);

    // Cleanup on unmount
    return () => {
      console.log('✓ Disconnecting from notification stream');
      es.close();
    };
  }, [activeAccountId]);  // Re-run when activeAccountId changes

  const playNotificationSound = () => {
    try {
      // Create a simple notification sound using Web Audio API
      const audioContext = new (window.AudioContext || (window as any).webkitAudioContext)();
      const oscillator = audioContext.createOscillator();
      const gainNode = audioContext.createGain();

      oscillator.connect(gainNode);
      gainNode.connect(audioContext.destination);

      oscillator.frequency.value = 800;
      oscillator.type = 'sine';

      gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
      gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.5);

      oscillator.start(audioContext.currentTime);
      oscillator.stop(audioContext.currentTime + 0.5);
    } catch (error) {
      console.log('Could not play notification sound:', error);
    }
  };

  // This component doesn't render anything visible
  return null;
}

