import { useState, useEffect, useCallback } from 'react';
import { jobsApi } from '@/lib/api';
import type { Job } from '@/lib/types';

interface UseJobStatusOptions {
  jobId: string | null;
  enabled?: boolean;
  pollInterval?: number;
  onComplete?: (job: Job) => void;
  onError?: (job: Job) => void;
}

export function useJobStatus({
  jobId,
  enabled = true,
  pollInterval = 3000,
  onComplete,
  onError,
}: UseJobStatusOptions) {
  const [job, setJob] = useState<Job | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchJob = useCallback(async () => {
    if (!jobId || !enabled) return;

    try {
      setError(null);
      const jobData = await jobsApi.get(jobId);
      setJob(jobData);

      if (jobData.status === 'completed' && onComplete) {
        onComplete(jobData);
      } else if (jobData.status === 'failed' && onError) {
        onError(jobData);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to fetch job status');
    } finally {
      setLoading(false);
    }
  }, [jobId, enabled, onComplete, onError]);

  useEffect(() => {
    if (!jobId || !enabled) {
      setJob(null);
      setError(null);
      return;
    }

    setLoading(true);
    fetchJob();

    // Poll for status updates if job is still processing
    const interval = setInterval(() => {
      if (job && (job.status === 'processing' || job.status === 'queued')) {
        fetchJob();
      }
    }, pollInterval);

    return () => clearInterval(interval);
  }, [jobId, enabled, pollInterval, fetchJob, job]);

  return {
    job,
    loading,
    error,
    refetch: fetchJob,
    isCompleted: job?.status === 'completed',
    isFailed: job?.status === 'failed',
    isProcessing: job?.status === 'processing' || job?.status === 'queued',
  };
}


