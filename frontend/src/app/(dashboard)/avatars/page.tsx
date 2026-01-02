'use client';

import { motion } from 'framer-motion';
import { Users, Plus, Settings2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

export default function AvatarsPage() {
  const avatars = [
    { id: '1', name: 'Professional Woman', type: 'Realistic', isDefault: true },
    { id: '2', name: 'Business Man', type: 'Realistic', isDefault: false },
    { id: '3', name: 'Animated Host', type: 'Cartoon', isDefault: false },
    { id: '4', name: 'News Anchor', type: 'Realistic', isDefault: false },
  ];

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
          <Button>
            <Plus className="w-4 h-4 mr-2" />
            Create Avatar
          </Button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {avatars.map((avatar, index) => (
            <motion.div
              key={avatar.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.1 }}
            >
              <Card className="overflow-hidden group cursor-pointer hover:border-primary transition">
                <div className="aspect-square bg-gradient-to-br from-neura-400/20 to-neura-600/20 flex items-center justify-center relative">
                  <Users className="w-16 h-16 text-muted-foreground" />
                  {avatar.isDefault && (
                    <span className="absolute top-2 right-2 px-2 py-1 rounded-full bg-primary text-primary-foreground text-xs">
                      Default
                    </span>
                  )}
                  <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition flex items-center justify-center">
                    <Button size="sm" variant="secondary">
                      <Settings2 className="w-4 h-4 mr-2" />
                      Configure
                    </Button>
                  </div>
                </div>
                <CardContent className="p-4">
                  <h3 className="font-semibold">{avatar.name}</h3>
                  <p className="text-sm text-muted-foreground">{avatar.type}</p>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>
      </motion.div>
    </div>
  );
}

