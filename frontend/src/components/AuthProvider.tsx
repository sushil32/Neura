'use client';

import { useAuth } from '@/lib/auth';
import { useEffect } from 'react';

export function AuthProvider({ children }: { children: React.ReactNode }) {
    const fetchUser = useAuth((state) => state.fetchUser);

    useEffect(() => {
        fetchUser();
    }, [fetchUser]);

    return <>{children}</>;
}
