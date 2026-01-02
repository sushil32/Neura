'use client';

import { motion } from 'framer-motion';
import Link from 'next/link';
import { 
  Video, 
  Clock, 
  CreditCard, 
  TrendingUp, 
  Plus,
  Play,
  ArrowRight,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { useAuth } from '@/lib/auth';
import { formatCredits } from '@/lib/utils';

export default function DashboardPage() {
  const { user } = useAuth();

  const stats = [
    {
      label: 'Videos Created',
      value: '12',
      change: '+3 this week',
      icon: Video,
      color: 'text-blue-500',
      bgColor: 'bg-blue-500/10',
    },
    {
      label: 'Total Duration',
      value: '45 min',
      change: '15 min this week',
      icon: Clock,
      color: 'text-green-500',
      bgColor: 'bg-green-500/10',
    },
    {
      label: 'Credits Used',
      value: formatCredits(user?.credits || 0),
      change: 'Available',
      icon: CreditCard,
      color: 'text-neura-500',
      bgColor: 'bg-neura-500/10',
    },
    {
      label: 'Views',
      value: '2.4k',
      change: '+12% this month',
      icon: TrendingUp,
      color: 'text-purple-500',
      bgColor: 'bg-purple-500/10',
    },
  ];

  const recentVideos = [
    { id: '1', title: 'Product Demo', status: 'completed', duration: '2:30', created: '2 hours ago' },
    { id: '2', title: 'Training Video', status: 'processing', duration: '5:00', created: '5 hours ago' },
    { id: '3', title: 'Marketing Intro', status: 'completed', duration: '1:45', created: '1 day ago' },
  ];

  return (
    <div className="p-8">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold">
              Welcome back, {user?.name?.split(' ')[0] || 'there'}!
            </h1>
            <p className="text-muted-foreground mt-1">
              Here's what's happening with your videos
            </p>
          </div>
          <Link href="/studio">
            <Button>
              <Plus className="w-4 h-4 mr-2" />
              Create Video
            </Button>
          </Link>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          {stats.map((stat, index) => (
            <motion.div
              key={stat.label}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.1 }}
            >
              <Card>
                <CardContent className="p-6">
                  <div className="flex items-start justify-between">
                    <div>
                      <p className="text-sm text-muted-foreground">{stat.label}</p>
                      <p className="text-3xl font-bold mt-1">{stat.value}</p>
                      <p className="text-xs text-muted-foreground mt-1">{stat.change}</p>
                    </div>
                    <div className={`p-3 rounded-lg ${stat.bgColor}`}>
                      <stat.icon className={`w-5 h-5 ${stat.color}`} />
                    </div>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>

        {/* Quick Actions */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle>Quick Actions</CardTitle>
              <CardDescription>Get started with common tasks</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-4">
                <Link href="/studio">
                  <div className="p-4 rounded-lg border border-border hover:border-primary/50 hover:bg-primary/5 transition cursor-pointer group">
                    <Video className="w-8 h-8 text-primary mb-3" />
                    <h3 className="font-semibold group-hover:text-primary transition">Create Video</h3>
                    <p className="text-sm text-muted-foreground">
                      Generate a new AI video
                    </p>
                  </div>
                </Link>
                <Link href="/live">
                  <div className="p-4 rounded-lg border border-border hover:border-primary/50 hover:bg-primary/5 transition cursor-pointer group">
                    <Play className="w-8 h-8 text-primary mb-3" />
                    <h3 className="font-semibold group-hover:text-primary transition">Go Live</h3>
                    <p className="text-sm text-muted-foreground">
                      Start a live avatar session
                    </p>
                  </div>
                </Link>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Credits</CardTitle>
              <CardDescription>Your usage this month</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="text-center">
                <div className="w-24 h-24 rounded-full bg-neura-500/10 border-4 border-neura-500 flex items-center justify-center mx-auto mb-4">
                  <span className="text-2xl font-bold text-neura-500">
                    {formatCredits(user?.credits || 0)}
                  </span>
                </div>
                <p className="text-sm text-muted-foreground mb-4">
                  Credits remaining
                </p>
                <Link href="/pricing">
                  <Button variant="outline" size="sm" className="w-full">
                    Upgrade Plan
                  </Button>
                </Link>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Recent Videos */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle>Recent Videos</CardTitle>
              <CardDescription>Your latest creations</CardDescription>
            </div>
            <Link href="/videos">
              <Button variant="ghost" size="sm">
                View all
                <ArrowRight className="w-4 h-4 ml-2" />
              </Button>
            </Link>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {recentVideos.map((video) => (
                <div
                  key={video.id}
                  className="flex items-center justify-between p-4 rounded-lg border border-border hover:bg-accent/50 transition"
                >
                  <div className="flex items-center gap-4">
                    <div className="w-16 h-10 rounded bg-muted flex items-center justify-center">
                      <Video className="w-5 h-5 text-muted-foreground" />
                    </div>
                    <div>
                      <h4 className="font-medium">{video.title}</h4>
                      <p className="text-sm text-muted-foreground">
                        {video.duration} • {video.created}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                      video.status === 'completed' 
                        ? 'bg-green-500/10 text-green-500' 
                        : 'bg-yellow-500/10 text-yellow-500'
                    }`}>
                      {video.status}
                    </span>
                    <Button variant="ghost" size="sm">
                      <Play className="w-4 h-4" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </motion.div>
    </div>
  );
}

