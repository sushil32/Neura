'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useAuth } from '@/contexts/AuthContext';

interface WebRTCConfig {
  sessionId: string;
  avatarId?: string;
  voiceId?: string;
  onMessage?: (data: any) => void;
  onFrame?: (frameData: string) => void;
  onAudio?: (audioData: string) => void;
  onConnectionChange?: (state: string) => void;
}

interface WebRTCState {
  isConnected: boolean;
  isConnecting: boolean;
  connectionState: string;
  error: string | null;
  stats: {
    frameCount: number;
    messageCount: number;
    latency: number;
  };
}

export function useWebRTC(config: WebRTCConfig) {
  const { token } = useAuth();
  const wsRef = useRef<WebSocket | null>(null);
  const pcRef = useRef<RTCPeerConnection | null>(null);
  const [state, setState] = useState<WebRTCState>({
    isConnected: false,
    isConnecting: false,
    connectionState: 'disconnected',
    error: null,
    stats: {
      frameCount: 0,
      messageCount: 0,
      latency: 0,
    },
  });

  const connect = useCallback(async () => {
    if (state.isConnecting || state.isConnected) return;

    setState(prev => ({ ...prev, isConnecting: true, error: null }));

    try {
      // Connect WebSocket for signaling
      const wsUrl = `${process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000'}/ws/live/${config.sessionId}`;
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('WebSocket connected');
        // Send auth token
        ws.send(JSON.stringify({
          type: 'auth',
          token: token,
        }));
      };

      ws.onmessage = async (event) => {
        const data = JSON.parse(event.data);
        console.log('WS message:', data.type);

        switch (data.type) {
          case 'session_created':
            await setupPeerConnection(data.ice_servers);
            break;

          case 'answer':
            if (pcRef.current) {
              const answer = new RTCSessionDescription({
                type: 'answer',
                sdp: data.sdp,
              });
              await pcRef.current.setRemoteDescription(answer);
            }
            break;

          case 'ice_candidate':
            if (pcRef.current && data.candidate) {
              await pcRef.current.addIceCandidate(
                new RTCIceCandidate(data.candidate)
              );
            }
            break;

          case 'connection_ready':
            setState(prev => ({
              ...prev,
              isConnected: true,
              isConnecting: false,
              connectionState: 'connected',
            }));
            config.onConnectionChange?.('connected');
            break;

          case 'avatar_response':
            config.onMessage?.(data);
            setState(prev => ({
              ...prev,
              stats: {
                ...prev.stats,
                messageCount: prev.stats.messageCount + 1,
              },
            }));
            break;

          case 'frame':
            config.onFrame?.(data.data);
            setState(prev => ({
              ...prev,
              stats: {
                ...prev.stats,
                frameCount: prev.stats.frameCount + 1,
              },
            }));
            break;

          case 'audio':
            config.onAudio?.(data.data);
            break;

          case 'pong':
            // Calculate latency
            if (data.timestamp) {
              const latency = Date.now() - new Date(data.timestamp).getTime();
              setState(prev => ({
                ...prev,
                stats: {
                  ...prev.stats,
                  latency,
                },
              }));
            }
            break;

          case 'error':
            console.error('WebRTC error:', data.error);
            setState(prev => ({ ...prev, error: data.error }));
            break;
        }
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        setState(prev => ({
          ...prev,
          isConnecting: false,
          error: 'WebSocket connection failed',
        }));
      };

      ws.onclose = () => {
        console.log('WebSocket closed');
        disconnect();
      };

    } catch (error) {
      console.error('Connection error:', error);
      setState(prev => ({
        ...prev,
        isConnecting: false,
        error: error instanceof Error ? error.message : 'Connection failed',
      }));
    }
  }, [config.sessionId, token, state.isConnecting, state.isConnected]);

  const setupPeerConnection = async (iceServers: RTCIceServer[]) => {
    try {
      // Create peer connection
      const pc = new RTCPeerConnection({
        iceServers: iceServers || [
          { urls: 'stun:stun.l.google.com:19302' },
        ],
      });
      pcRef.current = pc;

      // Handle ICE candidates
      pc.onicecandidate = (event) => {
        if (event.candidate && wsRef.current?.readyState === WebSocket.OPEN) {
          wsRef.current.send(JSON.stringify({
            type: 'ice_candidate',
            candidate: event.candidate,
          }));
        }
      };

      // Handle connection state changes
      pc.onconnectionstatechange = () => {
        console.log('Connection state:', pc.connectionState);
        setState(prev => ({
          ...prev,
          connectionState: pc.connectionState,
          isConnected: pc.connectionState === 'connected',
        }));
        config.onConnectionChange?.(pc.connectionState);
      };

      // Handle incoming tracks (video/audio from server)
      pc.ontrack = (event) => {
        console.log('Received track:', event.track.kind);
        // Handle incoming media streams
      };

      // Create and send offer
      const offer = await pc.createOffer({
        offerToReceiveVideo: true,
        offerToReceiveAudio: true,
      });
      await pc.setLocalDescription(offer);

      wsRef.current?.send(JSON.stringify({
        type: 'offer',
        sdp: offer.sdp,
        sdp_type: 'offer',
      }));

    } catch (error) {
      console.error('Peer connection setup failed:', error);
      throw error;
    }
  };

  const disconnect = useCallback(() => {
    // Close peer connection
    if (pcRef.current) {
      pcRef.current.close();
      pcRef.current = null;
    }

    // Close WebSocket
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    setState({
      isConnected: false,
      isConnecting: false,
      connectionState: 'disconnected',
      error: null,
      stats: {
        frameCount: 0,
        messageCount: 0,
        latency: 0,
      },
    });
    config.onConnectionChange?.('disconnected');
  }, []);

  const sendMessage = useCallback((text: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'message',
        content: text,
      }));
    }
  }, []);

  const sendAudio = useCallback((audioData: Blob) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      const reader = new FileReader();
      reader.onload = () => {
        const base64 = (reader.result as string).split(',')[1];
        wsRef.current?.send(JSON.stringify({
          type: 'audio',
          audio: base64,
        }));
      };
      reader.readAsDataURL(audioData);
    }
  }, []);

  const updateConfig = useCallback((newConfig: { avatarId?: string; voiceId?: string }) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'config',
        ...newConfig,
      }));
    }
  }, []);

  const ping = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'ping',
        timestamp: new Date().toISOString(),
      }));
    }
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      disconnect();
    };
  }, [disconnect]);

  // Periodic ping for latency measurement
  useEffect(() => {
    if (!state.isConnected) return;

    const interval = setInterval(ping, 5000);
    return () => clearInterval(interval);
  }, [state.isConnected, ping]);

  return {
    ...state,
    connect,
    disconnect,
    sendMessage,
    sendAudio,
    updateConfig,
  };
}

export default useWebRTC;

