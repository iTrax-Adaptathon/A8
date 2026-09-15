import { useCallback, useEffect, useState } from 'react';
import { getCapacity } from '../api/endpoints';
import { CapacityMetrics } from '../api/types';
import { useWebSocketEvent } from '../api/websocket';

export function useCapacity() {
  const [capacity, setCapacity] = useState<CapacityMetrics | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchCapacity = useCallback(async () => {
    try {
      const data = await getCapacity();
      setCapacity(data);
      setError(null);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError(String(err));
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCapacity();
  }, [fetchCapacity]);

  // Refresh capacity metrics when any operational state change happens
  useWebSocketEvent('*', () => {
    fetchCapacity();
  });

  return { capacity, loading, error, refetch: fetchCapacity };
}
