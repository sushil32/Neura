'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
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
import { llmApi, videosApi } from '@/lib/api';

export default function StudioPage() {
  const [step, setStep] = useState<'script' | 'avatar' | 'settings' | 'preview'>('script');
  const [isGenerating, setIsGenerating] = useState(false);
  const [script, setScript] = useState('');
  const [topic, setTopic] = useState('');
  const [videoType, setVideoType] = useState('explainer');
  const [duration, setDuration] = useState(60);

  const handleGenerateScript = async () => {
    if (!topic.trim()) {
      toast.error('Please enter a topic');
      return;
    }

    setIsGenerating(true);
    try {
      const result = await llmApi.generateScript({
        topic,
        type: videoType,
        duration,
      });
      setScript(result.script);
      toast.success('Script generated!');
    } catch (error) {
      toast.error('Failed to generate script');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleCreateVideo = async () => {
    if (!script.trim()) {
      toast.error('Please add a script');
      return;
    }

    setIsGenerating(true);
    try {
      const video = await videosApi.create({
        title: topic || 'Untitled Video',
        type: videoType,
        script,
      });
      
      // Start generation
      await videosApi.generate(video.id, {
        quality: 'balanced',
        resolution: '1080p',
      });
      
      toast.success('Video generation started!');
    } catch (error) {
      toast.error('Failed to create video');
    } finally {
      setIsGenerating(false);
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
              className={`flex items-center gap-2 px-4 py-2 rounded-lg transition ${
                step === s.key
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
                    Select Avatar
                  </CardTitle>
                  <CardDescription>
                    Choose an avatar for your video
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-3 gap-4 mb-6">
                    {[1, 2, 3, 4, 5, 6].map((i) => (
                      <div
                        key={i}
                        className="aspect-square rounded-xl bg-muted border-2 border-transparent hover:border-primary cursor-pointer transition overflow-hidden"
                      >
                        <div className="w-full h-full bg-gradient-to-br from-neura-400/20 to-neura-600/20 flex items-center justify-center">
                          <Users className="w-8 h-8 text-muted-foreground" />
                        </div>
                      </div>
                    ))}
                  </div>
                  
                  <div className="flex justify-between">
                    <Button variant="outline" onClick={() => setStep('script')}>
                      Back
                    </Button>
                    <Button onClick={() => setStep('settings')}>
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
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <Label>Resolution</Label>
                      <select className="w-full h-10 px-3 rounded-lg border border-input bg-background">
                        <option value="1080p">1080p (Full HD)</option>
                        <option value="720p">720p (HD)</option>
                        <option value="4k">4K (Ultra HD)</option>
                      </select>
                    </div>
                    <div>
                      <Label>Quality</Label>
                      <select className="w-full h-10 px-3 rounded-lg border border-input bg-background">
                        <option value="balanced">Balanced</option>
                        <option value="fast">Fast</option>
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
                <CardContent>
                  <div className="aspect-video rounded-xl bg-muted mb-6 flex items-center justify-center">
                    <Play className="w-16 h-16 text-muted-foreground" />
                  </div>

                  <div className="flex justify-between">
                    <Button variant="outline" onClick={() => setStep('settings')}>
                      Back
                    </Button>
                    <Button onClick={handleCreateVideo} disabled={isGenerating}>
                      {isGenerating ? (
                        <>
                          <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                          Creating...
                        </>
                      ) : (
                        <>
                          <Video className="w-4 h-4 mr-2" />
                          Generate Video
                        </>
                      )}
                    </Button>
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
      </motion.div>
    </div>
  );
}

