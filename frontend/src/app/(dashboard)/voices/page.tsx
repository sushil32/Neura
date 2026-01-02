'use client';

import { motion } from 'framer-motion';
import { Mic, Plus, Play, Settings2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';

export default function VoicesPage() {
  const voices = [
    { id: '1', name: 'Emily', language: 'English (US)', gender: 'Female', isDefault: true },
    { id: '2', name: 'James', language: 'English (UK)', gender: 'Male', isDefault: false },
    { id: '3', name: 'Sofia', language: 'Spanish', gender: 'Female', isDefault: false },
    { id: '4', name: 'Custom Voice', language: 'English (US)', gender: 'Cloned', isDefault: false },
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
            <h1 className="text-3xl font-bold">Voice Profiles</h1>
            <p className="text-muted-foreground mt-1">
              Manage voices for your AI videos
            </p>
          </div>
          <Button>
            <Plus className="w-4 h-4 mr-2" />
            Clone Voice
          </Button>
        </div>

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
                        {voice.isDefault && (
                          <span className="px-2 py-0.5 rounded-full bg-primary/10 text-primary text-xs">
                            Default
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-muted-foreground">{voice.language}</p>
                      <p className="text-xs text-muted-foreground mt-1">{voice.gender}</p>
                    </div>
                  </div>
                  
                  <div className="flex gap-2 mt-4">
                    <Button variant="outline" size="sm" className="flex-1">
                      <Play className="w-4 h-4 mr-1" />
                      Preview
                    </Button>
                    <Button variant="ghost" size="sm">
                      <Settings2 className="w-4 h-4" />
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>
      </motion.div>
    </div>
  );
}

