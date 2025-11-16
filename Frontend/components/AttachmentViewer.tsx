'use client';

import React, { useState, useEffect } from 'react';
import { X, Download, ZoomIn, ZoomOut, Loader2, AlertCircle, Maximize2 } from 'lucide-react';
import { api } from '@/lib/api';

interface AttachmentViewerProps {
  messageId: string;
  savedFilename: string;
  originalFilename: string;
  contentType: string;
  onClose: () => void;
}

export default function AttachmentViewer({
  messageId,
  savedFilename,
  originalFilename,
  contentType,
  onClose
}: AttachmentViewerProps) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [attachmentData, setAttachmentData] = useState<string | null>(null);
  const [zoom, setZoom] = useState(100);

  useEffect(() => {
    loadAttachment();
  }, [messageId, savedFilename]);

  const loadAttachment = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const result = await api.getAttachment(messageId, savedFilename);
      
      if (result.success && result.data) {
        setAttachmentData(result.data);
      } else {
        setError('Failed to load attachment');
      }
    } catch (err: any) {
      console.error('Failed to load attachment:', err);
      setError(err.message || 'Failed to load attachment');
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = async () => {
    try {
      await api.downloadAttachment(messageId, savedFilename);
    } catch (err: any) {
      console.error('Failed to download:', err);
      alert(`Failed to download ${originalFilename}`);
    }
  };

  const handleZoomIn = () => {
    setZoom(prev => Math.min(prev + 25, 200));
  };

  const handleZoomOut = () => {
    setZoom(prev => Math.max(prev - 25, 50));
  };

  const resetZoom = () => {
    setZoom(100);
  };

  const isImage = contentType.startsWith('image/');
  const isPDF = contentType.includes('pdf');
  const isViewable = isImage || isPDF;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm">
      {/* Header */}
      <div className="absolute top-0 left-0 right-0 bg-white/95 border-b border-gray-200 p-4 flex items-center justify-between z-10">
        <div className="flex items-center gap-3 flex-1 min-w-0">
          <button
            onClick={onClose}
            className="flex-shrink-0 p-2 hover:bg-gray-100 rounded-lg transition-colors"
            aria-label="Close"
          >
            <X className="w-5 h-5" />
          </button>
          
          <div className="flex-1 min-w-0">
            <h3 className="font-medium text-gray-900 truncate" title={originalFilename}>
              {originalFilename}
            </h3>
            <p className="text-sm text-gray-500">
              {contentType}
            </p>
          </div>
        </div>

        {/* Controls */}
        <div className="flex items-center gap-2 flex-shrink-0">
          {isImage && (
            <>
              <button
                onClick={handleZoomOut}
                disabled={zoom <= 50}
                className="p-2 hover:bg-gray-100 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                aria-label="Zoom out"
              >
                <ZoomOut className="w-5 h-5" />
              </button>
              
              <span className="text-sm font-medium text-gray-700 min-w-[60px] text-center">
                {zoom}%
              </span>
              
              <button
                onClick={handleZoomIn}
                disabled={zoom >= 200}
                className="p-2 hover:bg-gray-100 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                aria-label="Zoom in"
              >
                <ZoomIn className="w-5 h-5" />
              </button>
              
              <button
                onClick={resetZoom}
                className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
                aria-label="Reset zoom"
              >
                <Maximize2 className="w-5 h-5" />
              </button>
              
              <div className="w-px h-6 bg-gray-300 mx-1" />
            </>
          )}
          
          <button
            onClick={handleDownload}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            <Download className="w-4 h-4" />
            <span>Download</span>
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="w-full h-full pt-20 pb-4 px-4 overflow-auto">
        {loading && (
          <div className="flex flex-col items-center justify-center h-full">
            <Loader2 className="w-12 h-12 animate-spin text-white mb-4" />
            <p className="text-white">Loading {originalFilename}...</p>
          </div>
        )}

        {error && (
          <div className="flex flex-col items-center justify-center h-full">
            <AlertCircle className="w-12 h-12 text-red-400 mb-4" />
            <p className="text-white text-lg font-medium mb-2">Failed to load attachment</p>
            <p className="text-gray-300">{error}</p>
            <button
              onClick={loadAttachment}
              className="mt-4 px-4 py-2 bg-white/20 text-white rounded-lg hover:bg-white/30 transition-colors"
            >
              Try Again
            </button>
          </div>
        )}

        {!loading && !error && attachmentData && (
          <>
            {isImage && (
              <div className="flex items-center justify-center h-full p-4">
                <img
                  src={`data:${contentType};base64,${attachmentData}`}
                  alt={originalFilename}
                  style={{ 
                    maxWidth: '100%', 
                    maxHeight: '100%',
                    transform: `scale(${zoom / 100})`,
                    transformOrigin: 'center',
                    transition: 'transform 0.2s'
                  }}
                  className="object-contain"
                />
              </div>
            )}

            {isPDF && (
              <div className="flex items-center justify-center h-full">
                <iframe
                  src={`data:${contentType};base64,${attachmentData}`}
                  className="w-full h-full border-0 rounded-lg bg-white"
                  title={originalFilename}
                />
              </div>
            )}

            {!isViewable && (
              <div className="flex flex-col items-center justify-center h-full">
                <AlertCircle className="w-12 h-12 text-yellow-400 mb-4" />
                <p className="text-white text-lg font-medium mb-2">Preview not available</p>
                <p className="text-gray-300 mb-4">This file type cannot be previewed</p>
                <button
                  onClick={handleDownload}
                  className="flex items-center gap-2 px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                >
                  <Download className="w-5 h-5" />
                  <span>Download to view</span>
                </button>
              </div>
            )}
          </>
        )}
      </div>

      {/* Click outside to close */}
      <div 
        className="absolute inset-0 -z-10" 
        onClick={onClose}
        aria-label="Close viewer"
      />
    </div>
  );
}


