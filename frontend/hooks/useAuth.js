"use client";
import { useState, useEffect, useCallback } from "react";

const TOKEN_KEY = "fs_token";

function _decodeJwt(token) {
  try {
    const base64 = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    return JSON.parse(atob(base64));
  } catch {
    return null;
  }
}

function _isExpired(isoString) {
  if (!isoString) return false;
  return new Date(isoString) < new Date();
}

export function useAuth() {
  const [user, setUser]   = useState(null);
  const [token, setToken] = useState(null);

  // Load from localStorage on mount
  useEffect(() => {
    const stored = localStorage.getItem(TOKEN_KEY);
    if (!stored) return;
    const payload = _decodeJwt(stored);
    if (!payload) { localStorage.removeItem(TOKEN_KEY); return; }
    // Check JWT exp
    if (payload.exp && payload.exp * 1000 < Date.now()) {
      localStorage.removeItem(TOKEN_KEY);
      return;
    }
    setToken(stored);
    setUser(payload);
  }, []);

  const saveToken = useCallback((newToken) => {
    const payload = _decodeJwt(newToken);
    if (!payload) return;
    localStorage.setItem(TOKEN_KEY, newToken);
    setToken(newToken);
    setUser(payload);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setUser(null);
  }, []);

  const isLoggedIn = !!user;

  // Trial active: trial_ends_at exists and is in the future
  const trialActive = user?.trial_ends_at && !_isExpired(user.trial_ends_at);

  // Paid access: access_expires_at exists and is in the future
  const paidActive = user?.access_expires_at && !_isExpired(user.access_expires_at);

  // Full access: admin OR on trial OR paid
  const hasAccess = !!(user?.is_admin || trialActive || paidActive);

  // Days left in trial (0 if expired or no trial)
  const trialDaysLeft = (() => {
    if (!user?.trial_ends_at) return 0;
    const ms   = new Date(user.trial_ends_at) - new Date();
    return Math.max(0, Math.ceil(ms / (1000 * 60 * 60 * 24)));
  })();

  return {
    user,
    token,
    isLoggedIn,
    hasAccess,
    trialActive,
    trialDaysLeft,
    saveToken,
    logout,
  };
}
