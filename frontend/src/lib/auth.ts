import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { authApi, userApi } from './api';

interface User {
  id: string;
  email: string;
  name: string | null;
  plan: string;
  credits: number;
  is_verified: boolean;
}

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;

  // Actions
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, name?: string) => Promise<void>;
  logout: () => Promise<void>;
  fetchUser: () => Promise<void>;
  updateUser: (data: Partial<User>) => void;
  clearError: () => void;
}

export const useAuth = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      isAuthenticated: false,
      isLoading: true,
      error: null,

      login: async (email: string, password: string) => {
        set({ isLoading: true, error: null });
        try {
          const response = await authApi.login({ email, password });

          // Store tokens
          localStorage.setItem('access_token', response.access_token);
          localStorage.setItem('refresh_token', response.refresh_token);

          // Fetch full user profile
          const user = await userApi.getProfile();

          set({
            user,
            isAuthenticated: true,
            isLoading: false,
          });
        } catch (error: any) {
          set({
            error: error.response?.data?.detail || 'Login failed',
            isLoading: false,
          });
          throw error;
        }
      },

      register: async (email: string, password: string, name?: string) => {
        set({ isLoading: true, error: null });
        try {
          const response = await authApi.register({ email, password, name });

          // Store tokens
          localStorage.setItem('access_token', response.access_token);
          localStorage.setItem('refresh_token', response.refresh_token);

          // Fetch full user profile
          const user = await userApi.getProfile();

          set({
            user,
            isAuthenticated: true,
            isLoading: false,
          });
        } catch (error: any) {
          set({
            error: error.response?.data?.detail || 'Registration failed',
            isLoading: false,
          });
          throw error;
        }
      },

      logout: async () => {
        try {
          await authApi.logout();
        } catch (error) {
          // Continue with logout even if API call fails
        }
        set({
          user: null,
          isAuthenticated: false,
        });
      },

      fetchUser: async () => {
        const token = localStorage.getItem('access_token');
        if (!token) {
          set({ isAuthenticated: false, user: null, isLoading: false });
          return;
        }

        set({ isLoading: true });
        try {
          const user = await userApi.getProfile();
          set({
            user,
            isAuthenticated: true,
            isLoading: false,
          });
        } catch (error: any) {
          // Only logout on 401 (Unauthorized)
          if (error.response?.status === 401) {
            set({
              user: null,
              isAuthenticated: false,
              isLoading: false,
            });
          } else {
            // For other errors (network, 500, etc), just stop loading
            // Keep the previous user state (optimistic) or maybe don't update anything?
            // If we keep user as null, usage of user object might crash if we don't handle it.
            // But we shouldn't force logout.
            console.error('Fetch user failed:', error);
            set({ isLoading: false });
          }
        }
      },

      updateUser: (data: Partial<User>) => {
        const currentUser = get().user;
        if (currentUser) {
          set({ user: { ...currentUser, ...data } });
        }
      },

      clearError: () => set({ error: null }),
    }),
    {
      name: 'neura-auth',
      partialize: (state) => ({
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
);

