"use client";
import { useState, useEffect, useCallback } from "react";
import { fetchJSON } from "@/lib/api";

export function useChartData(pollMs = 5 * 60 * 1000) {
  const [chartData, setChartData] = useState([]);
  const [loading, setLoading]     = useState(true);

  const load = useCallback(async () => {
    try {
      const data = await fetchJSON("/api/chart-data");
      setChartData(data);
    } catch (e) {
      console.error("Failed to fetch chart data:", e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const interval = setInterval(load, pollMs);
    return () => clearInterval(interval);
  }, [load, pollMs]);

  return { chartData, loading };
}
