'use client';

import React, { useState, useEffect } from 'react';
import { Download, File, Image, FileText, FileArchive, FileVideo, FileAudio, Loader2, AlertCircle } from 'lucide-react';
import { api } from '@/lib/api';

interface Attachment {
  original_filename: string;
  saved_filename: string;
  content_type: string;
  size: number;
  file_path: string;
}

interface AttachmentListProps {
  messageId: string;
  compact?: boolean;
}

export default function AttachmentList({ messageId, compact = false }: AttachmentListProps) {
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState<string | null>(null);

  useEffect(() => {
    loadAttachments();
  }, [messageId]);

  const loadAttachments = async () => {
    try {
      setLoading(true);
      setError(null);
      const result = await api.listAttachments(messageId);
      
      if (result.success && result.attachments) {
        setAttachments(result.attachments);
      }
    } catch (err: any) {
      console.error('Failed to load attachments:', err);
      setError(err.message || 'Failed to load attachments');
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = async (savedFilename: string, originalFilename: string) => {
    // Validate required parameters
    if (!savedFilename || savedFilename === 'undefined' || !messageId) {
      console.error('Invalid download parameters:', { savedFilename, messageId });
      alert(`Cannot download: Missing file information`);
      return;
    }
    
    try {
      setDownloading(savedFilename);
      await api.downloadAttachment(messageId, savedFilename);
    } catch (err: any) {
      console.error('Failed to download attachment:', err);
      alert(`Failed to download ${originalFilename}: ${err.message || 'Unknown error'}`);
    } finally {
      setDownloading(null);
    }
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
  };

  const getFileIcon = (contentType: string) => {
    if (!contentType) return <File className="w-5 h-5" />;
    
    if (contentType.startsWith('image/')) return <Image className="w-5 h-5" />;
    if (contentType.startsWith('video/')) return <FileVideo className="w-5 h-5" />;
    if (contentType.startsWith('audio/')) return <FileAudio className="w-5 h-5" />;
    if (contentType.includes('pdf')) return <FileText className="w-5 h-5" />;
    if (contentType.includes('zip') || contentType.includes('rar') || contentType.includes('archive')) {
      return <FileArchive className="w-5 h-5" />;
    }
    return <File className="w-5 h-5" />;
  };

  const getFileTypeColor = (contentType: string): string => {
    if (!contentType) return 'text-gray-600 bg-gray-50 border-gray-200';
    
    if (contentType.startsWith('image/')) return 'text-blue-600 bg-blue-50 border-blue-200';
    if (contentType.startsWith('video/')) return 'text-purple-600 bg-purple-50 border-purple-200';
    if (contentType.startsWith('audio/')) return 'text-green-600 bg-green-50 border-green-200';
    if (contentType.includes('pdf')) return 'text-red-600 bg-red-50 border-red-200';
    if (contentType.includes('zip') || contentType.includes('archive')) {
      return 'text-orange-600 bg-orange-50 border-orange-200';
    }
    return 'text-gray-600 bg-gray-50 border-gray-200';
  };

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-gray-500">
        <Loader2 className="w-4 h-4 animate-spin" />
        <span>Loading attachments...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center gap-2 text-sm text-red-600">
        <AlertCircle className="w-4 h-4" />
        <span>{error}</span>
      </div>
    );
  }

  if (attachments.length === 0) {
    return null;
  }

  if (compact) {
    // Compact view - just show count badge
    return (
      <div className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium text-gray-700 bg-gray-100 rounded-md">
        <File className="w-3 h-3" />
        <span>{attachments.length} attachment{attachments.length !== 1 ? 's' : ''}</span>
      </div>
    );
  }

  // Full view - show all attachments
  return (
    <div className="space-y-2">
      <div className="text-sm font-medium text-gray-700 flex items-center gap-2">
        <File className="w-4 h-4" />
        <span>Attachments ({attachments.length})</span>
      </div>
      
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {attachments
          .filter((att) => att.saved_filename && att.saved_filename !== 'undefined')
          .map((att) => (
          <div
            key={att.saved_filename}
            className={`
              flex items-center gap-3 p-3 rounded-lg border transition-all
              hover:shadow-md cursor-pointer
              ${getFileTypeColor(att.content_type)}
            `}
            onClick={() => handleDownload(att.saved_filename, att.original_filename)}
          >
            {/* Icon */}
            <div className="flex-shrink-0">
              {getFileIcon(att.content_type)}
            </div>

            {/* File info */}
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium truncate" title={att.original_filename}>
                {att.original_filename}
              </div>
              <div className="text-xs text-gray-500">
                {formatFileSize(att.size)}
              </div>
            </div>

            {/* Download button */}
            <div className="flex-shrink-0">
              {downloading === att.saved_filename ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Download className="w-4 h-4" />
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

