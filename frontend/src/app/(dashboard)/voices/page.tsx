'use client';

import { useState, useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import { Mic, Plus, Play, Settings2, Loader2, Trash2, Upload } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { VoiceRecorder } from '@/components/voice-recorder';
import { ttsApi } from '@/lib/api';
import { toast } from 'sonner';
import type { Voice } from '@/lib/types';

export default function VoicesPage() {
  const [voices, setVoices] = useState<Voice[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [previewingId, setPreviewingId] = useState<string | null>(null);
  const [formData, setFormData] = useState({
    name: '',
    language: 'en',
    gender: 'neutral',
  });
  const [sampleFile, setSampleFile] = useState<File | null>(null);
  const [recordedBlob, setRecordedBlob] = useState<Blob | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    fetchVoices();
  }, []);

  const fetchVoices = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await ttsApi.listVoices();
      setVoices(response.voices || []);
    } catch (err: any) {
      setError(err.message || 'Failed to load voices');
      toast.error('Failed to load voices');
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async () => {
    if (!formData.name.trim()) {
      toast.error('Please enter a voice name');
      return;
    }
    if (!sampleFile) {
      toast.error('Please upload an audio sample to clone');
      return;
    }
    try {
      await ttsApi.createVoice({
        name: formData.name,
        language: formData.language,
        sample_file: sampleFile,
      });
      toast.success('Voice cloned successfully!');
      setShowCreateModal(false);
      setFormData({ name: '', language: 'en', gender: 'neutral' });
      setSampleFile(null);
      fetchVoices();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to clone voice');
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to delete this voice?')) return;
    try {
      setDeletingId(id);
      await ttsApi.deleteVoice(id);
      toast.success('Voice deleted');
      setVoices(voices.filter(v => v.id !== id));
    } catch (err: any) {
      toast.error('Failed to delete voice');
    } finally {
      setDeletingId(null);
    }
  };

  const handlePreview = async (voice: Voice) => {
    setPreviewingId(voice.id);
    try {
      const previewUrl = await ttsApi.previewVoice(voice.id);
      if (audioRef.current) {
        audioRef.current.src = previewUrl;
        audioRef.current.onended = () => setPreviewingId(null);
        audioRef.current.onerror = () => {
          toast.error('Failed to load preview');
          setPreviewingId(null);
        };
        audioRef.current.play();
      }
    } catch (err: any) {
      toast.error('Failed to play preview');
      setPreviewingId(null);
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
            <h1 className="text-3xl font-bold">Voice Profiles</h1>
            <p className="text-muted-foreground mt-1">
              Manage voices for your AI videos
            </p>
          </div>
          <Button onClick={() => setShowCreateModal(true)}>
            <Plus className="w-4 h-4 mr-2" />
            Clone Voice
          </Button>
        </div>

        <audio ref={audioRef} className="hidden" />

        {loading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
          </div>
        ) : error ? (
          <Card>
            <CardContent className="py-16 text-center">
              <p className="text-destructive mb-4">{error}</p>
              <Button onClick={fetchVoices}>Retry</Button>
            </CardContent>
          </Card>
        ) : voices.length === 0 ? (
          <Card>
            <CardContent className="py-16 text-center">
              <Mic className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
              <h3 className="text-lg font-semibold mb-2">No voices found</h3>
              <p className="text-muted-foreground mb-4">
                Create your first voice to get started
              </p>
              <Button onClick={() => setShowCreateModal(true)}>
                <Plus className="w-4 h-4 mr-2" />
                Clone Voice
              </Button>
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {voices.map((voice, index) => (
              <motion.div
                key={voice.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.1 }}
              >
                <Card className="overflow-hidden">
                  <CardContent className="p-6">
                    <div className="flex items-start gap-4">
                      <div className="w-12 h-12 rounded-full bg-neura-500/10 flex items-center justify-center shrink-0">
                        <Mic className="w-6 h-6 text-neura-500" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <h3 className="font-semibold">{voice.name}</h3>
                          {voice.is_default && (
                            <span className="px-2 py-0.5 rounded-full bg-primary/10 text-primary text-xs">
                              Default
                            </span>
                          )}
                        </div>
                        <p className="text-sm text-muted-foreground">{voice.language}</p>
                        <p className="text-xs text-muted-foreground mt-1 capitalize">{voice.gender}</p>
                      </div>
                    </div>

                    <div className="flex gap-2 mt-4">
                      <Button
                        variant="outline"
                        size="sm"
                        className="flex-1"
                        onClick={() => handlePreview(voice)}
                        disabled={previewingId === voice.id}
                      >
                        {previewingId === voice.id ? (
                          <Loader2 className="w-4 h-4 mr-1 animate-spin" />
                        ) : (
                          <Play className="w-4 h-4 mr-1" />
                        )}
                        Preview
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDelete(voice.id)}
                        disabled={deletingId === voice.id}
                      >
                        {deletingId === voice.id ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <Trash2 className="w-4 h-4" />
                        )}
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            ))}
          </div>
        )}

        {/* Create Modal */}
        {showCreateModal && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 overflow-y-auto p-4">
            <Card className="w-full max-w-lg">
              <CardContent className="p-6 space-y-4">
                <h2 className="text-xl font-semibold">Clone Your Voice</h2>
                <p className="text-sm text-muted-foreground">
                  Record or upload a voice sample to create your personalized AI voice.
                </p>

                <div>
                  <Label>Voice Name</Label>
                  <Input
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    placeholder="e.g., My Voice"
                  />
                </div>

                <div>
                  <Label>Language</Label>
                  <select
                    value={formData.language}
                    onChange={(e) => setFormData({ ...formData, language: e.target.value })}
                    className="w-full px-3 py-2 border rounded-md bg-background"
                  >
                    <option value="en">English (US/General)</option>
                    <option value="en-IN">English (Indian)</option>
                    <option value="es">Spanish</option>
                    <option value="fr">French</option>
                    <option value="de">German</option>
                    <option value="it">Italian</option>
                    <option value="pt">Portuguese</option>
                    <option value="hi">Hindi</option>
                  </select>
                </div>

                <div>
                  <Label>Gender</Label>
                  <select
                    value={formData.gender}
                    onChange={(e) => setFormData({ ...formData, gender: e.target.value })}
                    className="w-full px-3 py-2 border rounded-md bg-background"
                  >
                    <option value="neutral">Neutral</option>
                    <option value="male">Male</option>
                    <option value="female">Female</option>
                  </select>
                </div>

                <Tabs defaultValue="record" className="w-full">
                  <TabsList className="grid w-full grid-cols-2">
                    <TabsTrigger value="record">
                      <Mic className="w-4 h-4 mr-2" />
                      Record
                    </TabsTrigger>
                    <TabsTrigger value="upload">
                      <Upload className="w-4 h-4 mr-2" />
                      Upload
                    </TabsTrigger>
                  </TabsList>

                  <TabsContent value="record" className="mt-4">
                    <VoiceRecorder
                      onRecordingComplete={(blob) => {
                        setRecordedBlob(blob);
                        setSampleFile(null);
                        toast.success('Recording captured!');
                      }}
                      minDuration={6}
                      maxDuration={30}
                    />
                    {recordedBlob && (
                      <div className="mt-2 p-2 bg-green-500/10 text-green-600 rounded text-sm text-center">
                        ✓ Recording ready to use
                      </div>
                    )}
                  </TabsContent>

                  <TabsContent value="upload" className="mt-4">
                    <div className="space-y-4">
                      <div className="border-2 border-dashed rounded-lg p-6 text-center">
                        <Upload className="w-8 h-8 mx-auto mb-2 text-muted-foreground" />
                        <p className="text-sm text-muted-foreground mb-2">
                          Upload an audio file (WAV, MP3, M4A)
                        </p>
                        <Input
                          type="file"
                          accept="audio/*"
                          onChange={(e) => {
                            setSampleFile(e.target.files?.[0] || null);
                            setRecordedBlob(null);
                          }}
                          className="max-w-xs mx-auto"
                        />
                      </div>
                      {sampleFile && (
                        <div className="p-2 bg-green-500/10 text-green-600 rounded text-sm text-center">
                          ✓ {sampleFile.name} selected
                        </div>
                      )}
                      <div className="text-xs text-muted-foreground space-y-1">
                        <p>💡 <strong>Tips for best results:</strong></p>
                        <ul className="list-disc list-inside ml-2">
                          <li>Use 15-30 seconds of clear speech</li>
                          <li>No background noise or music</li>
                          <li>WAV format at 24kHz+ is ideal</li>
                          {formData.language === 'en-IN' && (
                            <li className="text-neura-500 font-medium">For Indian English, speak clearly and naturally</li>
                          )}
                        </ul>
                      </div>
                    </div>
                  </TabsContent>
                </Tabs>

                <div className="flex gap-2 justify-end pt-4 border-t">
                  <Button
                    variant="outline"
                    onClick={() => {
                      setShowCreateModal(false);
                      setFormData({ name: '', language: 'en', gender: 'neutral' });
                      setSampleFile(null);
                      setRecordedBlob(null);
                    }}
                  >
                    Cancel
                  </Button>
                  <Button
                    onClick={async () => {
                      if (!formData.name.trim()) {
                        toast.error('Please enter a voice name');
                        return;
                      }
                      const audioSource = recordedBlob || sampleFile;
                      if (!audioSource) {
                        toast.error('Please record or upload a voice sample');
                        return;
                      }

                      setIsCreating(true);
                      try {
                        // Convert blob to file if needed
                        const file = recordedBlob
                          ? new File([recordedBlob], 'recording.webm', { type: 'audio/webm' })
                          : sampleFile!;

                        await ttsApi.createVoice({
                          name: formData.name,
                          language: formData.language,
                          gender: formData.gender,
                          sample_file: file,
                        });
                        toast.success('Voice cloned successfully!');
                        setShowCreateModal(false);
                        setFormData({ name: '', language: 'en', gender: 'neutral' });
                        setSampleFile(null);
                        setRecordedBlob(null);
                        fetchVoices();
                      } catch (err: any) {
                        toast.error(err.response?.data?.detail || 'Failed to clone voice');
                      } finally {
                        setIsCreating(false);
                      }
                    }}
                    disabled={isCreating || (!sampleFile && !recordedBlob)}
                  >
                    {isCreating ? (
                      <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Cloning...</>
                    ) : (
                      'Clone Voice'
                    )}
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>
        )}
      </motion.div>
    </div>
  );
}

