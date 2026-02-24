"use client";
import { useState, useEffect, useCallback } from "react";
import { fetchJSON } from "@/lib/api";

export function useWatchlist() {
  const [watchlist, setWatchlist] = useState([]);
  const [loading, setLoading]     = useState(true);

  const load = useCallback(async () => {
    try {
      const data = await fetchJSON("/api/watchlist");
      setWatchlist(data);
    } catch (e) {
      console.error("Failed to fetch watchlist:", e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const addTicker = async (ticker, name) => {
    try {
      await fetchJSON("/api/watchlist", {
        method: "POST",
        body: JSON.stringify({ ticker, name }),
      });
      await load();
    } catch (e) {
      console.error("Failed to add ticker:", e);
    }
  };

  const removeTicker = async (ticker) => {
    try {
      await fetchJSON(`/api/watchlist/${ticker}`, { method: "DELETE" });
      await load();
    } catch (e) {
      console.error("Failed to remove ticker:", e);
    }
  };

  return { watchlist, loading, addTicker, removeTicker, refetch: load };
}
