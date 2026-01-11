'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Users, Plus, Settings2, Loader2, Trash2, Edit2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { avatarsApi } from '@/lib/api';
import { toast } from 'sonner';
import type { Avatar } from '@/lib/types';

export default function AvatarsPage() {
  const [avatars, setAvatars] = useState<Avatar[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingAvatar, setEditingAvatar] = useState<Avatar | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    is_default: false,
  });
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  useEffect(() => {
    fetchAvatars();
  }, []);

  const fetchAvatars = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await avatarsApi.list({ include_public: true });
      setAvatars(response.avatars || []);
    } catch (err: any) {
      setError(err.message || 'Failed to load avatars');
      toast.error('Failed to load avatars');
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async () => {
    try {
      const newAvatar = await avatarsApi.create({
        name: formData.name,
        description: formData.description || undefined,
        is_default: formData.is_default,
      });

      if (selectedFile) {
        try {
          await avatarsApi.uploadThumbnail(newAvatar.id, selectedFile);
        } catch (uploadErr) {
          console.error('Failed to upload image:', uploadErr);
          toast.error('Avatar created but image upload failed');
        }
      }

      toast.success('Avatar created');
      setShowCreateModal(false);
      setFormData({ name: '', description: '', is_default: false });
      setSelectedFile(null);
      fetchAvatars();
    } catch (err: any) {
      toast.error('Failed to create avatar');
    }
  };

  const handleUpdate = async () => {
    if (!editingAvatar) return;
    try {
      await avatarsApi.update(editingAvatar.id, {
        name: formData.name,
        description: formData.description || undefined,
        is_default: formData.is_default,
      });
      toast.success('Avatar updated');
      setEditingAvatar(null);
      setFormData({ name: '', description: '', is_default: false });
      fetchAvatars();
    } catch (err: any) {
      toast.error('Failed to update avatar');
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to delete this avatar?')) return;
    try {
      setDeletingId(id);
      await avatarsApi.delete(id);
      toast.success('Avatar deleted');
      setAvatars(avatars.filter(a => a.id !== id));
    } catch (err: any) {
      toast.error('Failed to delete avatar');
    } finally {
      setDeletingId(null);
    }
  };

  const openEditModal = (avatar: Avatar) => {
    setEditingAvatar(avatar);
    setFormData({
      name: avatar.name,
      description: avatar.description || '',
      is_default: avatar.is_default,
    });
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
            <h1 className="text-3xl font-bold">Avatars</h1>
            <p className="text-muted-foreground mt-1">
              Choose and customize your AI presenters
            </p>
          </div>
          <Button onClick={() => setShowCreateModal(true)}>
            <Plus className="w-4 h-4 mr-2" />
            Create Avatar
          </Button>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
          </div>
        ) : error ? (
          <Card>
            <CardContent className="py-16 text-center">
              <p className="text-destructive mb-4">{error}</p>
              <Button onClick={fetchAvatars}>Retry</Button>
            </CardContent>
          </Card>
        ) : avatars.length === 0 ? (
          <Card>
            <CardContent className="py-16 text-center">
              <Users className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
              <h3 className="text-lg font-semibold mb-2">No avatars found</h3>
              <p className="text-muted-foreground mb-4">
                Create your first avatar to get started
              </p>
              <Button onClick={() => setShowCreateModal(true)}>
                <Plus className="w-4 h-4 mr-2" />
                Create Avatar
              </Button>
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {avatars.map((avatar, index) => (
              <motion.div
                key={avatar.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.1 }}
              >
                <Card className="overflow-hidden group hover:border-primary transition">
                  <div className="aspect-square bg-gradient-to-br from-neura-400/20 to-neura-600/20 flex items-center justify-center relative">
                    {avatar.thumbnail_url ? (
                      <img
                        src={avatar.thumbnail_url}
                        alt={avatar.name}
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <Users className="w-16 h-16 text-muted-foreground" />
                    )}
                    {avatar.is_default && (
                      <span className="absolute top-2 right-2 px-2 py-1 rounded-full bg-primary text-primary-foreground text-xs">
                        Default
                      </span>
                    )}
                    {avatar.is_public && (
                      <span className="absolute top-2 left-2 px-2 py-1 rounded-full bg-green-500/10 text-green-500 text-xs">
                        Public
                      </span>
                    )}
                    <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition flex items-center justify-center gap-2">
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={() => openEditModal(avatar)}
                      >
                        <Edit2 className="w-4 h-4 mr-2" />
                        Edit
                      </Button>
                      <Button
                        size="sm"
                        variant="destructive"
                        onClick={() => handleDelete(avatar.id)}
                        disabled={deletingId === avatar.id}
                      >
                        {deletingId === avatar.id ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <Trash2 className="w-4 h-4" />
                        )}
                      </Button>
                    </div>
                  </div>
                  <CardContent className="p-4">
                    <h3 className="font-semibold">{avatar.name}</h3>
                    {avatar.description && (
                      <p className="text-sm text-muted-foreground truncate">{avatar.description}</p>
                    )}
                    {avatar.config && (
                      <p className="text-xs text-muted-foreground mt-1">
                        {avatar.config.style || 'Custom'}
                      </p>
                    )}
                  </CardContent>
                </Card>
              </motion.div>
            ))}
          </div>
        )}

        {/* Create/Edit Modal */}
        {(showCreateModal || editingAvatar) && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <Card className="w-full max-w-md m-4">
              <CardHeader>
                <CardTitle>{editingAvatar ? 'Edit Avatar' : 'Create Avatar'}</CardTitle>
                <CardDescription>
                  {editingAvatar ? 'Update avatar details' : 'Create a new AI presenter'}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <Label>Name</Label>
                  <Input
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    placeholder="Avatar name"
                  />
                </div>
                <div>
                  <Input
                    value={formData.description}
                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                    placeholder="Avatar description"
                  />
                </div>
                {!editingAvatar && (
                  <div>
                    <Label>Avatar Image (Portrait)</Label>
                    <Input
                      type="file"
                      accept="image/*"
                      onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                      className="cursor-pointer"
                    />
                    <p className="text-xs text-muted-foreground mt-1">
                      Upload a clear portrait photo (PNG/JPG).
                    </p>
                  </div>
                )}
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="is_default"
                    checked={formData.is_default}
                    onChange={(e) => setFormData({ ...formData, is_default: e.target.checked })}
                    className="w-4 h-4"
                  />
                  <Label htmlFor="is_default">Set as default avatar</Label>
                </div>
                <div className="flex gap-2 justify-end">
                  <Button
                    variant="outline"
                    onClick={() => {
                      setShowCreateModal(false);
                      setEditingAvatar(null);
                      setFormData({ name: '', description: '', is_default: false });
                      setSelectedFile(null);
                    }}
                  >
                    Cancel
                  </Button>
                  <Button onClick={editingAvatar ? handleUpdate : handleCreate} disabled={!formData.name || (showCreateModal && !editingAvatar && !selectedFile)}>
                    {editingAvatar ? 'Update' : 'Create'}
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

