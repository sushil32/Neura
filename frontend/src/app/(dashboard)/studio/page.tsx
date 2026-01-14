'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { useRouter } from 'next/navigation';
import {
  Sparkles,
  Video,
  Mic,
  Users,
  Settings2,
  Play,
  Loader2,
  Wand2,
  FileText,
} from 'lucide-react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { llmApi, videosApi, avatarsApi, ttsApi, jobsApi } from '@/lib/api';
import type { Avatar, Voice, Job } from '@/lib/types';
import { AvatarSettings } from '@/components/AvatarSettings';

export default function StudioPage() {
  const router = useRouter();
  const [step, setStep] = useState<'script' | 'avatar' | 'settings' | 'preview'>('script');
  const [isGenerating, setIsGenerating] = useState(false);
  const [script, setScript] = useState('');
  const [topic, setTopic] = useState('');

  const [audience, setAudience] = useState('');
  const [platform, setPlatform] = useState('YouTube');
  const [videoType, setVideoType] = useState('explainer');
  const [duration, setDuration] = useState(60);
  const [selectedAvatar, setSelectedAvatar] = useState<string | null>(null);
  const [selectedVoice, setSelectedVoice] = useState<string | null>(null);
  const [resolution, setResolution] = useState('1080p');
  const [quality, setQuality] = useState('balanced');
  const [avatars, setAvatars] = useState<Avatar[]>([]);
  const [voices, setVoices] = useState<Voice[]>([]);
  const [loadingAvatars, setLoadingAvatars] = useState(false);
  const [loadingVoices, setLoadingVoices] = useState(false);

  const [currentJob, setCurrentJob] = useState<Job | null>(null);
  const [generatedVideoId, setGeneratedVideoId] = useState<string | null>(null);
  // Preview State
  const [isPreviewGenerating, setIsPreviewGenerating] = useState(false);
  const [previewJob, setPreviewJob] = useState<Job | null>(null);
  const [previewVideoUrl, setPreviewVideoUrl] = useState<string | null>(null);

  // Avatar Settings State
  const [emotion, setEmotion] = useState('neutral');
  const [expressionScale, setExpressionScale] = useState(1.3);
  const [useEnhancer, setUseEnhancer] = useState(true);
  const [preprocess, setPreprocess] = useState('full');

  useEffect(() => {
    const fetchData = async () => {
      setLoadingAvatars(true);
      setLoadingVoices(true);
      try {
        const [avatarsResponse, voicesResponse] = await Promise.all([
          avatarsApi.list({ include_public: true }),
          ttsApi.listVoices(),
        ]);
        setAvatars(avatarsResponse.avatars || []);
        setVoices(voicesResponse.voices || []);

        // Set defaults
        if (avatarsResponse.avatars.length > 0 && !selectedAvatar) {
          const defaultAvatar = avatarsResponse.avatars.find(a => a.is_default) || avatarsResponse.avatars[0];
          setSelectedAvatar(defaultAvatar.id);
        }
        if (voicesResponse.voices.length > 0 && !selectedVoice) {
          const defaultVoice = voicesResponse.voices.find(v => v.is_default) || voicesResponse.voices[0];
          setSelectedVoice(defaultVoice.id);
        }
      } catch (err: any) {
        toast.error('Failed to load avatars/voices');
      } finally {
        setLoadingAvatars(false);
        setLoadingVoices(false);
      }
    };
    fetchData();
  }, []);

  // Poll for job status if video is generating
  useEffect(() => {
    if (!currentJob || currentJob.status === 'completed' || currentJob.status === 'failed') {
      return;
    }

    const interval = setInterval(async () => {
      try {
        const job = await jobsApi.get(currentJob.id);
        setCurrentJob(job);

        if (job.status === 'completed') {
          toast.success('Video generation completed!');
          if (generatedVideoId) {
            router.push(`/videos/${generatedVideoId}`);
          }
        } else if (job.status === 'failed') {
          toast.error('Video generation failed');
        }
      } catch (err) {
        // Ignore polling errors
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [currentJob, generatedVideoId, router]);

  // Poll for PREVIEW job status
  useEffect(() => {
    if (!previewJob || previewJob.status === 'completed' || previewJob.status === 'failed') {
      return;
    }

    const interval = setInterval(async () => {
      try {
        const job = await jobsApi.get(previewJob.id);
        setPreviewJob(job);

        if (job.status === 'completed' && job.result?.video_url) {
          setPreviewVideoUrl(job.result.video_url);
          setIsPreviewGenerating(false);
          toast.success('Preview ready!');
        } else if (job.status === 'failed') {
          toast.error('Preview generation failed');
          setIsPreviewGenerating(false);
        }
      } catch (err) {
        // Ignore polling errors
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [previewJob]);

  const handleGenerateScript = async () => {
    if (!topic.trim()) {
      toast.error('Please enter a topic');
      return;
    }

    setIsGenerating(true);
    setScript(''); // Clear previous script
    try {
      await llmApi.generateScriptStream(
        {
          topic,
          type: videoType,
          duration,
          audience,
          platform,
        },
        (chunk) => {
          setScript((prev) => prev + chunk);
        },
        (error) => {
          console.error('Stream error:', error);
          toast.error('Failed to generate script');
          setIsGenerating(false);
        }
      );
      // Success handled by completion of stream
    } catch (error) {
      toast.error('Failed to start generation');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleCreateVideo = async () => {
    if (!script.trim()) {
      toast.error('Please add a script');
      return;
    }

    if (!selectedAvatar) {
      toast.error('Please select an avatar');
      return;
    }

    setIsGenerating(true);
    try {
      const video = await videosApi.create({
        title: topic || 'Untitled Video',
        type: videoType,
        script,
        avatar_id: selectedAvatar,
      });

      setGeneratedVideoId(video.id);

      // Start generation - fixed: removed video_id from body
      const generateResponse = await videosApi.generate(video.id, {
        quality: quality as 'fast' | 'balanced' | 'high',
        resolution: resolution as '720p' | '1080p' | '4k',
        // Avatar Params
        emotion: emotion as 'neutral' | 'happy' | 'sad' | 'angry' | 'surprised',
        expression_scale: expressionScale,
        enhancer: useEnhancer ? 'gfpgan' : undefined,
        preprocess: preprocess as 'crop' | 'full',
        voice_id: selectedVoice?.id,
        avatar_id: selectedAvatar,
      });

      // Fetch job to track progress
      const job = await jobsApi.get(generateResponse.job_id);
      setCurrentJob(job);

      toast.success('Video generation started!');
    } catch (error: any) {
      toast.error(error.message || 'Failed to create video');
    } finally {
      setIsGenerating(false);
    }
  };


  const handleGeneratePreview = async () => {
    if (!script.trim() || !selectedAvatar) {
      toast.error('Script and Avatar are required');
      return;
    }

    setIsPreviewGenerating(true);
    setPreviewVideoUrl(null);
    try {
      // Create a temporary video/placeholder for preview
      // Note: In a real app we might want a distinct 'preview' type or ephemeral DB object
      const video = await videosApi.create({
        title: `Preview: ${topic || 'Untitled'}`,
        type: videoType,
        script: script, // Backend will truncate it
        avatar_id: selectedAvatar,
      });

      // Start preview generation (preview=true)
      const generateResponse = await videosApi.generate(video.id, {
        quality: 'balanced', // Upgrade to balanced for stability
        resolution: '1080p', // Force 1080p to prevent black video
        preview: true,
        // Pass Avatar Params to Preview
        emotion: emotion as 'neutral' | 'happy' | 'sad' | 'angry' | 'surprised',
        expression_scale: expressionScale,
        enhancer: useEnhancer ? 'gfpgan' : undefined,
        preprocess: preprocess as 'crop' | 'full',
        voice_id: selectedVoice?.id,
        avatar_id: selectedAvatar,
      });

      // Fetch job to track progress
      const job = await jobsApi.get(generateResponse.job_id);
      setPreviewJob(job);
      toast.info('Generating preview...');
    } catch (error: any) {
      toast.error(error.message || 'Failed to start preview');
      setIsPreviewGenerating(false);
    }
  };

  return (
    <div className="p-8">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold">Video Studio</h1>
          <p className="text-muted-foreground mt-1">
            Create AI-powered videos in minutes
          </p>
        </div>

        {/* Progress Steps */}
        <div className="flex items-center gap-4 mb-8">
          {[
            { key: 'script', label: 'Script', icon: FileText },
            { key: 'avatar', label: 'Avatar', icon: Users },
            { key: 'settings', label: 'Settings', icon: Settings2 },
            { key: 'preview', label: 'Preview', icon: Play },
          ].map((s, index) => (
            <button
              key={s.key}
              onClick={() => setStep(s.key as typeof step)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg transition ${step === s.key
                ? 'bg-primary text-primary-foreground'
                : 'bg-card hover:bg-accent'
                }`}
            >
              <s.icon className="w-4 h-4" />
              <span className="hidden sm:inline">{s.label}</span>
              {index < 3 && (
                <div className="w-8 h-px bg-border ml-2 hidden sm:block" />
              )}
            </button>
          ))}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Main Content */}
          <div className="lg:col-span-2 space-y-6">
            {step === 'script' && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <FileText className="w-5 h-5" />
                    Script
                  </CardTitle>
                  <CardDescription>
                    Write or generate your video script
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                  {/* AI Script Generation */}
                  <div className="p-4 rounded-lg bg-neura-500/5 border border-neura-500/20">
                    <div className="flex items-center gap-2 mb-4">
                      <Wand2 className="w-5 h-5 text-neura-500" />
                      <span className="font-medium">AI Script Generator</span>
                    </div>

                    <div className="space-y-4">
                      <div>
                        <Label>Topic</Label>
                        <Input
                          placeholder="e.g., How to use our new product feature"
                          value={topic}
                          onChange={(e) => setTopic(e.target.value)}
                        />
                      </div>

                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <Label>Target Audience</Label>
                          <Input
                            placeholder="e.g. Beginners, Tech Experts"
                            value={audience}
                            onChange={(e) => setAudience(e.target.value)}
                          />
                        </div>
                        <div>
                          <Label>Platform</Label>
                          <select
                            className="w-full h-10 px-3 rounded-lg border border-input bg-background"
                            value={platform}
                            onChange={(e) => setPlatform(e.target.value)}
                          >
                            <option value="YouTube">YouTube</option>
                            <option value="TikTok">TikTok / Shorts</option>
                            <option value="LinkedIn">LinkedIn</option>
                            <option value="Training">Internal Training</option>
                          </select>
                        </div>
                      </div>

                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <Label>Video Type</Label>
                          <select
                            className="w-full h-10 px-3 rounded-lg border border-input bg-background"
                            value={videoType}
                            onChange={(e) => setVideoType(e.target.value)}
                          >
                            <option value="explainer">Explainer</option>
                            <option value="training">Training</option>
                            <option value="marketing">Marketing</option>
                            <option value="presentation">Presentation</option>
                          </select>
                        </div>
                        <div>
                          <Label>Duration (seconds)</Label>
                          <Input
                            type="number"
                            min={15}
                            max={300}
                            value={duration}
                            onChange={(e) => setDuration(Number(e.target.value))}
                          />
                        </div>
                      </div>

                      <Button
                        onClick={handleGenerateScript}
                        disabled={isGenerating}
                        className="w-full"
                      >
                        {isGenerating ? (
                          <>
                            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                            Generating...
                          </>
                        ) : (
                          <>
                            <Sparkles className="w-4 h-4 mr-2" />
                            Generate Script
                          </>
                        )}
                      </Button>
                    </div>
                  </div>

                  {/* Script Editor */}
                  <div>
                    <Label>Script</Label>
                    <textarea
                      className="w-full h-64 p-4 rounded-lg border border-input bg-background resize-none focus:outline-none focus:ring-2 focus:ring-ring"
                      placeholder="Enter your script here or generate one above..."
                      value={script}
                      onChange={(e) => setScript(e.target.value)}
                    />
                    <p className="text-xs text-muted-foreground mt-2">
                      {script.split(/\s+/).filter(Boolean).length} words •
                      ~{Math.ceil(script.split(/\s+/).filter(Boolean).length / 150)} min
                    </p>
                  </div>

                  <div className="flex justify-end">
                    <Button onClick={() => setStep('avatar')}>
                      Continue to Avatar
                    </Button>
                  </div>
                </CardContent>
              </Card>
            )}

            {step === 'avatar' && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Users className="w-5 h-5" />
                    Select Avatar & Voice
                  </CardTitle>
                  <CardDescription>
                    Choose an avatar and voice for your video
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                  <div>
                    <Label>Avatar</Label>
                    {loadingAvatars ? (
                      <div className="flex items-center justify-center py-8">
                        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
                      </div>
                    ) : (
                      <div className="grid grid-cols-3 gap-4 mt-2">
                        {avatars.map((avatar) => (
                          <div
                            key={avatar.id}
                            onClick={() => setSelectedAvatar(avatar.id)}
                            className={`aspect-square rounded-xl bg-muted border-2 cursor-pointer transition overflow-hidden ${selectedAvatar === avatar.id
                              ? 'border-primary'
                              : 'border-transparent hover:border-primary/50'
                              }`}
                          >
                            {avatar.thumbnail_url ? (
                              <img
                                src={avatar.thumbnail_url}
                                alt={avatar.name}
                                className="w-full h-full object-cover"
                              />
                            ) : (
                              <div className="w-full h-full bg-gradient-to-br from-neura-400/20 to-neura-600/20 flex items-center justify-center">
                                <Users className="w-8 h-8 text-muted-foreground" />
                              </div>
                            )}
                            {avatar.is_default && (
                              <span className="absolute top-1 right-1 px-1.5 py-0.5 rounded bg-primary text-primary-foreground text-xs">
                                Default
                              </span>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  <div>
                    <Label>Voice</Label>
                    {loadingVoices ? (
                      <div className="flex items-center justify-center py-4">
                        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
                      </div>
                    ) : (
                      <select
                        value={selectedVoice || ''}
                        onChange={(e) => setSelectedVoice(e.target.value)}
                        className="w-full h-10 px-3 rounded-lg border border-input bg-background mt-2"
                      >
                        <option value="">Select a voice...</option>
                        {voices.map((voice) => (
                          <option key={voice.id} value={voice.id}>
                            {voice.name} ({voice.language}) {voice.is_default ? '- Default' : ''}
                          </option>
                        ))}
                      </select>
                    )}
                  </div>

                  <div className="flex justify-between">
                    <Button variant="outline" onClick={() => setStep('script')}>
                      Back
                    </Button>
                    <Button
                      onClick={() => setStep('settings')}
                      disabled={!selectedAvatar}
                    >
                      Continue to Settings
                    </Button>
                  </div>
                </CardContent>
              </Card>
            )}

            {step === 'settings' && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Settings2 className="w-5 h-5" />
                    Video Settings
                  </CardTitle>
                  <CardDescription>
                    Configure your video output
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                  {/* Avatar Advanced Settings */}
                  <AvatarSettings
                    emotion={emotion}
                    setEmotion={setEmotion}
                    expressionScale={expressionScale}
                    setExpressionScale={setExpressionScale}
                    useEnhancer={useEnhancer}
                    setUseEnhancer={setUseEnhancer}
                    preprocess={preprocess}
                    setPreprocess={setPreprocess}
                  />

                  <div className="w-full h-px bg-border my-2" />

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <Label>Resolution</Label>
                      <select
                        value={resolution}
                        onChange={(e) => setResolution(e.target.value)}
                        className="w-full h-10 px-3 rounded-lg border border-input bg-background"
                      >
                        <option value="720p">720p (HD)</option>
                        <option value="1080p">1080p (Full HD)</option>
                        <option value="4k">4K (Ultra HD)</option>
                      </select>
                    </div>
                    <div>
                      <Label>Quality</Label>
                      <select
                        value={quality}
                        onChange={(e) => setQuality(e.target.value)}
                        className="w-full h-10 px-3 rounded-lg border border-input bg-background"
                      >
                        <option value="fast">Fast</option>
                        <option value="balanced">Balanced</option>
                        <option value="high">High Quality</option>
                      </select>
                    </div>
                  </div>

                  <div>
                    <Label>Background</Label>
                    <div className="grid grid-cols-4 gap-2 mt-2">
                      {['#000000', '#FFFFFF', '#1E40AF', '#059669'].map((color) => (
                        <button
                          key={color}
                          className="w-full aspect-video rounded-lg border-2 border-transparent hover:border-primary transition"
                          style={{ backgroundColor: color }}
                        />
                      ))}
                    </div>
                  </div>

                  <div className="flex justify-between">
                    <Button variant="outline" onClick={() => setStep('avatar')}>
                      Back
                    </Button>
                    <Button onClick={() => setStep('preview')}>
                      Preview
                    </Button>
                  </div>
                </CardContent>
              </Card>
            )}

            {step === 'preview' && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Play className="w-5 h-5" />
                    Preview & Generate
                  </CardTitle>
                  <CardDescription>
                    Review your video and start generation
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">


                  {/* Preview Player or Placeholder */}
                  {previewVideoUrl ? (
                    <div className="rounded-xl overflow-hidden border border-border bg-black">
                      <video
                        src={previewVideoUrl}
                        controls
                        className="w-full aspect-video"
                        autoPlay
                      />
                      <div className="p-2 bg-muted/50 text-xs text-center text-muted-foreground">
                        Preview Mode (Low Resolution • Short Clip)
                      </div>
                    </div>
                  ) : (
                    <div className="aspect-video rounded-xl bg-muted flex flex-col items-center justify-center gap-4 border-2 border-dashed border-muted-foreground/20">
                      {isPreviewGenerating ? (
                        <div className="text-center space-y-2">
                          <Loader2 className="w-8 h-8 animate-spin text-primary mx-auto" />
                          <p className="text-sm font-medium">Render in progress...</p>
                          {previewJob?.current_step && (
                            <p className="text-xs text-muted-foreground">{previewJob.current_step}</p>
                          )}
                        </div>
                      ) : (
                        <div className="text-center space-y-2">
                          <Play className="w-12 h-12 text-muted-foreground/50 mx-auto" />
                          <p className="text-sm text-muted-foreground">Generate a preview to check lip-sync</p>
                        </div>
                      )}
                    </div>
                  )}

                  <div className="flex justify-between items-center pt-4">
                    <Button variant="outline" onClick={() => setStep('settings')}>
                      Back
                    </Button>

                    <div className="flex gap-3">
                      <Button
                        variant="secondary"
                        onClick={handleGeneratePreview}
                        disabled={isPreviewGenerating || isGenerating}
                      >
                        {isPreviewGenerating ? 'Rendering...' : 'Generate Preview'}
                      </Button>

                      <Button
                        onClick={handleCreateVideo}
                        disabled={isGenerating || isPreviewGenerating || !!currentJob}
                        className="min-w-[140px]"
                      >
                        {isGenerating || currentJob ? (
                          <>
                            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                            Creating Only...
                          </>
                        ) : (
                          <>
                            <Video className="w-4 h-4 mr-2" />
                            Generate Video
                          </>
                        )}
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Credits Required</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-center">
                  <p className="text-4xl font-bold text-neura-500">
                    {Math.ceil(script.split(/\s+/).filter(Boolean).length / 20) || 10}
                  </p>
                  <p className="text-sm text-muted-foreground">Estimated credits</p>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Tips</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-sm text-muted-foreground">
                <p>• Keep sentences short and clear</p>
                <p>• Use [PAUSE] for natural breaks</p>
                <p>• Avoid complex technical jargon</p>
                <p>• Review the script before generating</p>
              </CardContent>
            </Card>
          </div>
        </div>
      </motion.div >
    </div >
  );
}

