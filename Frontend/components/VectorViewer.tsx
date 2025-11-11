'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Database, Search, Trash2, RefreshCw, Sparkles } from 'lucide-react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

interface VectorStats {
  total_emails: number;
  collection_name: string;
}

interface VectorSearchResult {
  id: string;
  distance: number;
  metadata: {
    subject: string;
    from: string;
    date: string;
    category?: string;
    urgency_score?: string;
    has_attachments?: string;
    is_spam?: string;
  };
  document: string;
}

interface SemanticSearchResponse {
  success: boolean;
  query: string;
  results: VectorSearchResult[];
  count: number;
}

export default function VectorViewer() {
  const [stats, setStats] = useState<VectorStats | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<VectorSearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedResult, setSelectedResult] = useState<VectorSearchResult | null>(null);
  const [browseMode, setBrowseMode] = useState<'search' | 'all'>('search');
  const [currentPage, setCurrentPage] = useState(1);
  const [resultsPerPage] = useState(10);

  const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  // Load stats on mount
  useEffect(() => {
    loadStats();
  }, []);

  const loadStats = async () => {
    try {
      const response = await fetch(`${API_BASE}/api/search/stats`);
      const data = await response.json();
      setStats(data);
    } catch (error) {
      console.error('Failed to load stats:', error);
    }
  };

  const performSearch = async () => {
    if (!searchQuery.trim()) return;
    
    setLoading(true);
    setBrowseMode('search');
    setCurrentPage(1);
    try {
      const response = await fetch(`${API_BASE}/api/search/semantic`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: searchQuery,
          n_results: 50
        })
      });
      const data: SemanticSearchResponse = await response.json();
      setSearchResults(data.results || []);
      setSelectedResult(null);
    } catch (error) {
      console.error('Search failed:', error);
    } finally {
      setLoading(false);
    }
  };

  const browseAll = async () => {
    setLoading(true);
    setBrowseMode('all');
    setCurrentPage(1);
    setSearchQuery('');
    try {
      // Use a generic query to get all emails
      const response = await fetch(`${API_BASE}/api/search/semantic`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: 'email message',
          n_results: stats?.total_emails || 100
        })
      });
      const data: SemanticSearchResponse = await response.json();
      setSearchResults(data.results || []);
      setSelectedResult(null);
    } catch (error) {
      console.error('Browse failed:', error);
    } finally {
      setLoading(false);
    }
  };

  const clearVectorStore = async () => {
    if (!confirm('Are you sure you want to clear all vector data?')) return;
    
    try {
      await fetch(`${API_BASE}/api/search/clear`, { method: 'DELETE' });
      setSearchResults([]);
      setSelectedResult(null);
      loadStats();
    } catch (error) {
      console.error('Failed to clear:', error);
    }
  };

  const getSimilarityColor = (distance: number) => {
    if (distance < 0.3) return 'bg-green-500';
    if (distance < 0.6) return 'bg-yellow-500';
    return 'bg-red-500';
  };

  const getSimilarityLabel = (distance: number) => {
    if (distance < 0.3) return 'Highly Relevant';
    if (distance < 0.6) return 'Moderately Relevant';
    return 'Less Relevant';
  };

  // Pagination calculations
  const totalPages = Math.ceil(searchResults.length / resultsPerPage);
  const startIndex = (currentPage - 1) * resultsPerPage;
  const endIndex = startIndex + resultsPerPage;
  const currentResults = searchResults.slice(startIndex, endIndex);

  const goToPage = (page: number) => {
    setCurrentPage(page);
    setSelectedResult(null);
  };

  return (
    <div className="container mx-auto p-6 space-y-6">
      {/* Header Stats */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Database className="w-5 h-5" />
            Vector Database Viewer
          </CardTitle>
          <CardDescription>
            Explore and search through your email embeddings
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between">
            <div className="space-y-1">
              <p className="text-sm text-muted-foreground">Total Indexed Emails</p>
              <p className="text-3xl font-bold">{stats?.total_emails || 0}</p>
              <p className="text-xs text-muted-foreground">
                Collection: {stats?.collection_name || 'N/A'}
              </p>
              {stats && stats.total_emails > 0 && (
                <div className="mt-2">
                  <Badge variant="outline" className="text-xs">
                    💡 Showing filtered results
                  </Badge>
                </div>
              )}
            </div>
            <div className="flex gap-2">
              <Button onClick={loadStats} variant="outline" size="sm">
                <RefreshCw className="w-4 h-4 mr-2" />
                Refresh
              </Button>
              <Button onClick={clearVectorStore} variant="destructive" size="sm">
                <Trash2 className="w-4 h-4 mr-2" />
                Clear All
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Search Interface */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Sparkles className="w-5 h-5" />
            Semantic Search & Browse
          </CardTitle>
          <CardDescription>
            Search by meaning or browse all indexed emails
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex gap-2">
            <Input
              placeholder="e.g., urgent meeting requests, invoice payments, project updates..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && performSearch()}
            />
            <Button onClick={performSearch} disabled={loading || !searchQuery.trim()}>
              <Search className="w-4 h-4 mr-2" />
              {loading && browseMode === 'search' ? 'Searching...' : 'Search'}
            </Button>
            <Button onClick={browseAll} disabled={loading} variant="outline">
              <Database className="w-4 h-4 mr-2" />
              {loading && browseMode === 'all' ? 'Loading...' : 'Browse All'}
            </Button>
          </div>
          {browseMode === 'all' && searchResults.length > 0 && (
            <div className="text-sm text-muted-foreground">
              Showing all {searchResults.length} indexed emails
            </div>
          )}
        </CardContent>
      </Card>

      {/* Results */}
      {searchResults.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Results List */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>
                    {browseMode === 'all' ? 'All Emails' : 'Search Results'} ({searchResults.length})
                  </CardTitle>
                  <CardDescription>
                    Showing {startIndex + 1}-{Math.min(endIndex, searchResults.length)} of {searchResults.length}
                  </CardDescription>
                </div>
                {totalPages > 1 && (
                  <div className="flex items-center gap-2">
                    <Button
                      onClick={() => goToPage(currentPage - 1)}
                      disabled={currentPage === 1}
                      variant="outline"
                      size="sm"
                    >
                      Previous
                    </Button>
                    <span className="text-sm text-muted-foreground">
                      Page {currentPage} of {totalPages}
                    </span>
                    <Button
                      onClick={() => goToPage(currentPage + 1)}
                      disabled={currentPage === totalPages}
                      variant="outline"
                      size="sm"
                    >
                      Next
                    </Button>
                  </div>
                )}
              </div>
            </CardHeader>
            <CardContent>
              <ScrollArea className="h-[600px] pr-4">
                <div className="space-y-3">
                  {currentResults.map((result, idx) => (
                    <div
                      key={result.id}
                      onClick={() => setSelectedResult(result)}
                      className={`p-4 border rounded-lg cursor-pointer transition-colors hover:bg-accent ${
                        selectedResult?.id === result.id ? 'bg-accent' : ''
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2 mb-2">
                        <div className="flex-1 min-w-0">
                          <p className="font-semibold truncate">
                            {result.metadata.subject || 'No Subject'}
                          </p>
                          <p className="text-xs text-muted-foreground truncate">
                            {result.metadata.from}
                          </p>
                        </div>
                        <Badge variant="outline" className="text-xs">
                          #{startIndex + idx + 1}
                        </Badge>
                      </div>
                      
                      <div className="flex items-center gap-2 flex-wrap">
                        {browseMode === 'search' && (
                          <div className="flex items-center gap-1">
                            <div className={`w-2 h-2 rounded-full ${getSimilarityColor(result.distance)}`} />
                            <span className="text-xs">
                              {getSimilarityLabel(result.distance)}
                            </span>
                          </div>
                        )}
                        
                        {result.metadata.category && (
                          <Badge variant="secondary" className="text-xs">
                            {result.metadata.category}
                          </Badge>
                        )}
                        
                        {result.metadata.has_attachments === 'true' && (
                          <Badge variant="outline" className="text-xs">
                            📎 Attachments
                          </Badge>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </ScrollArea>
              {totalPages > 1 && (
                <div className="mt-4 flex items-center justify-center gap-2">
                  <Button
                    onClick={() => goToPage(1)}
                    disabled={currentPage === 1}
                    variant="outline"
                    size="sm"
                  >
                    First
                  </Button>
                  <Button
                    onClick={() => goToPage(currentPage - 1)}
                    disabled={currentPage === 1}
                    variant="outline"
                    size="sm"
                  >
                    Previous
                  </Button>
                  <span className="text-sm px-4">
                    Page {currentPage} of {totalPages}
                  </span>
                  <Button
                    onClick={() => goToPage(currentPage + 1)}
                    disabled={currentPage === totalPages}
                    variant="outline"
                    size="sm"
                  >
                    Next
                  </Button>
                  <Button
                    onClick={() => goToPage(totalPages)}
                    disabled={currentPage === totalPages}
                    variant="outline"
                    size="sm"
                  >
                    Last
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Detail View */}
          <Card>
            <CardHeader>
              <CardTitle>Details</CardTitle>
              <CardDescription>
                {selectedResult ? 'Vector embedding details' : 'Select a result to view details'}
              </CardDescription>
            </CardHeader>
            <CardContent>
              {selectedResult ? (
                <ScrollArea className="h-[600px] pr-4">
                  <Tabs defaultValue="metadata">
                    <TabsList className="w-full">
                      <TabsTrigger value="metadata" className="flex-1">Metadata</TabsTrigger>
                      <TabsTrigger value="document" className="flex-1">Document</TabsTrigger>
                      <TabsTrigger value="technical" className="flex-1">Technical</TabsTrigger>
                    </TabsList>

                    <TabsContent value="metadata" className="space-y-4">
                      <div>
                        <label className="text-sm font-semibold">Subject</label>
                        <p className="text-sm">{selectedResult.metadata.subject}</p>
                      </div>
                      <div>
                        <label className="text-sm font-semibold">From</label>
                        <p className="text-sm">{selectedResult.metadata.from}</p>
                      </div>
                      <div>
                        <label className="text-sm font-semibold">Date</label>
                        <p className="text-sm">{selectedResult.metadata.date}</p>
                      </div>
                      {selectedResult.metadata.category && (
                        <div>
                          <label className="text-sm font-semibold">Category</label>
                          <p className="text-sm capitalize">{selectedResult.metadata.category}</p>
                        </div>
                      )}
                      {selectedResult.metadata.urgency_score && (
                        <div>
                          <label className="text-sm font-semibold">Urgency Score</label>
                          <p className="text-sm">{selectedResult.metadata.urgency_score}/10</p>
                        </div>
                      )}
                    </TabsContent>

                    <TabsContent value="document">
                      <div className="space-y-2">
                        <label className="text-sm font-semibold">Indexed Document Text</label>
                        <div className="bg-muted p-4 rounded-md text-sm whitespace-pre-wrap">
                          {selectedResult.document}
                        </div>
                      </div>
                    </TabsContent>

                    <TabsContent value="technical" className="space-y-4">
                      <div>
                        <label className="text-sm font-semibold">Vector ID</label>
                        <p className="text-xs font-mono bg-muted p-2 rounded break-all">
                          {selectedResult.id}
                        </p>
                      </div>
                      {browseMode === 'search' && (
                        <>
                          <div>
                            <label className="text-sm font-semibold">Distance Score</label>
                            <p className="text-sm">{selectedResult.distance.toFixed(4)}</p>
                            <p className="text-xs text-muted-foreground">
                              Lower is better (0 = perfect match)
                            </p>
                          </div>
                          <div>
                            <label className="text-sm font-semibold">Similarity Percentage</label>
                            <p className="text-sm">{((1 - selectedResult.distance) * 100).toFixed(2)}%</p>
                          </div>
                        </>
                      )}
                      <div>
                        <label className="text-sm font-semibold">Storage Info</label>
                        <p className="text-xs text-muted-foreground">
                          This email is indexed as a vector embedding in ChromaDB
                        </p>
                      </div>
                    </TabsContent>
                  </Tabs>
                </ScrollArea>
              ) : (
                <div className="h-[600px] flex items-center justify-center text-muted-foreground">
                  <div className="text-center">
                    <Database className="w-12 h-12 mx-auto mb-2 opacity-50" />
                    <p>Select a search result to view details</p>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* Empty State */}
      {searchResults.length === 0 && searchQuery && !loading && (
        <Card>
          <CardContent className="py-12">
            <div className="text-center text-muted-foreground">
              <Search className="w-12 h-12 mx-auto mb-2 opacity-50" />
              <p>No results found for "{searchQuery}"</p>
              <p className="text-sm">Try a different search query</p>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

