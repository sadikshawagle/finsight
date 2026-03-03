const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "https://finsight-vmas.vercel.app";

function _authHeaders() {
  const token = typeof window !== "undefined" ? localStorage.getItem("fs_token") : null;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function fetchJSON(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json", ..._authHeaders() },
    ...options,
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function postJSON(path, body) {
  return fetchJSON(path, {
    method:  "POST",
    body:    JSON.stringify(body),
  });
}
