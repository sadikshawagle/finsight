const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "https://finsight-vmas.vercel.app";

export async function fetchJSON(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}
