// TypeScript types matching backend schemas

export type VideoType = 'explainer' | 'training' | 'marketing' | 'presentation' | 'custom';
export type VideoStatus = 'draft' | 'queued' | 'processing' | 'rendering' | 'completed' | 'failed';
export type JobStatus = 'pending' | 'queued' | 'processing' | 'completed' | 'failed' | 'cancelled';
export type JobType = 'video_generation' | 'live_session' | 'tts_generation' | 'avatar_training' | 'voice_cloning';

export interface Video {
  id: string;
  user_id: string;
  avatar_id: string | null;
  title: string;
  description: string | null;
  type: VideoType;
  status: VideoStatus;
  script: string | null;
  prompt: string | null;
  video_url: string | null;
  thumbnail_url: string | null;
  audio_url: string | null;
  duration: number | null;
  resolution: string | null;
  file_size: number | null;
  video_metadata: Record<string, any> | null;
  error_message: string | null;
  credits_used: number;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
}

export interface VideoListResponse {
  videos: Video[];
  total: number;
}

export interface VideoGenerateRequest {
  quality?: 'fast' | 'balanced' | 'high';
  resolution?: '720p' | '1080p' | '4k';
}

export interface VideoGenerateResponse {
  video_id: string;
  job_id: string;
  status: string;
  estimated_time: number;
  credits_estimated: number;
}

export interface User {
  id: string;
  email: string;
  name: string | null;
  plan: string;
  credits: number;
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
  updated_at: string;
}

export interface Avatar {
  id: string;
  user_id: string | null;
  voice_id: string | null;
  name: string;
  description: string | null;
  model_path: string | null;
  thumbnail_url: string | null;
  config: Record<string, any> | null;
  is_default: boolean;
  is_public: boolean;
  is_premium: boolean;
  created_at: string;
  updated_at: string;
}

export interface AvatarListResponse {
  avatars: Avatar[];
  total: number;
}

export interface Voice {
  id: string;
  name: string;
  language: string;
  gender: string;
  is_default: boolean;
  sample_url: string | null;
  created_at: string;
}

export interface VoiceListResponse {
  voices: Voice[];
  total: number;
}

export interface Job {
  id: string;
  user_id: string;
  type: JobType;
  status: JobStatus;
  priority: number;
  progress: number;
  current_step: string | null;
  input_data: Record<string, any> | null;
  result: Record<string, any> | null;
  error: string | null;
  credits_estimated: number;
  credits_used: number;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface JobListResponse {
  jobs: Job[];
  total: number;
}

export interface CreditsHistory {
  id: string;
  amount: number;
  action: string;
  description: string | null;
  balance_after: number;
  created_at: string;
}

export interface CreditsHistoryListResponse {
  history: CreditsHistory[];
  total: number;
  current_balance: number;
}

export interface LiveSession {
  session_id: string;
  avatar_id: string | null;
  websocket_url: string;
  status: string;
  credits_per_minute: number;
}

export interface ScriptGenerateResponse {
  script: string;
  estimated_duration: number;
}

export interface ChatResponse {
  message: string;
  usage: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
}


