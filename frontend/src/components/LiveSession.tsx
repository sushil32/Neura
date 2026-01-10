"use client";

import { useEffect, useRef } from 'react';
import { useWebRTC } from '@/hooks/useWebRTC';

interface LiveSessionProps {
    sessionId: string;
    onEnd: () => void;
}

export function LiveSession({ sessionId, onEnd }: LiveSessionProps) {
    const { status, error, videoRef, connect, disconnect } = useWebRTC({ sessionId });

    // Auto-connect on mount
    useEffect(() => {
        connect();
        return () => {
            disconnect();
        };
    }, [connect, disconnect]);

    return (
        <div className="flex flex-col items-center justify-center p-6 bg-gray-900 rounded-xl border border-gray-800 w-full max-w-4xl mx-auto my-8">
            <div className="relative w-full aspect-video bg-black rounded-lg overflow-hidden mb-6 shadow-2xl">
                <video
                    ref={videoRef}
                    autoPlay
                    playsInline
                    muted // Muted to prevent feedback if it's playing local audio? No, we want remote audio.
                    // IMPORTANT: If videoRef is for LOCAL stream (for debugging), mute it. 
                    // If it's for REMOTE stream (Avatar), unmute it.
                    // Currently useWebRTC doesn't distinguish streams well in UI ref.
                    // useWebRTC needs to attach REMOTE stream to videoRef.
                    // But useWebRTC implementation attaches LOCAL stream in early steps? 
                    // Wait, useWebRTC currently DOES NOT receive distinct remote stream in the example earlier.
                    // It processes `on("track")` but didn't attach to a state/ref.
                    // I need to fix useWebRTC to handle remote stream.
                    className="w-full h-full object-cover"
                />

                <div className="absolute top-4 right-4 px-3 py-1 rounded-full bg-black/60 text-white text-sm backdrop-blur-sm border border-white/10">
                    Status: <span className={
                        status === 'connected' ? 'text-green-400' :
                            status === 'connecting' ? 'text-yellow-400' :
                                'text-red-400'
                    }>{status}</span>
                </div>
            </div>

            {error && (
                <div className="mb-4 p-4 bg-red-900/50 text-red-200 rounded-lg border border-red-800">
                    Error: {error}
                </div>
            )}

            <div className="flex gap-4">
                <button
                    onClick={onEnd}
                    className="px-6 py-3 bg-red-600 hover:bg-red-700 text-white font-semibold rounded-lg transition-colors shadow-lg shadow-red-900/20"
                >
                    End Session
                </button>
            </div>
        </div>
    );
}
