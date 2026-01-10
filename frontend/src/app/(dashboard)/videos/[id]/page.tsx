'use client';

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { 
  Video, 
  Play,
  Download,
  Trash2,
  ArrowLeft,
  Clock,
  Loader2,
  RefreshCw,
  Settings2,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { formatDate, formatDuration, formatCredits } from '@/lib/utils';
import { videosApi, jobsApi } from '@/lib/api';
import { toast } from 'sonner';
import { useJobStatus } from '@/hooks/useJobStatus';
import type { Video as VideoType } from '@/lib/types';

export default function VideoDetailPage() {
  const params = useParams();
  const router = useRouter();
  const videoId = params.id as string;
  
  const [video, setVideo] = useState<VideoType | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);

  // Fetch video details
  useEffect(() => {
    const fetchVideo = async () => {
      try {
        setLoading(true);
        setError(null);
        const videoData = await videosApi.get(videoId);
        setVideo(videoData);
        
        // If video is processing, find the associated job
        if (videoData.status === 'processing' || videoData.status === 'queued') {
          const jobs = await jobsApi.list({ limit: 100 });
          const job = jobs.jobs?.find(j => 
            j.type === 'video_generation' && 
            j.input_data?.video_id === videoId
          );
          if (job) {
            setJobId(job.id);
          }
        }
      } catch (err: any) {
        setError(err.message || 'Failed to load video');
        toast.error('Failed to load video');
      } finally {
        setLoading(false);
      }
    };

    if (videoId) {
      fetchVideo();
    }
  }, [videoId]);

  // Poll for job status if video is processing
  const { job, isProcessing: jobProcessing } = useJobStatus({
    jobId: jobId,
    enabled: !!jobId && (video?.status === 'processing' || video?.status === 'queued'),
    pollInterval: 3000,
    onComplete: async () => {
      // Refresh video data when job completes
      try {
        const videoData = await videosApi.get(videoId);
        setVideo(videoData);
        toast.success('Video generation completed!');
      } catch (err) {
        console.error('Failed to refresh video:', err);
      }
    },
  });

  const handleDelete = async () => {
    if (!confirm('Are you sure you want to delete this video? This action cannot be undone.')) {
      return;
    }

    setDeleting(true);
    try {
      await videosApi.delete(videoId);
      toast.success('Video deleted');
      router.push('/videos');
    } catch (err: any) {
      toast.error(err.message || 'Failed to delete video');
    } finally {
      setDeleting(false);
    }
  };

  const handleRegenerate = async () => {
    if (!video) return;

    setRegenerating(true);
    try {
      const response = await videosApi.generate(videoId, {
        quality: 'balanced',
        resolution: video.resolution || '1080p',
      });
      setJobId(response.job_id);
      toast.success('Video regeneration started');
      
      // Refresh video to update status
      const videoData = await videosApi.get(videoId);
      setVideo(videoData);
    } catch (err: any) {
      toast.error(err.message || 'Failed to regenerate video');
    } finally {
      setRegenerating(false);
    }
  };

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center min-h-[60vh]">
        <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error || !video) {
    return (
      <div className="p-8">
        <Card>
          <CardContent className="py-16 text-center">
            <p className="text-destructive mb-4">{error || 'Video not found'}</p>
            <Button onClick={() => router.push('/videos')}>
              <ArrowLeft className="w-4 h-4 mr-2" />
              Back to Videos
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  const isProcessing = video.status === 'processing' || video.status === 'queued';
  const isCompleted = video.status === 'completed';
  const progress = job?.progress || 0;

  return (
    <div className="p-8">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-4">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => router.push('/videos')}
            >
              <ArrowLeft className="w-4 h-4 mr-2" />
              Back
            </Button>
            <div>
              <h1 className="text-3xl font-bold">{video.title}</h1>
              {video.description && (
                <p className="text-muted-foreground mt-1">{video.description}</p>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2">
            {isCompleted && (
              <Button
                variant="outline"
                onClick={handleRegenerate}
                disabled={regenerating}
              >
                {regenerating ? (
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                ) : (
                  <RefreshCw className="w-4 h-4 mr-2" />
                )}
                Regenerate
              </Button>
            )}
            <Button
              variant="destructive"
              onClick={handleDelete}
              disabled={deleting}
            >
              {deleting ? (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <Trash2 className="w-4 h-4 mr-2" />
              )}
              Delete
            </Button>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Main Video Player */}
          <div className="lg:col-span-2 space-y-6">
            <Card>
              <CardContent className="p-0">
                <div className="aspect-video bg-gradient-to-br from-slate-900 to-slate-800 relative overflow-hidden rounded-t-lg">
                  {video.video_url ? (
                    <video
                      src={video.video_url}
                      controls
                      className="w-full h-full"
                      poster={video.thumbnail_url}
                    />
                  ) : video.thumbnail_url ? (
                    <img
                      src={video.thumbnail_url}
                      alt={video.title}
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center">
                      <Video className="w-16 h-16 text-muted-foreground" />
                    </div>
                  )}
                  
                  {/* Processing Overlay */}
                  {isProcessing && (
                    <div className="absolute inset-0 bg-black/60 flex items-center justify-center">
                      <div className="text-center">
                        <Loader2 className="w-12 h-12 animate-spin text-white mx-auto mb-4" />
                        <p className="text-white font-medium mb-2">
                          {job?.current_step || 'Processing video...'}
                        </p>
                        <div className="w-64 h-2 bg-white/20 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-primary transition-all duration-300"
                            style={{ width: `${progress * 100}%` }}
                          />
                        </div>
                        <p className="text-white/80 text-sm mt-2">
                          {Math.round(progress * 100)}% complete
                        </p>
                      </div>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>

            {/* Video Details */}
            <Card>
              <CardHeader>
                <CardTitle>Details</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-sm text-muted-foreground">Status</p>
                    <p className="font-medium capitalize">{video.status}</p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Type</p>
                    <p className="font-medium capitalize">{video.type}</p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Duration</p>
                    <p className="font-medium">
                      {video.duration ? formatDuration(video.duration) : 'N/A'}
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Resolution</p>
                    <p className="font-medium">{video.resolution || 'N/A'}</p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Created</p>
                    <p className="font-medium">{formatDate(video.created_at)}</p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Credits Used</p>
                    <p className="font-medium">{formatCredits(video.credits_used)}</p>
                  </div>
                </div>

                {video.script && (
                  <div>
                    <p className="text-sm text-muted-foreground mb-2">Script</p>
                    <p className="text-sm bg-muted p-3 rounded-lg whitespace-pre-wrap">
                      {video.script}
                    </p>
                  </div>
                )}

                {video.error_message && (
                  <div className="p-4 rounded-lg bg-destructive/10 border border-destructive/20">
                    <p className="text-sm font-medium text-destructive mb-1">Error</p>
                    <p className="text-sm text-destructive/80">{video.error_message}</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            {/* Actions */}
            <Card>
              <CardHeader>
                <CardTitle>Actions</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {video.video_url && (
                  <Button
                    variant="outline"
                    className="w-full justify-start"
                    onClick={() => window.open(video.video_url, '_blank')}
                  >
                    <Play className="w-4 h-4 mr-2" />
                    Play Video
                  </Button>
                )}
                {video.video_url && (
                  <Button
                    variant="outline"
                    className="w-full justify-start"
                    onClick={() => {
                      const link = document.createElement('a');
                      link.href = video.video_url!;
                      link.download = `${video.title}.mp4`;
                      link.click();
                    }}
                  >
                    <Download className="w-4 h-4 mr-2" />
                    Download
                  </Button>
                )}
                {video.audio_url && (
                  <Button
                    variant="outline"
                    className="w-full justify-start"
                    onClick={() => window.open(video.audio_url, '_blank')}
                  >
                    <Download className="w-4 h-4 mr-2" />
                    Download Audio
                  </Button>
                )}
              </CardContent>
            </Card>

            {/* Metadata */}
            {video.video_metadata && Object.keys(video.video_metadata).length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle>Metadata</CardTitle>
                </CardHeader>
                <CardContent>
                  <pre className="text-xs bg-muted p-3 rounded-lg overflow-auto">
                    {JSON.stringify(video.video_metadata, null, 2)}
                  </pre>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      </motion.div>
    </div>
  );
}

