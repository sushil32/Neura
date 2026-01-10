import { useEffect, useRef, useState, useCallback } from 'react';

type WebRTCStatus = 'idle' | 'connecting' | 'connected' | 'disconnected' | 'failed';

interface UseWebRTCProps {
    sessionId: string;
    onStatusChange?: (status: WebRTCStatus) => void;
}

export function useWebRTC({ sessionId, onStatusChange }: UseWebRTCProps) {
    const [status, setStatus] = useState<WebRTCStatus>('idle');
    const [error, setError] = useState<string | null>(null);

    const videoRef = useRef<HTMLVideoElement>(null);
    const pcRef = useRef<RTCPeerConnection | null>(null);
    const wsRef = useRef<WebSocket | null>(null);
    const streamRef = useRef<MediaStream | null>(null);

    const cleanup = useCallback(() => {
        if (streamRef.current) {
            streamRef.current.getTracks().forEach(track => track.stop());
            streamRef.current = null;
        }
        if (pcRef.current) {
            pcRef.current.close();
            pcRef.current = null;
        }
        if (wsRef.current) {
            wsRef.current.close();
            wsRef.current = null;
        }
        setStatus('disconnected');
    }, []);

    const connect = useCallback(async () => {
        try {
            setStatus('connecting');
            setError(null);

            // 1. Get User Media
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
            streamRef.current = stream;

            // 2. Init WebSocket for Signaling
            // Adjust URL based on environment/proxy
            const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
            const wsProtocol = apiUrl.startsWith('https') ? 'wss' : 'ws';
            const wsBase = apiUrl.replace(/^https?/, wsProtocol);
            const wsUrl = `${wsBase}/api/v1/live/ws/${sessionId}`;

            const ws = new WebSocket(wsUrl);
            wsRef.current = ws;

            await new Promise<void>((resolve, reject) => {
                ws.onopen = () => resolve();
                ws.onerror = (err) => reject(err);
            });

            // 3. Init RTCPeerConnection
            const pc = new RTCPeerConnection({
                iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
            });
            pcRef.current = pc;

            // Add local tracks
            stream.getTracks().forEach(track => {
                pc.addTrack(track, stream);
            });

            // Handle connection state
            pc.onconnectionstatechange = () => {
                const state = pc.connectionState;
                console.log('WebRTC State:', state);
                if (state === 'connected') setStatus('connected');
                if (state === 'failed') setStatus('failed');
            };

            // Handle incoming tracks (Remote Stream)
            pc.ontrack = (event) => {
                console.log('Track received:', event.track.kind);
                if (videoRef.current) {
                    if (!videoRef.current.srcObject) {
                        videoRef.current.srcObject = new MediaStream();
                    }
                    (videoRef.current.srcObject as MediaStream).addTrack(event.track);
                }
            };

            // Handle ICE candidates - send to server
            pc.onicecandidate = (event) => {
                if (event.candidate) {
                    console.log('Sending ICE candidate');
                    ws.send(JSON.stringify({
                        type: 'candidate',
                        content: JSON.stringify(event.candidate),
                        metadata: {}
                    }));
                }
            };

            // 4. Create Offer
            const offer = await pc.createOffer();
            await pc.setLocalDescription(offer);

            // 5. Send Offer via WS
            ws.send(JSON.stringify({
                type: 'offer',
                content: offer.sdp,
                metadata: { type: 'offer' }
            }));

            // 6. Handle messages from WS (Answer + ICE candidates)
            ws.onmessage = async (event) => {
                const msg = JSON.parse(event.data);
                if (msg.type === 'answer') {
                    await pc.setRemoteDescription(new RTCSessionDescription({
                        type: 'answer',
                        sdp: msg.content
                    }));
                } else if (msg.type === 'candidate' && msg.content) {
                    try {
                        const candidate = JSON.parse(msg.content);
                        await pc.addIceCandidate(new RTCIceCandidate(candidate));
                        console.log('Added remote ICE candidate');
                    } catch (e) {
                        console.error('Error adding ICE candidate:', e);
                    }
                }
            };

        } catch (err: any) {
            console.error('WebRTC Error:', err);
            setError(err.message || 'Failed to connect');
            setStatus('failed');
            cleanup();
        }
    }, [sessionId, cleanup]);

    useEffect(() => {
        return cleanup;
    }, [cleanup]);

    const [stats, setStats] = useState({ latency: 0, frameCount: 0, messageCount: 0 });

    // Helper properties
    const isConnected = status === 'connected';
    const isConnecting = status === 'connecting';

    const sendMessage = useCallback((text: string) => {
        console.log('Sending message (stub):', text);
        // TODO: Implement DataChannel
    }, []);

    const sendAudio = useCallback((blob: Blob) => {
        console.log('Sending audio (stub):', blob.size);
        // TODO: Implement send
    }, []);

    const updateConfig = useCallback((config: any) => {
        console.log('Updating config:', config);
    }, []);

    return {
        connect,
        disconnect: cleanup,
        status,
        error,
        videoRef,
        stats,
        isConnected,
        isConnecting,
        sendMessage,
        sendAudio,
        updateConfig
    };
}
