'use client';

import { useState, useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import { Mic, Plus, Play, Settings2, Loader2, Trash2, Upload } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
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
    try {
      await ttsApi.createVoice({
        name: formData.name,
        language: formData.language,
        gender: formData.gender,
        sample_file: sampleFile || undefined,
      });
      toast.success('Voice created');
      setShowCreateModal(false);
      setFormData({ name: '', language: 'en', gender: 'neutral' });
      setSampleFile(null);
      fetchVoices();
    } catch (err: any) {
      toast.error('Failed to create voice');
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
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <Card className="w-full max-w-md m-4">
              <CardContent className="p-6 space-y-4">
                <h2 className="text-xl font-semibold">Clone Voice</h2>
                <div>
                  <Label>Voice Name</Label>
                  <Input
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    placeholder="e.g., My Custom Voice"
                  />
                </div>
                <div>
                  <Label>Language</Label>
                  <select
                    value={formData.language}
                    onChange={(e) => setFormData({ ...formData, language: e.target.value })}
                    className="w-full px-3 py-2 border rounded-md"
                  >
                    <option value="en">English</option>
                    <option value="es">Spanish</option>
                    <option value="fr">French</option>
                    <option value="de">German</option>
                    <option value="it">Italian</option>
                  </select>
                </div>
                <div>
                  <Label>Gender</Label>
                  <select
                    value={formData.gender}
                    onChange={(e) => setFormData({ ...formData, gender: e.target.value })}
                    className="w-full px-3 py-2 border rounded-md"
                  >
                    <option value="neutral">Neutral</option>
                    <option value="male">Male</option>
                    <option value="female">Female</option>
                  </select>
                </div>
                <div>
                  <Label>Sample Audio (optional)</Label>
                  <div className="flex items-center gap-2">
                    <Input
                      type="file"
                      accept="audio/*"
                      onChange={(e) => setSampleFile(e.target.files?.[0] || null)}
                      className="flex-1"
                    />
                    {sampleFile && (
                      <span className="text-sm text-muted-foreground">{sampleFile.name}</span>
                    )}
                  </div>
                </div>
                <div className="flex gap-2 justify-end">
                  <Button
                    variant="outline"
                    onClick={() => {
                      setShowCreateModal(false);
                      setFormData({ name: '', language: 'en', gender: 'neutral' });
                      setSampleFile(null);
                    }}
                  >
                    Cancel
                  </Button>
                  <Button onClick={handleCreate}>Create</Button>
                </div>
              </CardContent>
            </Card>
          </div>
        )}
      </motion.div>
    </div>
  );
}

