"use client";
import { useState, useEffect, useCallback } from "react";
import { fetchJSON, postJSON } from "@/lib/api";

export function usePortfolio() {
  const [holdings, setHoldings] = useState([]);
  const [summary,  setSummary]  = useState(null);
  const [loading,  setLoading]  = useState(false);
  const [error,    setError]    = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchJSON("/api/portfolio");
      setHoldings(data.holdings || []);
      setSummary(data.summary   || null);
    } catch (e) {
      // 401 = not logged in — silently keep empty state
      if (!e?.message?.includes("401")) {
        setError(e?.message || "Failed to load portfolio.");
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const addHolding = useCallback(async (ticker, quantity, avg_buy_price, currency = "USD") => {
    await postJSON("/api/portfolio", { ticker, quantity, avg_buy_price, currency });
    await load();
  }, [load]);

  const removeHolding = useCallback(async (id) => {
    const BASE = process.env.NEXT_PUBLIC_API_URL || "https://finsight-vmas.vercel.app";
    const token = typeof window !== "undefined" ? localStorage.getItem("fs_token") : null;
    const headers = token ? { Authorization: `Bearer ${token}` } : {};
    await fetch(`${BASE}/api/portfolio/${id}`, { method: "DELETE", headers });
    await load();
  }, [load]);

  return { holdings, summary, loading, error, addHolding, removeHolding, refetch: load };
}
