import axios from 'axios'

let _baseUrl = 'http://127.0.0.1:8000'

export function setApiBaseUrl(url: string) {
  _baseUrl = url.replace(/\/$/, '')
}

export function getApiBaseUrl(): string {
  return _baseUrl
}

export function apiUrl(path: string): string {
  const p = path.startsWith('/') ? path : `/${path}`
  return `${_baseUrl}${p}`
}

export function getErrMsg(err: any, fallback = '未知错误'): string {
  if (typeof err === 'string') return err
  try {
    return err?.response?.data?.detail ||
      err?.response?.data?.message ||
      err?.response?.data?.error ||
      err?.message ||
      err?.toString?.() ||
      fallback
  } catch {
    return fallback
  }
}

export async function scanPorts(baseUrl: string, start = 8000, end = 8010): Promise<string | null> {
  const base = baseUrl.replace(/\/$/, '').replace(/:\d+/, '')
  for (let port = start; port <= end; port++) {
    try {
      await axios.get(`${base}:${port}/`, { timeout: 500 })
      return `${base}:${port}`
    } catch { /* continue */ }
  }
  return null
}
