'use client';

import { useState, useRef, useCallback, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  Radio, Users, Mic, MicOff, Settings2, Play, Square,
  MessageSquare, Volume2, VolumeX, Send, Wifi, WifiOff,
  Video, VideoOff, Maximize2, Clock
} from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Slider } from '@/components/ui/slider';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { liveApi, avatarsApi, ttsApi } from '@/lib/api';
import { useWebRTC } from '@/hooks/useWebRTC';
import { cn } from '@/lib/utils';
import type { Avatar, Voice } from '@/lib/types';
import { Loader2 } from 'lucide-react';

interface ChatMessage {
  id: string;
  role: 'user' | 'avatar';
  content: string;
  timestamp: Date;
}

export default function LivePage() {
  const [isLive, setIsLive] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [message, setMessage] = useState('');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isMuted, setIsMuted] = useState(false);
  const [isSpeakerMuted, setIsSpeakerMuted] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [selectedAvatar, setSelectedAvatar] = useState<string | null>(null);
  const [selectedVoice, setSelectedVoice] = useState<string | null>(null);
  const [sessionTime, setSessionTime] = useState(0);
  const [currentFrame, setCurrentFrame] = useState<string | null>(null);
  const [avatars, setAvatars] = useState<Avatar[]>([]);
  const [voices, setVoices] = useState<Voice[]>([]);
  const [loadingAvatars, setLoadingAvatars] = useState(false);
  const [loadingVoices, setLoadingVoices] = useState(false);

  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

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

  // WebRTC connection
  const webrtc = useWebRTC({
    sessionId: sessionId || '',
    avatarId: selectedAvatar || '',
    voiceId: selectedVoice || '',
    onMessage: (data) => {
      if (data.content) {
        setMessages(prev => [...prev, {
          id: Date.now().toString(),
          role: 'avatar',
          content: data.content,
          timestamp: new Date(),
        }]);
      }

      // Play audio if available
      if (data.audio && !isSpeakerMuted) {
        playAudio(data.audio);
      }
    },
    onFrame: (frameData) => {
      setCurrentFrame(frameData);
      // Draw frame to canvas
      if (canvasRef.current && frameData) {
        const ctx = canvasRef.current.getContext('2d');
        if (ctx) {
          const img = new Image();
          img.onload = () => {
            ctx.drawImage(img, 0, 0, canvasRef.current!.width, canvasRef.current!.height);
          };
          img.src = `data:image/png;base64,${frameData}`;
        }
      }
    },
    onConnectionChange: (state) => {
      if (state === 'connected') {
        toast.success('Avatar connected!');
      } else if (state === 'disconnected') {
        toast.info('Connection closed');
      } else if (state === 'failed') {
        toast.error('Connection failed');
      }
    },
  });

  const handleStartSession = async () => {
    if (!selectedAvatar) {
      toast.error('Please select an avatar');
      return;
    }

    try {
      const response = await liveApi.startSession({
        avatar_id: selectedAvatar,
      });
      setSessionId(response.session_id);
      setIsLive(true);

      // Start session timer
      timerRef.current = setInterval(() => {
        setSessionTime(prev => prev + 1);
      }, 1000);

      toast.success('Live session started!');
      // WebRTC connection is handled by useEffect watching sessionId
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Failed to start session');
    }
  };

  const handleStopSession = async () => {
    if (!sessionId) return;

    try {
      // Stop timer
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }

      // Disconnect WebRTC
      webrtc.disconnect();

      // Stop backend session
      await liveApi.stopSession(sessionId);

      setIsLive(false);
      setSessionId(null);
      setSessionTime(0);
      setMessages([]);
      setCurrentFrame(null);
      toast.success('Session ended');
    } catch (error) {
      toast.error('Failed to stop session');
    }
  };

  // Connect WebRTC when session starts
  useEffect(() => {
    if (sessionId && isLive && !webrtc.isConnected && !webrtc.isConnecting) {
      webrtc.connect();
    }
  }, [sessionId, isLive, webrtc]);

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSendMessage = () => {
    if (!message.trim() || !webrtc.isConnected) return;

    // Add user message
    setMessages(prev => [...prev, {
      id: Date.now().toString(),
      role: 'user',
      content: message,
      timestamp: new Date(),
    }]);

    // Send to WebRTC
    webrtc.sendMessage(message);
    setMessage('');
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const toggleRecording = async () => {
    if (isRecording) {
      // Stop recording
      mediaRecorderRef.current?.stop();
      setIsRecording(false);
    } else {
      try {
        // Start recording
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const mediaRecorder = new MediaRecorder(stream);
        const chunks: Blob[] = [];

        mediaRecorder.ondataavailable = (e) => {
          chunks.push(e.data);
        };

        mediaRecorder.onstop = () => {
          const audioBlob = new Blob(chunks, { type: 'audio/webm' });
          webrtc.sendAudio(audioBlob);
          stream.getTracks().forEach(track => track.stop());
        };

        mediaRecorderRef.current = mediaRecorder;
        mediaRecorder.start();
        setIsRecording(true);
      } catch (error) {
        toast.error('Failed to access microphone');
      }
    }
  };

  const playAudio = (base64Audio: string) => {
    const audio = new Audio(`data:audio/wav;base64,${base64Audio}`);
    audio.play().catch(console.error);
  };

  const formatTime = (seconds: number) => {
    const hrs = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    return `${hrs.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className="p-8">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold">Live Avatar</h1>
            <p className="text-muted-foreground mt-1">
              Real-time AI avatar streaming with {"<"}500ms latency
            </p>
          </div>
          {!isLive ? (
            <Button onClick={handleStartSession} size="lg">
              <Radio className="w-4 h-4 mr-2" />
              Go Live
            </Button>
          ) : (
            <Button variant="destructive" onClick={handleStopSession} size="lg">
              <Square className="w-4 h-4 mr-2" />
              End Session
            </Button>
          )}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Main Stream */}
          <div className="lg:col-span-2 space-y-6">
            <Card className="overflow-hidden">
              <CardContent className="p-0">
                <div className="aspect-video bg-gradient-to-br from-slate-900 to-slate-800 relative">
                  {/* Canvas for avatar frames */}
                  <canvas
                    ref={canvasRef}
                    width={1280}
                    height={720}
                    className="w-full h-full object-contain"
                  />

                  {/* Overlay when not connected */}
                  {!webrtc.isConnected && (
                    <div className="absolute inset-0 flex items-center justify-center bg-slate-900/80">
                      {isLive && webrtc.isConnecting ? (
                        <div className="text-center">
                          <div className="w-12 h-12 border-4 border-neura-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
                          <p className="text-white">Connecting...</p>
                        </div>
                      ) : (
                        <div className="text-center">
                          <Video className="w-16 h-16 text-slate-500 mx-auto mb-4" />
                          <p className="text-slate-400">Click "Go Live" to start streaming</p>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Live indicator */}
                  {isLive && (
                    <div className="absolute top-4 left-4 flex items-center gap-2">
                      <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-red-500 text-white text-sm">
                        <div className="w-2 h-2 rounded-full bg-white animate-pulse" />
                        LIVE
                      </div>
                      <div className="px-3 py-1.5 rounded-full bg-black/50 text-white text-sm backdrop-blur">
                        {formatTime(sessionTime)}
                      </div>
                    </div>
                  )}

                  {/* Connection status */}
                  {isLive && (
                    <div className="absolute top-4 right-4 flex items-center gap-2">
                      <div className={cn(
                        "flex items-center gap-1 px-2 py-1 rounded-full text-xs",
                        webrtc.isConnected
                          ? "bg-green-500/20 text-green-400"
                          : "bg-yellow-500/20 text-yellow-400"
                      )}>
                        {webrtc.isConnected ? <Wifi className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
                        {webrtc.stats.latency}ms
                      </div>
                    </div>
                  )}
                </div>

                {/* Controls */}
                <div className="p-4 border-t border-border bg-slate-50 dark:bg-slate-900">
                  <div className="flex items-center gap-4">
                    <Button
                      variant={isRecording ? "destructive" : "outline"}
                      size="sm"
                      disabled={!isLive || !webrtc.isConnected}
                      onClick={toggleRecording}
                    >
                      {isRecording ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setIsSpeakerMuted(!isSpeakerMuted)}
                    >
                      {isSpeakerMuted ? <VolumeX className="w-4 h-4" /> : <Volume2 className="w-4 h-4" />}
                    </Button>
                    <div className="w-24">
                      <Slider
                        defaultValue={[100]}
                        max={100}
                        step={1}
                        disabled={isSpeakerMuted}
                      />
                    </div>
                    <Button variant="outline" size="sm">
                      <Maximize2 className="w-4 h-4" />
                    </Button>
                    <div className="flex-1" />
                    <div className="text-sm text-muted-foreground flex items-center gap-2">
                      <Clock className="w-4 h-4" />
                      {formatTime(sessionTime)}
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Chat */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <MessageSquare className="w-5 h-5" />
                  Chat with Avatar
                </CardTitle>
                <CardDescription>
                  Type or speak to interact with your AI avatar in real-time
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="h-64 border border-border rounded-lg mb-4 overflow-y-auto bg-muted/30">
                  {messages.length === 0 ? (
                    <div className="h-full flex items-center justify-center">
                      <p className="text-muted-foreground text-sm">
                        {isLive && webrtc.isConnected
                          ? 'Start typing to interact with the avatar'
                          : 'Start a live session to chat'}
                      </p>
                    </div>
                  ) : (
                    <div className="p-4 space-y-4">
                      {messages.map((msg) => (
                        <div
                          key={msg.id}
                          className={cn(
                            "flex",
                            msg.role === 'user' ? 'justify-end' : 'justify-start'
                          )}
                        >
                          <div className={cn(
                            "max-w-[80%] px-4 py-2 rounded-2xl",
                            msg.role === 'user'
                              ? 'bg-neura-500 text-white rounded-br-sm'
                              : 'bg-slate-200 dark:bg-slate-700 rounded-bl-sm'
                          )}>
                            <p className="text-sm">{msg.content}</p>
                            <p className="text-xs opacity-60 mt-1">
                              {msg.timestamp.toLocaleTimeString()}
                            </p>
                          </div>
                        </div>
                      ))}
                      <div ref={messagesEndRef} />
                    </div>
                  )}
                </div>
                <div className="flex gap-2">
                  <Input
                    placeholder="Type your message..."
                    value={message}
                    onChange={(e) => setMessage(e.target.value)}
                    onKeyPress={handleKeyPress}
                    disabled={!isLive || !webrtc.isConnected}
                    className="flex-1"
                  />
                  <Button
                    onClick={handleSendMessage}
                    disabled={!isLive || !webrtc.isConnected || !message.trim()}
                  >
                    <Send className="w-4 h-4" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            {/* Session Info */}
            <Card>
              <CardHeader>
                <CardTitle>Session Info</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">Status</span>
                  <span className={cn(
                    "flex items-center gap-1 text-sm font-medium",
                    webrtc.isConnected ? "text-green-500" : "text-slate-500"
                  )}>
                    <div className={cn(
                      "w-2 h-2 rounded-full",
                      webrtc.isConnected ? "bg-green-500 animate-pulse" : "bg-slate-400"
                    )} />
                    {webrtc.isConnected ? 'Connected' : isLive ? 'Connecting' : 'Offline'}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">Latency</span>
                  <span className="text-sm font-medium">{webrtc.stats.latency}ms</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">Frames</span>
                  <span className="text-sm font-medium">{webrtc.stats.frameCount}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">Messages</span>
                  <span className="text-sm font-medium">{webrtc.stats.messageCount}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">Credits/min</span>
                  <span className="text-sm font-medium">5 credits</span>
                </div>
                {sessionId && (
                  <div className="pt-2 border-t">
                    <p className="text-xs text-muted-foreground">Session ID</p>
                    <p className="font-mono text-xs truncate">{sessionId}</p>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Avatar Selection */}
            <Card>
              <CardHeader>
                <CardTitle>Avatar</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="aspect-square rounded-lg bg-gradient-to-br from-neura-400/20 to-neura-600/20 flex items-center justify-center overflow-hidden">
                  {currentFrame ? (
                    <img
                      src={`data:image/png;base64,${currentFrame}`}
                      alt="Avatar"
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <Users className="w-12 h-12 text-muted-foreground" />
                  )}
                </div>
                {loadingAvatars ? (
                  <div className="flex items-center justify-center py-4">
                    <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />
                  </div>
                ) : (
                  <Select
                    value={selectedAvatar || ''}
                    onValueChange={(v) => {
                      setSelectedAvatar(v);
                      if (webrtc.isConnected) {
                        webrtc.updateConfig({ avatarId: v });
                      }
                    }}
                    disabled={isLive}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select Avatar" />
                    </SelectTrigger>
                    <SelectContent>
                      {avatars.map((avatar) => (
                        <SelectItem key={avatar.id} value={avatar.id}>
                          {avatar.name} {avatar.is_default ? '(Default)' : ''}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              </CardContent>
            </Card>

            {/* Voice Selection */}
            <Card>
              <CardHeader>
                <CardTitle>Voice</CardTitle>
              </CardHeader>
              <CardContent>
                {loadingVoices ? (
                  <div className="flex items-center justify-center py-4">
                    <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />
                  </div>
                ) : (
                  <Select
                    value={selectedVoice || ''}
                    onValueChange={(v) => {
                      setSelectedVoice(v);
                      if (webrtc.isConnected) {
                        webrtc.updateConfig({ voiceId: v });
                      }
                    }}
                    disabled={isLive}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select Voice" />
                    </SelectTrigger>
                    <SelectContent>
                      {voices.map((voice) => (
                        <SelectItem key={voice.id} value={voice.id}>
                          {voice.name} ({voice.language}) {voice.is_default ? '- Default' : ''}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              </CardContent>
            </Card>

            {/* Quick Tips */}
            <Card>
              <CardHeader>
                <CardTitle>Tips</CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="text-sm text-muted-foreground space-y-2">
                  <li>• Speak clearly for best voice recognition</li>
                  <li>• Use a good microphone for better audio</li>
                  <li>• Ensure stable internet for low latency</li>
                  <li>• Type longer messages for detailed responses</li>
                </ul>
              </CardContent>
            </Card>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
