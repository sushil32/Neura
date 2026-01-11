'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { Mic, Square, Play, RotateCcw, Check } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';

interface VoiceRecorderProps {
    onRecordingComplete: (blob: Blob) => void;
    minDuration?: number; // Minimum recording duration in seconds
    maxDuration?: number; // Maximum recording duration in seconds
}

const SAMPLE_SCRIPT = `Hello, my name is... and I'm recording my voice for voice cloning. 
I'll speak naturally and clearly so the AI can learn my unique voice patterns.
The quick brown fox jumps over the lazy dog. Pack my box with five dozen liquor jugs.
I enjoy creating content and sharing my ideas with the world.`;

export function VoiceRecorder({
    onRecordingComplete,
    minDuration = 6,
    maxDuration = 30
}: VoiceRecorderProps) {
    const [isRecording, setIsRecording] = useState(false);
    const [isPaused, setIsPaused] = useState(false);
    const [recordedBlob, setRecordedBlob] = useState<Blob | null>(null);
    const [duration, setDuration] = useState(0);
    const [audioLevel, setAudioLevel] = useState(0);
    const [isPlaying, setIsPlaying] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const mediaRecorderRef = useRef<MediaRecorder | null>(null);
    const audioContextRef = useRef<AudioContext | null>(null);
    const analyserRef = useRef<AnalyserNode | null>(null);
    const streamRef = useRef<MediaStream | null>(null);
    const chunksRef = useRef<Blob[]>([]);
    const timerRef = useRef<NodeJS.Timeout | null>(null);
    const audioRef = useRef<HTMLAudioElement | null>(null);
    const animationRef = useRef<number | null>(null);

    // Cleanup on unmount
    useEffect(() => {
        return () => {
            stopRecording();
            if (audioRef.current) {
                audioRef.current.pause();
            }
        };
    }, []);

    const updateAudioLevel = useCallback(() => {
        if (analyserRef.current && isRecording) {
            const dataArray = new Uint8Array(analyserRef.current.frequencyBinCount);
            analyserRef.current.getByteFrequencyData(dataArray);

            // Calculate average level
            const average = dataArray.reduce((a, b) => a + b, 0) / dataArray.length;
            setAudioLevel(Math.min(100, (average / 128) * 100));

            animationRef.current = requestAnimationFrame(updateAudioLevel);
        }
    }, [isRecording]);

    const startRecording = async () => {
        try {
            setError(null);
            chunksRef.current = [];
            setRecordedBlob(null);

            // Request microphone access with specific constraints for quality
            const stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    sampleRate: 48000, // High quality, will be converted server-side
                    channelCount: 1,   // Mono
                }
            });

            streamRef.current = stream;

            // Set up audio context for level monitoring
            audioContextRef.current = new AudioContext();
            const source = audioContextRef.current.createMediaStreamSource(stream);
            analyserRef.current = audioContextRef.current.createAnalyser();
            analyserRef.current.fftSize = 256;
            source.connect(analyserRef.current);

            // Create MediaRecorder
            const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
                ? 'audio/webm;codecs=opus'
                : 'audio/webm';

            mediaRecorderRef.current = new MediaRecorder(stream, { mimeType });

            mediaRecorderRef.current.ondataavailable = (e) => {
                if (e.data.size > 0) {
                    chunksRef.current.push(e.data);
                }
            };

            mediaRecorderRef.current.onstop = () => {
                const blob = new Blob(chunksRef.current, { type: 'audio/webm' });
                setRecordedBlob(blob);
            };

            // Start recording
            mediaRecorderRef.current.start(100); // Collect data every 100ms
            setIsRecording(true);
            setDuration(0);

            // Start duration timer
            timerRef.current = setInterval(() => {
                setDuration(prev => {
                    const newDuration = prev + 1;
                    if (newDuration >= maxDuration) {
                        stopRecording();
                    }
                    return newDuration;
                });
            }, 1000);

            // Start audio level monitoring
            updateAudioLevel();

        } catch (err: any) {
            setError(err.message || 'Failed to access microphone');
            console.error('Recording error:', err);
        }
    };

    const stopRecording = () => {
        if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
            mediaRecorderRef.current.stop();
        }

        if (streamRef.current) {
            streamRef.current.getTracks().forEach(track => track.stop());
            streamRef.current = null;
        }

        if (timerRef.current) {
            clearInterval(timerRef.current);
            timerRef.current = null;
        }

        if (animationRef.current) {
            cancelAnimationFrame(animationRef.current);
            animationRef.current = null;
        }

        if (audioContextRef.current) {
            audioContextRef.current.close();
            audioContextRef.current = null;
        }

        setIsRecording(false);
        setAudioLevel(0);
    };

    const playRecording = () => {
        if (recordedBlob && audioRef.current) {
            const url = URL.createObjectURL(recordedBlob);
            audioRef.current.src = url;
            audioRef.current.onended = () => setIsPlaying(false);
            audioRef.current.play();
            setIsPlaying(true);
        }
    };

    const resetRecording = () => {
        setRecordedBlob(null);
        setDuration(0);
        if (audioRef.current) {
            audioRef.current.pause();
            audioRef.current.src = '';
        }
        setIsPlaying(false);
    };

    const confirmRecording = () => {
        if (recordedBlob) {
            onRecordingComplete(recordedBlob);
        }
    };

    const formatTime = (seconds: number) => {
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    };

    const isValidDuration = duration >= minDuration;

    return (
        <div className="space-y-4">
            <audio ref={audioRef} className="hidden" />

            {/* Sample Script */}
            <div className="bg-muted/50 rounded-lg p-4">
                <p className="text-sm font-medium mb-2">📝 Sample Script (read this naturally):</p>
                <p className="text-sm text-muted-foreground italic whitespace-pre-line">
                    {SAMPLE_SCRIPT}
                </p>
            </div>

            {/* Recording Controls */}
            <div className="flex flex-col items-center gap-4 py-4">
                {/* Audio Level Indicator */}
                {isRecording && (
                    <div className="w-full space-y-1">
                        <div className="flex justify-between text-xs text-muted-foreground">
                            <span>Audio Level</span>
                            <span>{formatTime(duration)} / {formatTime(maxDuration)}</span>
                        </div>
                        <div className="h-2 bg-muted rounded-full overflow-hidden">
                            <div
                                className="h-full bg-gradient-to-r from-green-500 via-yellow-500 to-red-500 transition-all duration-75"
                                style={{ width: `${audioLevel}%` }}
                            />
                        </div>
                        <Progress value={(duration / maxDuration) * 100} className="h-1" />
                    </div>
                )}

                {/* Main Record Button */}
                <div className="flex items-center gap-4">
                    {!isRecording && !recordedBlob && (
                        <Button
                            size="lg"
                            onClick={startRecording}
                            className="rounded-full w-16 h-16 bg-red-500 hover:bg-red-600"
                        >
                            <Mic className="w-8 h-8" />
                        </Button>
                    )}

                    {isRecording && (
                        <Button
                            size="lg"
                            onClick={stopRecording}
                            variant="destructive"
                            className="rounded-full w-16 h-16"
                        >
                            <Square className="w-8 h-8" />
                        </Button>
                    )}

                    {recordedBlob && !isRecording && (
                        <div className="flex items-center gap-2">
                            <Button
                                size="lg"
                                variant="outline"
                                onClick={playRecording}
                                disabled={isPlaying}
                                className="rounded-full w-12 h-12"
                            >
                                <Play className="w-5 h-5" />
                            </Button>
                            <Button
                                size="lg"
                                variant="outline"
                                onClick={resetRecording}
                                className="rounded-full w-12 h-12"
                            >
                                <RotateCcw className="w-5 h-5" />
                            </Button>
                            <Button
                                size="lg"
                                onClick={confirmRecording}
                                disabled={!isValidDuration}
                                className="rounded-full w-12 h-12 bg-green-500 hover:bg-green-600"
                            >
                                <Check className="w-5 h-5" />
                            </Button>
                        </div>
                    )}
                </div>

                {/* Status Text */}
                <p className="text-sm text-muted-foreground text-center">
                    {!isRecording && !recordedBlob && 'Click the microphone to start recording'}
                    {isRecording && 'Recording... Click the square to stop'}
                    {recordedBlob && !isValidDuration && (
                        <span className="text-amber-500">
                            Recording too short. Minimum {minDuration} seconds required.
                        </span>
                    )}
                    {recordedBlob && isValidDuration && 'Click ✓ to use this recording'}
                </p>

                {/* Duration Info */}
                {recordedBlob && (
                    <p className="text-xs text-muted-foreground">
                        Duration: {formatTime(duration)} (min: {minDuration}s, max: {maxDuration}s)
                    </p>
                )}
            </div>

            {/* Error Display */}
            {error && (
                <div className="bg-destructive/10 text-destructive rounded-lg p-3 text-sm">
                    {error}
                </div>
            )}

            {/* Tips */}
            <div className="text-xs text-muted-foreground space-y-1">
                <p>💡 <strong>Tips for best results:</strong></p>
                <ul className="list-disc list-inside space-y-0.5 ml-2">
                    <li>Find a quiet room with no background noise</li>
                    <li>Speak naturally at a normal pace</li>
                    <li>Position yourself 6-12 inches from the microphone</li>
                    <li>Record at least 10-15 seconds for best quality</li>
                </ul>
            </div>
        </div>
    );
}
