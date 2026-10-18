// Every call is relative: Compose's nginx and the Kubernetes Ingress route
// /api to the backend, so the browser never needs the backend's hostname.
export async function api(path, { method = "GET", body } = {}) {
  const res = await fetch(`/api${path}`, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (res.status === 204) return null;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    let msg = data.detail ?? res.statusText;
    if (Array.isArray(msg)) msg = msg.map((d) => `${d.loc?.at(-1)}: ${d.msg}`).join("; ");
    throw new Error(msg);
  }
  return data;
}

export const rupees = (n) => `₹${Number(n || 0).toLocaleString("en-IN")}`;

export function dateLabel(iso) {
  return new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

export function timeAgo(iso) {
  const s = Math.round((Date.now() - new Date(iso)) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return `${Math.floor(s / 86400)} d ago`;
}
