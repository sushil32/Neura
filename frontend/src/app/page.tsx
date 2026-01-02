'use client';

import Link from 'next/link';
import { motion } from 'framer-motion';
import { ArrowRight, Play, Sparkles, Video, Mic, Zap } from 'lucide-react';
import { Button } from '@/components/ui/button';

export default function HomePage() {
  return (
    <div className="min-h-screen gradient-bg">
      {/* Header */}
      <header className="fixed top-0 left-0 right-0 z-50 glass">
        <div className="container mx-auto px-6 py-4 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-neura-400 to-neura-600 flex items-center justify-center">
              <Sparkles className="w-5 h-5 text-white" />
            </div>
            <span className="text-xl font-bold text-gradient">NEURA</span>
          </Link>
          
          <nav className="hidden md:flex items-center gap-8">
            <Link href="#features" className="text-muted-foreground hover:text-foreground transition">
              Features
            </Link>
            <Link href="#pricing" className="text-muted-foreground hover:text-foreground transition">
              Pricing
            </Link>
            <Link href="/docs" className="text-muted-foreground hover:text-foreground transition">
              Docs
            </Link>
          </nav>
          
          <div className="flex items-center gap-4">
            <Link href="/login">
              <Button variant="ghost">Sign In</Button>
            </Link>
            <Link href="/register">
              <Button>Get Started</Button>
            </Link>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="pt-32 pb-20 px-6">
        <div className="container mx-auto max-w-6xl">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
            className="text-center"
          >
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-neura-500/10 border border-neura-500/20 mb-8">
              <Sparkles className="w-4 h-4 text-neura-400" />
              <span className="text-sm text-neura-400">Introducing NEURA</span>
            </div>
            
            <h1 className="text-5xl md:text-7xl font-bold mb-6">
              Where AI{' '}
              <span className="text-gradient">Comes Alive</span>
            </h1>
            
            <p className="text-xl text-muted-foreground max-w-2xl mx-auto mb-10">
              Create lifelike digital humans that speak, react, and present content 
              in real-time. Transform your ideas into engaging video content.
            </p>
            
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <Link href="/register">
                <Button size="lg" className="glow">
                  Start Creating
                  <ArrowRight className="w-4 h-4 ml-2" />
                </Button>
              </Link>
              <Button size="lg" variant="outline">
                <Play className="w-4 h-4 mr-2" />
                Watch Demo
              </Button>
            </div>
          </motion.div>

          {/* Hero Visual */}
          <motion.div
            initial={{ opacity: 0, y: 40 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.2 }}
            className="mt-20 relative"
          >
            <div className="aspect-video rounded-2xl bg-card border border-border overflow-hidden shadow-2xl glow">
              <div className="absolute inset-0 flex items-center justify-center">
                <div className="w-32 h-32 rounded-full bg-gradient-to-br from-neura-400/20 to-neura-600/20 flex items-center justify-center">
                  <Play className="w-12 h-12 text-neura-400" />
                </div>
              </div>
              {/* Placeholder for avatar preview */}
              <div className="absolute bottom-0 left-0 right-0 h-1/2 bg-gradient-to-t from-background to-transparent" />
            </div>
          </motion.div>
        </div>
      </section>

      {/* Features Section */}
      <section id="features" className="py-20 px-6">
        <div className="container mx-auto max-w-6xl">
          <motion.div
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
            className="text-center mb-16"
          >
            <h2 className="text-4xl font-bold mb-4">Powerful Features</h2>
            <p className="text-muted-foreground max-w-2xl mx-auto">
              Everything you need to create stunning AI-powered videos
            </p>
          </motion.div>

          <div className="grid md:grid-cols-3 gap-8">
            {[
              {
                icon: Video,
                title: 'AI Video Generation',
                description: 'Create professional videos with AI avatars that lip-sync perfectly with your script.',
              },
              {
                icon: Mic,
                title: 'Custom Voice Cloning',
                description: 'Clone any voice from a short sample and use it for your videos.',
              },
              {
                icon: Zap,
                title: 'Real-Time Streaming',
                description: 'Stream live AI avatars with < 500ms latency for interactive experiences.',
              },
            ].map((feature, index) => (
              <motion.div
                key={feature.title}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: index * 0.1 }}
                className="p-6 rounded-2xl bg-card border border-border hover:border-neura-500/50 transition group"
              >
                <div className="w-12 h-12 rounded-xl bg-neura-500/10 flex items-center justify-center mb-4 group-hover:bg-neura-500/20 transition">
                  <feature.icon className="w-6 h-6 text-neura-400" />
                </div>
                <h3 className="text-xl font-semibold mb-2">{feature.title}</h3>
                <p className="text-muted-foreground">{feature.description}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20 px-6">
        <div className="container mx-auto max-w-4xl">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true }}
            className="p-12 rounded-3xl bg-gradient-to-br from-neura-600 to-neura-800 text-center relative overflow-hidden"
          >
            <div className="absolute inset-0 opacity-30">
              <div className="absolute top-0 left-1/4 w-64 h-64 bg-white/20 rounded-full blur-3xl" />
              <div className="absolute bottom-0 right-1/4 w-64 h-64 bg-white/10 rounded-full blur-3xl" />
            </div>
            
            <div className="relative">
              <h2 className="text-4xl font-bold text-white mb-4">
                Ready to Create?
              </h2>
              <p className="text-neura-100 mb-8 max-w-xl mx-auto">
                Start creating stunning AI videos today. No credit card required.
              </p>
              <Link href="/register">
                <Button size="lg" variant="secondary" className="bg-white text-neura-700 hover:bg-white/90">
                  Get Started Free
                  <ArrowRight className="w-4 h-4 ml-2" />
                </Button>
              </Link>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-12 px-6 border-t border-border">
        <div className="container mx-auto max-w-6xl">
          <div className="flex flex-col md:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <div className="w-6 h-6 rounded bg-gradient-to-br from-neura-400 to-neura-600 flex items-center justify-center">
                <Sparkles className="w-4 h-4 text-white" />
              </div>
              <span className="font-semibold">NEURA</span>
            </div>
            <p className="text-muted-foreground text-sm">
              © 2024 NEURA. All rights reserved.
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}

