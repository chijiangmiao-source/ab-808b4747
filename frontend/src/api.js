// Thin client for the FastAPI backend.
// In production the same origin is served by nginx which proxies /api.
const BASE = import.meta.env.VITE_API_BASE ?? "";

async function request(path, options) {
  const res = await fetch(`${BASE}${path}`, options);
  let data = null;
  try {
    data = await res.json();
  } catch {
    /* non-JSON response */
  }
  if (!res.ok) {
    const errors = data?.errors ?? [{
      code: "HTTP_ERROR",
      message: `请求失败：HTTP ${res.status}`,
    }];
    const err = new Error("locate failed");
    err.errors = errors;
    err.status = res.status;
    throw err;
  }
  return data;
}

export function locate(payload) {
  return request("/api/v1/locate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function getLimits() {
  return request("/api/v1/limits");
}

export function getHealth() {
  return request("/health");
}
