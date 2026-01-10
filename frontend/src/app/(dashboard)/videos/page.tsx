'use client';

import { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import Link from 'next/link';
import { 
  Video, 
  Plus, 
  Search, 
  Filter,
  Play,
  Download,
  Trash2,
  MoreVertical,
  Clock,
  Loader2,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent } from '@/components/ui/card';
import { formatDate, formatDuration } from '@/lib/utils';
import { videosApi, jobsApi } from '@/lib/api';
import { toast } from 'sonner';
import type { Video as VideoType } from '@/lib/types';

export default function VideosPage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [videos, setVideos] = useState<VideoType[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const fetchVideos = useCallback(async () => {
    try {
      setError(null);
      const params: any = {};
      if (statusFilter !== 'all') {
        params.status = statusFilter;
      }
      const response = await videosApi.list(params);
      setVideos(response.videos || []);
    } catch (err: any) {
      setError(err.message || 'Failed to load videos');
      toast.error('Failed to load videos');
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    fetchVideos();
  }, [fetchVideos]);

  // Poll for processing videos
  useEffect(() => {
    const processingVideos = videos.filter(v => 
      v.status === 'processing' || v.status === 'queued'
    );
    
    if (processingVideos.length === 0) return;

    const interval = setInterval(() => {
      fetchVideos();
    }, 5000); // Poll every 5 seconds

    return () => clearInterval(interval);
  }, [videos, fetchVideos]);

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to delete this video?')) return;
    
    try {
      setDeletingId(id);
      await videosApi.delete(id);
      toast.success('Video deleted');
      setVideos(videos.filter(v => v.id !== id));
    } catch (err: any) {
      toast.error('Failed to delete video');
    } finally {
      setDeletingId(null);
    }
  };

  const handleDownload = (video: VideoType) => {
    if (video.video_url) {
      window.open(video.video_url, '_blank');
    } else {
      toast.error('Video not available yet');
    }
  };

  const filteredVideos = videos.filter((video) => {
    const matchesSearch = video.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (video.description?.toLowerCase().includes(searchQuery.toLowerCase()) ?? false);
    return matchesSearch;
  });

  const getStatusBadge = (status: string) => {
    const styles = {
      completed: 'bg-green-500/10 text-green-500',
      processing: 'bg-yellow-500/10 text-yellow-500',
      draft: 'bg-gray-500/10 text-gray-500',
      failed: 'bg-red-500/10 text-red-500',
    };
    return styles[status as keyof typeof styles] || styles.draft;
  };

  return (
    <div className="p-8">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold">Videos</h1>
            <p className="text-muted-foreground mt-1">
              Manage your AI-generated videos
            </p>
          </div>
          <Link href="/studio">
            <Button>
              <Plus className="w-4 h-4 mr-2" />
              Create Video
            </Button>
          </Link>
        </div>

        {/* Filters */}
        <div className="flex flex-col sm:flex-row gap-4 mb-6">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <Input
              placeholder="Search videos..."
              className="pl-10"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
          <div className="flex gap-2">
            {['all', 'completed', 'processing', 'draft'].map((status) => (
              <Button
                key={status}
                variant={statusFilter === status ? 'default' : 'outline'}
                size="sm"
                onClick={() => setStatusFilter(status)}
              >
                {status.charAt(0).toUpperCase() + status.slice(1)}
              </Button>
            ))}
          </div>
        </div>

        {/* Loading State */}
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
          </div>
        ) : error ? (
          <Card>
            <CardContent className="py-16 text-center">
              <p className="text-destructive mb-4">{error}</p>
              <Button onClick={fetchVideos}>Retry</Button>
            </CardContent>
          </Card>
        ) : filteredVideos.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredVideos.map((video, index) => (
              <motion.div
                key={video.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.1 }}
              >
                <Card className="overflow-hidden group">
                  <Link href={`/videos/${video.id}`}>
                    <div className="aspect-video bg-muted relative cursor-pointer">
                      {video.thumbnail_url ? (
                        <img
                          src={video.thumbnail_url}
                          alt={video.title}
                          className="w-full h-full object-cover"
                        />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-neura-400/10 to-neura-600/10">
                          <Video className="w-12 h-12 text-muted-foreground" />
                        </div>
                      )}
                      
                      {/* Overlay */}
                      <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition flex items-center justify-center gap-2">
                        {video.status === 'completed' && video.video_url && (
                          <>
                            <Button 
                              size="sm" 
                              variant="secondary"
                              onClick={(e) => {
                                e.preventDefault();
                                window.open(video.video_url!, '_blank');
                              }}
                            >
                              <Play className="w-4 h-4" />
                            </Button>
                            <Button 
                              size="sm" 
                              variant="secondary"
                              onClick={(e) => {
                                e.preventDefault();
                                handleDownload(video);
                              }}
                            >
                              <Download className="w-4 h-4" />
                            </Button>
                          </>
                        )}
                        {(video.status === 'processing' || video.status === 'queued') && (
                          <Loader2 className="w-8 h-8 animate-spin text-white" />
                        )}
                      </div>

                      {/* Duration badge */}
                      {video.duration && (
                        <div className="absolute bottom-2 right-2 px-2 py-1 rounded bg-black/70 text-white text-xs">
                          {formatDuration(video.duration)}
                        </div>
                      )}
                    </div>
                  </Link>
                  
                  <CardContent className="p-4">
                    <div className="flex items-start justify-between mb-2">
                      <Link href={`/videos/${video.id}`} className="flex-1 min-w-0">
                        <h3 className="font-semibold truncate hover:text-primary transition">{video.title}</h3>
                        {video.description && (
                          <p className="text-sm text-muted-foreground truncate">
                            {video.description}
                          </p>
                        )}
                      </Link>
                      <div className="relative">
                        <Button 
                          variant="ghost" 
                          size="sm" 
                          className="shrink-0"
                          onClick={(e) => {
                            e.stopPropagation();
                            // TODO: Add dropdown menu
                          }}
                        >
                          <MoreVertical className="w-4 h-4" />
                        </Button>
                      </div>
                    </div>
                    
                    <div className="flex items-center justify-between text-xs text-muted-foreground">
                      <span className={`px-2 py-1 rounded-full ${getStatusBadge(video.status)}`}>
                        {video.status}
                      </span>
                      <div className="flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {formatDate(video.created_at)}
                      </div>
                    </div>
                    
                    {/* Delete button */}
                    <div className="mt-2 flex justify-end">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDelete(video.id)}
                        disabled={deletingId === video.id}
                        className="text-destructive hover:text-destructive"
                      >
                        {deletingId === video.id ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <Trash2 className="w-4 h-4" />
                        )}
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            ))}
          </div>
        ) : (
          <Card>
            <CardContent className="py-16 text-center">
              <Video className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
              <h3 className="text-lg font-semibold mb-2">No videos found</h3>
              <p className="text-muted-foreground mb-4">
                {searchQuery || statusFilter !== 'all'
                  ? 'Try adjusting your filters'
                  : "You haven't created any videos yet"}
              </p>
              <Link href="/studio">
                <Button>
                  <Plus className="w-4 h-4 mr-2" />
                  Create Your First Video
                </Button>
              </Link>
            </CardContent>
          </Card>
        )}
      </motion.div>
    </div>
  );
}

