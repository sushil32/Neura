'use client';

import { useState } from 'react';
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
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent } from '@/components/ui/card';
import { formatDate, formatDuration } from '@/lib/utils';

export default function VideosPage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');

  // Mock data - would come from API
  const videos = [
    {
      id: '1',
      title: 'Product Feature Demo',
      description: 'Showcasing our new dashboard features',
      status: 'completed',
      duration: 180,
      thumbnail: null,
      createdAt: '2024-01-15T10:00:00Z',
      views: 245,
    },
    {
      id: '2',
      title: 'Onboarding Tutorial',
      description: 'Getting started guide for new users',
      status: 'processing',
      duration: 300,
      thumbnail: null,
      createdAt: '2024-01-14T15:30:00Z',
      views: 0,
    },
    {
      id: '3',
      title: 'Weekly Update',
      description: 'Company announcements and updates',
      status: 'completed',
      duration: 120,
      thumbnail: null,
      createdAt: '2024-01-13T09:00:00Z',
      views: 523,
    },
    {
      id: '4',
      title: 'Marketing Promo',
      description: 'New year promotional video',
      status: 'draft',
      duration: 60,
      thumbnail: null,
      createdAt: '2024-01-12T14:00:00Z',
      views: 0,
    },
  ];

  const filteredVideos = videos.filter((video) => {
    const matchesSearch = video.title.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus = statusFilter === 'all' || video.status === statusFilter;
    return matchesSearch && matchesStatus;
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

        {/* Videos Grid */}
        {filteredVideos.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredVideos.map((video, index) => (
              <motion.div
                key={video.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.1 }}
              >
                <Card className="overflow-hidden group">
                  <div className="aspect-video bg-muted relative">
                    {video.thumbnail ? (
                      <img
                        src={video.thumbnail}
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
                      {video.status === 'completed' && (
                        <>
                          <Button size="sm" variant="secondary">
                            <Play className="w-4 h-4" />
                          </Button>
                          <Button size="sm" variant="secondary">
                            <Download className="w-4 h-4" />
                          </Button>
                        </>
                      )}
                    </div>

                    {/* Duration badge */}
                    <div className="absolute bottom-2 right-2 px-2 py-1 rounded bg-black/70 text-white text-xs">
                      {formatDuration(video.duration)}
                    </div>
                  </div>
                  
                  <CardContent className="p-4">
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex-1 min-w-0">
                        <h3 className="font-semibold truncate">{video.title}</h3>
                        <p className="text-sm text-muted-foreground truncate">
                          {video.description}
                        </p>
                      </div>
                      <Button variant="ghost" size="sm" className="shrink-0">
                        <MoreVertical className="w-4 h-4" />
                      </Button>
                    </div>
                    
                    <div className="flex items-center justify-between text-xs text-muted-foreground">
                      <span className={`px-2 py-1 rounded-full ${getStatusBadge(video.status)}`}>
                        {video.status}
                      </span>
                      <div className="flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {formatDate(video.createdAt)}
                      </div>
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

