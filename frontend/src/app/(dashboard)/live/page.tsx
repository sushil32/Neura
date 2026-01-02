'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import { Radio, Users, Mic, Settings2, Play, Square, MessageSquare } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { liveApi } from '@/lib/api';

export default function LivePage() {
  const [isLive, setIsLive] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [message, setMessage] = useState('');

  const handleStartSession = async () => {
    try {
      const response = await liveApi.startSession();
      setSessionId(response.session_id);
      setIsLive(true);
      toast.success('Live session started!');
    } catch (error) {
      toast.error('Failed to start session');
    }
  };

  const handleStopSession = async () => {
    if (!sessionId) return;
    
    try {
      await liveApi.stopSession(sessionId);
      setIsLive(false);
      setSessionId(null);
      toast.success('Session ended');
    } catch (error) {
      toast.error('Failed to stop session');
    }
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
              Stream real-time AI avatar presentations
            </p>
          </div>
          {!isLive ? (
            <Button onClick={handleStartSession}>
              <Radio className="w-4 h-4 mr-2" />
              Go Live
            </Button>
          ) : (
            <Button variant="destructive" onClick={handleStopSession}>
              <Square className="w-4 h-4 mr-2" />
              End Session
            </Button>
          )}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Main Stream */}
          <div className="lg:col-span-2">
            <Card>
              <CardContent className="p-0">
                <div className="aspect-video bg-muted rounded-t-lg flex items-center justify-center relative">
                  {isLive ? (
                    <>
                      <div className="absolute top-4 left-4 flex items-center gap-2 px-3 py-1.5 rounded-full bg-red-500 text-white text-sm">
                        <div className="w-2 h-2 rounded-full bg-white animate-pulse" />
                        LIVE
                      </div>
                      <Users className="w-24 h-24 text-muted-foreground" />
                    </>
                  ) : (
                    <div className="text-center">
                      <Radio className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
                      <p className="text-muted-foreground">Click "Go Live" to start streaming</p>
                    </div>
                  )}
                </div>
                
                {/* Controls */}
                <div className="p-4 border-t border-border">
                  <div className="flex items-center gap-4">
                    <Button variant="outline" size="sm" disabled={!isLive}>
                      <Mic className="w-4 h-4" />
                    </Button>
                    <Button variant="outline" size="sm" disabled={!isLive}>
                      <Settings2 className="w-4 h-4" />
                    </Button>
                    <div className="flex-1" />
                    <span className="text-sm text-muted-foreground">
                      {isLive ? '00:00:00' : 'Not live'}
                    </span>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Chat/Input */}
            <Card className="mt-6">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <MessageSquare className="w-5 h-5" />
                  Chat with Avatar
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-48 border border-border rounded-lg mb-4 p-4 overflow-y-auto bg-muted/50">
                  <p className="text-muted-foreground text-center text-sm">
                    {isLive ? 'Start typing to interact with the avatar' : 'Start a live session to chat'}
                  </p>
                </div>
                <div className="flex gap-2">
                  <Input
                    placeholder="Type your message..."
                    value={message}
                    onChange={(e) => setMessage(e.target.value)}
                    disabled={!isLive}
                  />
                  <Button disabled={!isLive || !message}>Send</Button>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Session Info</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <p className="text-sm text-muted-foreground">Status</p>
                  <p className="font-medium">{isLive ? 'Live' : 'Offline'}</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Credits/min</p>
                  <p className="font-medium">5 credits</p>
                </div>
                {sessionId && (
                  <div>
                    <p className="text-sm text-muted-foreground">Session ID</p>
                    <p className="font-mono text-xs truncate">{sessionId}</p>
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Avatar</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="aspect-square rounded-lg bg-gradient-to-br from-neura-400/20 to-neura-600/20 flex items-center justify-center mb-4">
                  <Users className="w-12 h-12 text-muted-foreground" />
                </div>
                <Button variant="outline" className="w-full">
                  Change Avatar
                </Button>
              </CardContent>
            </Card>
          </div>
        </div>
      </motion.div>
    </div>
  );
}

