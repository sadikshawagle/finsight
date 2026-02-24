"use client";
import { useState, useEffect, useCallback } from "react";
import { fetchJSON } from "@/lib/api";

export function useSignals(plan = "FREE", pollMs = 5 * 60 * 1000) {
  const [signals, setSignals]       = useState([]);
  const [loading, setLoading]       = useState(true);
  const [lastFetched, setLastFetched] = useState(null);
  const [newId, setNewId]           = useState(null);

  const load = useCallback(async () => {
    try {
      const data = await fetchJSON(`/api/signals?plan=${plan}&limit=50`);
      setSignals(prev => {
        // Detect genuinely new signals (not in previous list)
        const prevIds = new Set(prev.map(s => s.id));
        const newest  = data.find(s => !prevIds.has(s.id));
        if (newest) setNewId(newest.id);
        return data;
      });
      setLastFetched(new Date());
    } catch (e) {
      console.error("Failed to fetch signals:", e);
    } finally {
      setLoading(false);
    }
  }, [plan]);

  useEffect(() => {
    load();
    const interval = setInterval(load, pollMs);
    return () => clearInterval(interval);
  }, [load, pollMs]);

  return { signals, loading, lastFetched, newId, refetch: load };
}
