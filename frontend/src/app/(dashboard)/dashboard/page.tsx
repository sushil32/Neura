'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import Link from 'next/link';
import { 
  Video, 
  Clock, 
  CreditCard, 
  TrendingUp, 
  Plus,
  Play,
  ArrowRight,
  Loader2,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { useAuth } from '@/lib/auth';
import { formatCredits } from '@/lib/utils';
import { videosApi, userApi } from '@/lib/api';
import { toast } from 'sonner';
import type { Video as VideoType } from '@/lib/types';

export default function DashboardPage() {
  const { user } = useAuth();
  const [videos, setVideos] = useState<VideoType[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        setError(null);
        const [videosResponse] = await Promise.all([
          videosApi.list({ limit: 10 }),
        ]);
        setVideos(videosResponse.videos || []);
      } catch (err: any) {
        setError(err.message || 'Failed to load dashboard data');
        toast.error('Failed to load dashboard data');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  // Calculate stats from real data
  const totalVideos = videos.length;
  const completedVideos = videos.filter(v => v.status === 'completed').length;
  const totalDuration = videos
    .filter(v => v.duration)
    .reduce((sum, v) => sum + (v.duration || 0), 0);
  
  const formatDuration = (seconds: number) => {
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    if (hours > 0) {
      return `${hours}h ${minutes % 60}m`;
    }
    return `${minutes}m`;
  };

  const formatTimeAgo = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffInSeconds = Math.floor((now.getTime() - date.getTime()) / 1000);
    
    if (diffInSeconds < 60) return 'Just now';
    if (diffInSeconds < 3600) return `${Math.floor(diffInSeconds / 60)} minutes ago`;
    if (diffInSeconds < 86400) return `${Math.floor(diffInSeconds / 3600)} hours ago`;
    if (diffInSeconds < 604800) return `${Math.floor(diffInSeconds / 86400)} days ago`;
    return date.toLocaleDateString();
  };

  const stats = [
    {
      label: 'Videos Created',
      value: totalVideos.toString(),
      change: `${completedVideos} completed`,
      icon: Video,
      color: 'text-blue-500',
      bgColor: 'bg-blue-500/10',
    },
    {
      label: 'Total Duration',
      value: totalDuration > 0 ? formatDuration(totalDuration) : '0m',
      change: `${completedVideos} videos`,
      icon: Clock,
      color: 'text-green-500',
      bgColor: 'bg-green-500/10',
    },
    {
      label: 'Credits Available',
      value: formatCredits(user?.credits || 0),
      change: 'Remaining',
      icon: CreditCard,
      color: 'text-neura-500',
      bgColor: 'bg-neura-500/10',
    },
    {
      label: 'Processing',
      value: videos.filter(v => v.status === 'processing' || v.status === 'queued').length.toString(),
      change: 'In progress',
      icon: TrendingUp,
      color: 'text-purple-500',
      bgColor: 'bg-purple-500/10',
    },
  ];

  const recentVideos = videos.slice(0, 5).map(video => ({
    id: video.id,
    title: video.title,
    status: video.status,
    duration: video.duration ? formatDuration(video.duration) : 'N/A',
    created: formatTimeAgo(video.created_at),
  }));

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center min-h-[400px]">
        <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8">
        <Card>
          <CardContent className="p-6 text-center">
            <p className="text-destructive mb-4">{error}</p>
            <Button onClick={() => window.location.reload()}>Retry</Button>
          </CardContent>
        </Card>
      </div>
    );
  }

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
            <h1 className="text-3xl font-bold">
              Welcome back, {user?.name?.split(' ')[0] || 'there'}!
            </h1>
            <p className="text-muted-foreground mt-1">
              Here's what's happening with your videos
            </p>
          </div>
          <Link href="/studio">
            <Button>
              <Plus className="w-4 h-4 mr-2" />
              Create Video
            </Button>
          </Link>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          {stats.map((stat, index) => (
            <motion.div
              key={stat.label}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.1 }}
            >
              <Card>
                <CardContent className="p-6">
                  <div className="flex items-start justify-between">
                    <div>
                      <p className="text-sm text-muted-foreground">{stat.label}</p>
                      <p className="text-3xl font-bold mt-1">{stat.value}</p>
                      <p className="text-xs text-muted-foreground mt-1">{stat.change}</p>
                    </div>
                    <div className={`p-3 rounded-lg ${stat.bgColor}`}>
                      <stat.icon className={`w-5 h-5 ${stat.color}`} />
                    </div>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>

        {/* Quick Actions */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle>Quick Actions</CardTitle>
              <CardDescription>Get started with common tasks</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-4">
                <Link href="/studio">
                  <div className="p-4 rounded-lg border border-border hover:border-primary/50 hover:bg-primary/5 transition cursor-pointer group">
                    <Video className="w-8 h-8 text-primary mb-3" />
                    <h3 className="font-semibold group-hover:text-primary transition">Create Video</h3>
                    <p className="text-sm text-muted-foreground">
                      Generate a new AI video
                    </p>
                  </div>
                </Link>
                <Link href="/live">
                  <div className="p-4 rounded-lg border border-border hover:border-primary/50 hover:bg-primary/5 transition cursor-pointer group">
                    <Play className="w-8 h-8 text-primary mb-3" />
                    <h3 className="font-semibold group-hover:text-primary transition">Go Live</h3>
                    <p className="text-sm text-muted-foreground">
                      Start a live avatar session
                    </p>
                  </div>
                </Link>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Credits</CardTitle>
              <CardDescription>Your usage this month</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="text-center">
                <div className="w-24 h-24 rounded-full bg-neura-500/10 border-4 border-neura-500 flex items-center justify-center mx-auto mb-4">
                  <span className="text-2xl font-bold text-neura-500">
                    {formatCredits(user?.credits || 0)}
                  </span>
                </div>
                <p className="text-sm text-muted-foreground mb-4">
                  Credits remaining
                </p>
                <Link href="/pricing">
                  <Button variant="outline" size="sm" className="w-full">
                    Upgrade Plan
                  </Button>
                </Link>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Recent Videos */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle>Recent Videos</CardTitle>
              <CardDescription>Your latest creations</CardDescription>
            </div>
            <Link href="/videos">
              <Button variant="ghost" size="sm">
                View all
                <ArrowRight className="w-4 h-4 ml-2" />
              </Button>
            </Link>
          </CardHeader>
          <CardContent>
            {recentVideos.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                <Video className="w-12 h-12 mx-auto mb-4 opacity-50" />
                <p>No videos yet</p>
                <Link href="/studio">
                  <Button className="mt-4" size="sm">
                    <Plus className="w-4 h-4 mr-2" />
                    Create your first video
                  </Button>
                </Link>
              </div>
            ) : (
              <div className="space-y-4">
                {recentVideos.map((video) => {
                  const fullVideo = videos.find(v => v.id === video.id);
                  return (
                    <Link key={video.id} href={`/videos/${video.id}`}>
                      <div className="flex items-center justify-between p-4 rounded-lg border border-border hover:bg-accent/50 transition cursor-pointer">
                        <div className="flex items-center gap-4">
                          <div className="w-16 h-10 rounded bg-muted flex items-center justify-center">
                            {fullVideo?.thumbnail_url ? (
                              <img 
                                src={fullVideo.thumbnail_url} 
                                alt={video.title}
                                className="w-full h-full object-cover rounded"
                              />
                            ) : (
                              <Video className="w-5 h-5 text-muted-foreground" />
                            )}
                          </div>
                          <div>
                            <h4 className="font-medium">{video.title}</h4>
                            <p className="text-sm text-muted-foreground">
                              {video.duration} • {video.created}
                            </p>
                          </div>
                        </div>
                        <div className="flex items-center gap-4">
                          <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                            video.status === 'completed' 
                              ? 'bg-green-500/10 text-green-500' 
                              : video.status === 'processing' || video.status === 'queued'
                              ? 'bg-yellow-500/10 text-yellow-500'
                              : video.status === 'failed'
                              ? 'bg-red-500/10 text-red-500'
                              : 'bg-gray-500/10 text-gray-500'
                          }`}>
                            {video.status}
                          </span>
                          {fullVideo?.video_url && (
                            <Button 
                              variant="ghost" 
                              size="sm"
                              onClick={(e) => {
                                e.preventDefault();
                                window.open(fullVideo.video_url!, '_blank');
                              }}
                            >
                              <Play className="w-4 h-4" />
                            </Button>
                          )}
                        </div>
                      </div>
                    </Link>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>
      </motion.div>
    </div>
  );
}

