import axios, { AxiosError, AxiosInstance } from 'axios';
import type {
  Video,
  VideoListResponse,
  VideoGenerateRequest,
  VideoGenerateResponse,
  User,
  Avatar,
  AvatarListResponse,
  Voice,
  VoiceListResponse,
  Job,
  JobListResponse,
  CreditsHistoryListResponse,
  LiveSession,
  ScriptGenerateResponse,
  ChatResponse,
} from './types';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Create axios instance
const api: AxiosInstance = axios.create({
  baseURL: `${API_URL}/api/v1`,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to add auth token
api.interceptors.request.use((config) => {
  const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor for token refresh
api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as any;

    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      try {
        const refreshToken = localStorage.getItem('refresh_token');
        if (refreshToken) {
          const response = await axios.post(`${API_URL}/api/v1/auth/refresh`, {
            refresh_token: refreshToken,
          });

          const { access_token } = response.data;
          localStorage.setItem('access_token', access_token);

          originalRequest.headers.Authorization = `Bearer ${access_token}`;
          return api(originalRequest);
        }
      } catch (refreshError) {
        // Clear tokens and redirect to login
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        window.location.href = '/login';
      }
    }

    return Promise.reject(error);
  }
);

// Auth API
export const authApi = {
  register: async (data: { email: string; password: string; name?: string }) => {
    const response = await api.post('/auth/register', data);
    return response.data;
  },

  login: async (data: { email: string; password: string }) => {
    const response = await api.post('/auth/login', data);
    return response.data;
  },

  logout: async () => {
    const refreshToken = localStorage.getItem('refresh_token');
    if (refreshToken) {
      await api.post('/auth/logout', { refresh_token: refreshToken });
    }
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
  },

  refresh: async (refreshToken: string) => {
    const response = await api.post('/auth/refresh', { refresh_token: refreshToken });
    return response.data;
  },
};

// User API
export const userApi = {
  getProfile: async (): Promise<User> => {
    const response = await api.get('/users/me');
    return response.data;
  },

  updateProfile: async (data: { name?: string; email?: string }): Promise<User> => {
    const response = await api.patch('/users/me', data);
    return response.data;
  },

  changePassword: async (data: { current_password: string; new_password: string }): Promise<void> => {
    await api.post('/users/me/password', data);
  },

  deleteAccount: async (): Promise<void> => {
    await api.delete('/users/me');
  },

  getCreditsHistory: async (limit = 50, offset = 0): Promise<CreditsHistoryListResponse> => {
    const response = await api.get('/users/me/credits', { params: { limit, offset } });
    return response.data;
  },
};

// Videos API
export const videosApi = {
  list: async (params?: { status?: string; type?: string; limit?: number; offset?: number }): Promise<VideoListResponse> => {
    const response = await api.get('/videos', { params });
    // Backend returns a list directly, wrap it for consistency
    const videos = Array.isArray(response.data) ? response.data : [];
    return {
      videos,
      total: videos.length,
    };
  },

  get: async (id: string): Promise<Video> => {
    const response = await api.get(`/videos/${id}`);
    return response.data;
  },

  create: async (data: {
    title: string;
    description?: string;
    type?: string;
    script?: string;
    prompt?: string;
    avatar_id?: string;
  }): Promise<Video> => {
    const response = await api.post('/videos', data);
    return response.data;
  },

  update: async (id: string, data: Partial<{
    title: string;
    description: string;
    script: string;
    prompt: string;
    avatar_id: string;
  }>): Promise<Video> => {
    const response = await api.patch(`/videos/${id}`, data);
    return response.data;
  },

  delete: async (id: string): Promise<void> => {
    await api.delete(`/videos/${id}`);
  },

  generate: async (id: string, data: VideoGenerateRequest): Promise<VideoGenerateResponse> => {
    // Remove video_id from body - it's in the URL path
    const response = await api.post(`/videos/${id}/generate`, data);
    return response.data;
  },
};

// Avatars API
export const avatarsApi = {
  list: async (params?: { include_public?: boolean; limit?: number; offset?: number }): Promise<AvatarListResponse> => {
    const response = await api.get('/avatars', { params });
    return response.data;
  },

  get: async (id: string): Promise<Avatar> => {
    const response = await api.get(`/avatars/${id}`);
    return response.data;
  },

  create: async (data: {
    name: string;
    description?: string;
    voice_id?: string;
    config?: object;
    is_default?: boolean;
  }): Promise<Avatar> => {
    const response = await api.post('/avatars', data);
    return response.data;
  },

  update: async (id: string, data: Partial<{
    name: string;
    description: string;
    voice_id: string;
    config: object;
    is_default: boolean;
  }>): Promise<Avatar> => {
    const response = await api.patch(`/avatars/${id}`, data);
    return response.data;
  },

  delete: async (id: string): Promise<void> => {
    await api.delete(`/avatars/${id}`);
  },

  uploadThumbnail: async (id: string, file: File): Promise<Avatar> => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post(`/avatars/${id}/thumbnail`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },
};

// Jobs API
export const jobsApi = {
  list: async (params?: { status?: string; type?: string; limit?: number; offset?: number }): Promise<JobListResponse> => {
    const response = await api.get('/jobs', { params });
    return response.data;
  },

  get: async (id: string): Promise<Job> => {
    const response = await api.get(`/jobs/${id}`);
    return response.data;
  },

  cancel: async (id: string): Promise<Job> => {
    const response = await api.post(`/jobs/${id}/cancel`);
    return response.data;
  },

  delete: async (id: string): Promise<void> => {
    await api.delete(`/jobs/${id}`);
  },
};

// LLM API
export const llmApi = {
  chat: async (data: {
    messages: Array<{ role: string; content: string }>;
    temperature?: number;
    max_tokens?: number;
  }): Promise<ChatResponse> => {
    const response = await api.post('/llm/chat', data);
    return response.data;
  },

  generateScript: async (data: {
    topic: string;
    type?: string;
    duration?: number;
    tone?: string;
  }): Promise<ScriptGenerateResponse> => {
    const response = await api.post('/llm/script/generate', data);
    return response.data;
  },
};

// Live API
export const liveApi = {
  startSession: async (data: { avatar_id?: string }): Promise<LiveSession> => {
    const response = await api.post('/live/start', data);
    return response.data;
  },

  stopSession: async (sessionId: string): Promise<void> => {
    await api.post(`/live/${sessionId}/stop`);
  },

  getStatus: async (sessionId: string): Promise<any> => {
    const response = await api.get(`/live/${sessionId}/status`);
    return response.data;
  },
};

// TTS/Voices API
export const ttsApi = {
  listVoices: async (params?: { limit?: number; offset?: number }): Promise<VoiceListResponse> => {
    const response = await api.get('/tts/voices', { params });
    return response.data;
  },

  getVoice: async (id: string): Promise<Voice> => {
    const response = await api.get(`/tts/voices/${id}`);
    return response.data;
  },

  createVoice: async (data: {
    name: string;
    language?: string;
    gender?: string;
    sample_file?: File;
  }): Promise<Voice> => {
    const formData = new FormData();
    formData.append('name', data.name);
    if (data.language) formData.append('language', data.language);
    if (data.gender) formData.append('gender', data.gender);
    if (data.sample_file) formData.append('sample_file', data.sample_file);

    const response = await api.post('/tts/voices', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  deleteVoice: async (id: string): Promise<void> => {
    await api.delete(`/tts/voices/${id}`);
  },

  previewVoice: async (id: string): Promise<string> => {
    // Fetch audio blob with proper auth header
    const response = await api.get(`/tts/voices/${id}/preview`, {
      responseType: 'blob',
    });
    const blob = new Blob([response.data], { type: 'audio/wav' });
    return URL.createObjectURL(blob);
  },
};

export default api;

