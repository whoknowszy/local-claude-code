const BASE = '/api';

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

export const api = {
  getConfig: (reveal = false) => request(`/config${reveal ? '?reveal=true' : ''}`),
  updateConfig: (config) => request('/config', { method: 'PUT', body: JSON.stringify(config) }),

  getProviders: () => request('/providers'),
  createProvider: (provider) => request('/providers', { method: 'POST', body: JSON.stringify(provider) }),
  updateProvider: (name, provider) => request(`/providers/${encodeURIComponent(name)}`, { method: 'PUT', body: JSON.stringify(provider) }),
  deleteProvider: (name) => request(`/providers/${encodeURIComponent(name)}`, { method: 'DELETE' }),

  getStats: () => request('/stats'),
  getHealth: () => request('/health'),
  getRecentLogs: () => request('/logs/recent'),

  getClaudeEnv: () => request('/config/claude-env'),
  updateClaudeEnv: (env) => request('/config/claude-env', { method: 'PUT', body: JSON.stringify(env) }),
};
