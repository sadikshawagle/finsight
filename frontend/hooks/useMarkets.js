"use client";
import { useState, useEffect, useCallback } from "react";
import { fetchJSON } from "@/lib/api";

export function useMarkets(pollMs = 60 * 1000) {
  const [markets, setMarkets] = useState({ indices: {}, commodities: {}, crypto: {} });
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const data = await fetchJSON("/api/markets/overview");
      setMarkets(data);
    } catch (e) {
      console.error("Failed to fetch markets:", e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const interval = setInterval(load, pollMs);
    return () => clearInterval(interval);
  }, [load, pollMs]);

  // Flatten into the array format the UI expects
  const allMarkets = [
    ...Object.entries(markets.indices).map(([name, d]) => ({
      name, value: d.price?.toLocaleString() ?? "—",
      change: `${d.change_pct >= 0 ? "+" : ""}${d.change_pct?.toFixed(2) ?? "0"}%`,
      up: (d.change_pct ?? 0) >= 0,
    })),
    ...Object.entries(markets.commodities).map(([name, d]) => ({
      name, value: d.price?.toLocaleString() ?? "—",
      change: `${d.change_pct >= 0 ? "+" : ""}${d.change_pct?.toFixed(2) ?? "0"}%`,
      up: (d.change_pct ?? 0) >= 0,
    })),
    ...Object.entries(markets.crypto).map(([name, d]) => ({
      name, value: `$${d.price?.toLocaleString() ?? "—"}`,
      change: `${d.change_pct >= 0 ? "+" : ""}${d.change_pct?.toFixed(2) ?? "0"}%`,
      up: (d.change_pct ?? 0) >= 0,
    })),
  ];

  return { markets, allMarkets, loading };
}
