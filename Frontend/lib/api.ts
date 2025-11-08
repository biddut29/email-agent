/**
 * API Client for Email Agent Backend
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface Email {
  id: string;
  message_id: string;
  subject: string;
  from: string;
  to: string;
  date: string;
  text_body: string;
  html_body: string;
  attachments: any[];
  has_attachments: boolean;
  ai_analysis?: {
    category: string;
    urgency_score: number;
    is_spam: boolean;
    summary: string;
  };
}

export interface EmailStats {
  total_emails: number;
  with_attachments: number;
  categories: Record<string, number>;
  average_urgency: number;
  spam_count: number;
}

class EmailAgentAPI {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    
    // Get session token from localStorage
    const token = localStorage.getItem('session_token');
    
    // Prepare headers
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      ...options.headers,
    };
    
    // Add session token to cookie if available
    if (token) {
      // Set cookie for same-origin requests
      document.cookie = `session_token=${token}; path=/; max-age=604800`;
    }
    
    try {
      const response = await fetch(url, {
        ...options,
        credentials: 'include', // Include cookies
        headers,
      });

      // Handle network errors
      if (!response.ok) {
        let errorMessage = `Request failed: ${response.status} ${response.statusText}`;
        try {
          const error = await response.json();
          errorMessage = error.detail || error.message || errorMessage;
        } catch {
          // If response is not JSON, use status text
          errorMessage = `HTTP ${response.status}: ${response.statusText}`;
        }
        throw new Error(errorMessage);
      }

      return response.json();
    } catch (error: any) {
      // Handle network errors (backend not running, CORS, etc.)
      if (error instanceof TypeError && error.message === 'Failed to fetch') {
        throw new Error(
          `Cannot connect to backend at ${this.baseUrl}. ` +
          `Please ensure the backend server is running on port 8000. ` +
          `Error: ${error.message}`
        );
      }
      
      // Re-throw if it's already an Error we created
      if (error instanceof Error) {
        throw error;
      }
      
      // Handle other errors
      throw new Error(`Request failed: ${error.message || String(error)}`);
    }
  }

  // Health check
  async healthCheck() {
    return this.request<{ status: string; email: string; ai_enabled: boolean }>('/api/health');
  }

  // Get emails with optional date range
  async getEmails(
    limit: number = 10, 
    unreadOnly: boolean = false, 
    folder: string = 'INBOX',
    dateFrom?: string,  // YYYY-MM-DD format
    dateTo?: string     // YYYY-MM-DD format
  ) {
    const params = new URLSearchParams({
      limit: limit.toString(),
      unread_only: unreadOnly.toString(),
      folder,
    });
    if (dateFrom) params.append('date_from', dateFrom);
    if (dateTo) params.append('date_to', dateTo);
    
    return this.request<{ success: boolean; count: number; emails: Email[]; date_range?: { from?: string; to?: string } }>(
      `/api/emails?${params}`
    );
  }

  // Get unread emails
  async getUnreadEmails(limit: number = 10) {
    const params = new URLSearchParams({ limit: limit.toString() });
    return this.request<{ success: boolean; count: number; emails: Email[] }>(
      `/api/emails/unread?${params}`
    );
  }

  // Get single email
  async getEmail(emailId: string) {
    return this.request<{ success: boolean; email: Email }>(`/api/emails/${emailId}`);
  }

  // Send email
  async sendEmail(data: {
    to: string | string[];
    subject: string;
    body: string;
    cc?: string[];
    bcc?: string[];
    html?: boolean;
  }) {
    return this.request<{ success: boolean; message: string }>('/api/emails/send', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  // Reply to email
  async replyToEmail(emailId: string, body: string, tone: string = 'professional') {
    return this.request<{ success: boolean; message: string }>('/api/emails/reply', {
      method: 'POST',
      body: JSON.stringify({ email_id: emailId, body, tone }),
    });
  }

  // Analyze email with AI
  async analyzeEmail(data: {
    email_id?: string;
    subject?: string;
    body?: string;
    from_email?: string;
  }) {
    return this.request<{
      success: boolean;
      analysis: {
        category: string;
        urgency: { score: number; reason: string };
        spam: { is_spam: boolean; confidence: number };
        summary: string;
        action_items: string[];
      };
    }>('/api/emails/analyze', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  // Generate AI response
  async generateResponse(emailId: string, tone: string = 'professional') {
    const params = new URLSearchParams({ email_id: emailId, tone });
    return this.request<{
      success: boolean;
      response: string;
      original_email: { subject: string; from: string };
    }>(`/api/emails/generate-response?${params}`, {
      method: 'POST',
    });
  }

  // Search emails
  async searchEmails(data: {
    query?: string;
    sender?: string;
    subject?: string;
    limit?: number;
  }) {
    return this.request<{ success: boolean; count: number; emails: Email[] }>(
      '/api/emails/search',
      {
        method: 'POST',
        body: JSON.stringify(data),
      }
    );
  }

  // Get statistics
  async getStatistics() {
    return this.request<{ success: boolean; statistics: EmailStats }>('/api/statistics');
  }

  // Mark as read
  async markAsRead(emailId: string) {
    return this.request<{ success: boolean; message: string }>(
      `/api/emails/${emailId}/read`,
      {
        method: 'PUT',
      }
    );
  }

  // List folders
  async listFolders() {
    return this.request<{ success: boolean; folders: string[] }>('/api/folders');
  }

  // Chat endpoints
  async sendChatMessage(message: string, includeContext: boolean = true) {
    return this.request<{
      success: boolean;
      response: string;
      tokens_used?: number;
      error: boolean;
    }>('/api/chat/message', {
      method: 'POST',
      body: JSON.stringify({ message, include_context: includeContext }),
    });
  }

  async updateChatContext(emails: Email[]) {
    return this.request<{ success: boolean; message: string }>('/api/chat/context', {
      method: 'POST',
      body: JSON.stringify({ emails }),
    });
  }

  async resetChat() {
    return this.request<{ success: boolean; message: string }>('/api/chat/reset', {
      method: 'POST',
    });
  }

  async getChatHistory() {
    return this.request<{
      success: boolean;
      history: Array<{ role: string; content: string }>;
    }>('/api/chat/history');
  }

  async getChatSuggestions() {
    return this.request<{ success: boolean; suggestions: string[] }>(
      '/api/chat/suggestions'
    );
  }

  // Vector Search endpoints
  async semanticSearch(query: string, nResults: number = 10) {
    return this.request<{
      success: boolean;
      query: string;
      results: Array<{
        id: string;
        distance: number;
        metadata: Record<string, any>;
        document: string;
      }>;
      count: number;
    }>('/api/search/semantic', {
      method: 'POST',
      body: JSON.stringify({ query, n_results: nResults }),
    });
  }

  async getVectorStats() {
    return this.request<{
      success: boolean;
      total_emails: number;
      collection_name: string;
    }>('/api/search/stats');
  }

  async clearVectorStore() {
    return this.request<{
      success: boolean;
      message: string;
    }>('/api/search/clear', {
      method: 'DELETE',
    });
  }

  // Load emails from MongoDB to Vector Store
  async loadToVector(dateFrom?: string, dateTo?: string, limit: number = 1000) {
    const params = new URLSearchParams({ limit: limit.toString() });
    if (dateFrom) params.append('date_from', dateFrom);
    if (dateTo) params.append('date_to', dateTo);
    
    return this.request<{
      success: boolean;
      message: string;
      mongo_count: number;
      vector_count: number;
      date_range?: { from?: string; to?: string };
    }>(`/api/emails/load-to-vector?${params}`, {
      method: 'POST',
    });
  }

  // Get MongoDB statistics
  async getMongoDBStats() {
    return this.request<{
      account_id: number;
      total_emails: number;
      oldest_email?: string;
      newest_email?: string;
    }>('/api/mongodb/stats');
  }

  // Get emails from MongoDB
  async getMongoDBEmails(
    limit: number = 50,
    skip: number = 0,
    dateFrom?: string,
    dateTo?: string,
    unreadOnly: boolean = false
  ) {
    const params = new URLSearchParams({
      limit: limit.toString(),
      skip: skip.toString(),
      unread_only: unreadOnly.toString(),
    });
    if (dateFrom) params.append('date_from', dateFrom);
    if (dateTo) params.append('date_to', dateTo);
    
    return this.request<{
      success: boolean;
      emails: Email[];
      count: number;
      total: number;
      skip: number;
      limit: number;
      has_more: boolean;
    }>(`/api/mongodb/emails?${params}`);
  }

  // Re-fetch email from IMAP to update body
  async refetchEmailFromIMAP(messageId: string) {
    return this.request<{
      success: boolean;
      message: string;
      email: {
        message_id: string;
        subject: string;
        from: string;
        to: string;
        text_body: string;
        html_body: string;
      };
      text_body_length: number;
      html_body_length: number;
      body_extracted?: boolean;
    }>(`/api/mongodb/email/${encodeURIComponent(messageId)}/refetch`, {
      method: 'POST',
    });
  }

  // Get single email with full body from MongoDB
  async getSingleEmail(messageId: string) {
    return this.request<{
      success: boolean;
      email: Email;
    }>(`/api/mongodb/email/${encodeURIComponent(messageId)}`);
  }

  // Attachment endpoints
  async getEmailAttachments(emailId: string) {
    return this.request<{
      success: boolean;
      email_id: string;
      count: number;
      attachments: Array<{
        filename: string;
        content_type: string;
        size: number;
        data: string;  // base64 encoded
        text_content?: string;
      }>;
    }>(`/api/emails/${emailId}/attachments`);
  }

  async getSpecificAttachment(emailId: string, filename: string) {
    return this.request<{
      success: boolean;
      attachment: {
        filename: string;
        content_type: string;
        size: number;
        data: string;  // base64 encoded
      };
    }>(`/api/emails/${emailId}/attachments/${encodeURIComponent(filename)}`);
  }

  // Account management endpoints
  async getAccounts() {
    return this.request<{
      success: boolean;
      accounts: Array<{
        id: number;
        email: string;
        imap_server: string;
        imap_port: number;
        smtp_server: string;
        smtp_port: number;
        is_active: boolean;
      }>;
      active_account_id: number | null;
    }>('/api/accounts');
  }

  async addAccount(
    email: string,
    password: string,
    imapServer: string,
    imapPort: number,
    smtpServer: string,
    smtpPort: number
  ) {
    return this.request<{ success: boolean; account?: any; error?: string }>(
      '/api/accounts',
      {
        method: 'POST',
        body: JSON.stringify({
          email,
          password,
          imap_server: imapServer,
          imap_port: imapPort,
          smtp_server: smtpServer,
          smtp_port: smtpPort,
        }),
      }
    );
  }

  async deleteAccount(accountId: number) {
    return this.request<{ success: boolean; message: string }>(
      `/api/accounts/${accountId}`,
      {
        method: 'DELETE',
      }
    );
  }

  async activateAccount(accountId: number) {
    return this.request<{ success: boolean; message: string; error?: string }>(
      `/api/accounts/${accountId}/activate`,
      {
        method: 'PUT',
      }
    );
  }

  async updateAccount(accountId: number, updates: Record<string, any>) {
    return this.request<{ success: boolean; message: string }>(
      `/api/accounts/${accountId}`,
      {
        method: 'PUT',
        body: JSON.stringify(updates),
      }
    );
  }

  async getActiveAccount() {
    return this.request<{
      success: boolean;
      account?: {
        id: number;
        email: string;
        imap_server: string;
        imap_port: number;
        smtp_server: string;
        smtp_port: number;
        is_active: boolean;
      };
      message?: string;
    }>('/api/accounts/active');
  }

  // AI Analysis endpoints
  async getAIAnalysisStats() {
    return this.request<{
      success: boolean;
      total_analyzed: number;
      by_category: Record<string, number>;
      spam_count: number;
      urgent_count: number;
    }>('/api/ai-analysis/stats');
  }

  async getEmailAIAnalysis(messageId: string) {
    return this.request<{
      success: boolean;
      analysis: {
        email_message_id: string;
        account_id: number;
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
      } | null;
    }>(`/api/ai-analysis/${encodeURIComponent(messageId)}`);
  }

  async getEmailReply(messageId: string) {
    return this.request<{
      success: boolean;
      reply: {
        email_message_id: string;
        account_id: number;
        to: string;
        subject: string;
        body: string;
        sent_at: string;
        success: boolean;
      } | null;
    }>(`/api/reply/${encodeURIComponent(messageId)}`);
  }

  async getEmailDetails(messageId: string) {
    return this.request<{
      success: boolean;
      analysis: {
        email_message_id: string;
        account_id: number;
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
      } | null;
      reply: {
        email_message_id: string;
        account_id: number;
        to: string;
        subject: string;
        body: string;
        sent_at: string;
        success: boolean;
      } | null;
    }>(`/api/email-details/${encodeURIComponent(messageId)}`);
  }

  async analyzeExistingEmails(limit: number = 100) {
    return this.request<{
      success: boolean;
      processed: number;
      message: string;
    }>(`/api/ai-analysis/process-existing?limit=${limit}`, {
      method: 'POST',
    });
  }

  // Send reply to email
  async sendReply(messageId: string, replyBody: string) {
    return this.request<{
      success: boolean;
      message: string;
      to: string;
      subject: string;
    }>(`/api/emails/reply-from-mongodb?message_id=${encodeURIComponent(messageId)}&reply_body=${encodeURIComponent(replyBody)}`, {
      method: 'POST',
    });
  }

  // Auto-reply endpoints
  async getAutoReplyStatus() {
    return this.request<{
      success: boolean;
      auto_reply_enabled: boolean;
    }>('/api/auto-reply/status');
  }

  async toggleAutoReply(enabled: boolean) {
    return this.request<{
      success: boolean;
      auto_reply_enabled: boolean;
      message: string;
    }>(`/api/auto-reply/toggle?enabled=${enabled}`, {
      method: 'POST',
    });
  }

  // Authentication endpoints
  async login(): Promise<{ success: boolean; auth_url: string }> {
    return this.request<{ success: boolean; auth_url: string }>('/api/auth/login');
  }

  async loginWithPassword(email: string, password: string): Promise<{
    success: boolean;
    session_token: string;
    user: {
      account_id: number;
      email: string;
    };
  }> {
    const result = await this.request<{
      success: boolean;
      session_token: string;
      user: {
        account_id: number;
        email: string;
      };
    }>('/api/auth/login-password', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    
    // Store session token
    if (result.success && result.session_token) {
      localStorage.setItem('session_token', result.session_token);
    }
    
    return result;
  }

  async getCurrentUser(): Promise<{
    success: boolean;
    user: {
      account_id: number;
      email: string;
      name: string;
    };
  }> {
    const token = localStorage.getItem('session_token');
    return this.request<{
      success: boolean;
      user: {
        account_id: number;
        email: string;
        name: string;
      };
    }>('/api/auth/me', {
      credentials: 'include',
      headers: {
        'Cookie': token ? `session_token=${token}` : ''
      }
    });
  }

  async logout(): Promise<{ success: boolean }> {
    const token = localStorage.getItem('session_token');
    const result = await this.request<{ success: boolean }>('/api/auth/logout', {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Cookie': token ? `session_token=${token}` : ''
      }
    });
    localStorage.removeItem('session_token');
    return result;
  }
}

export const api = new EmailAgentAPI();
export default api;

