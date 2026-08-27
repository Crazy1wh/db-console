interface Envelope<T> { success: boolean; data: T; error: null | { code: string; message: string; details?: unknown } }

export class ApiError extends Error {
  constructor(public code: string, message: string, public status: number, public details?: unknown) {
    super(message)
  }
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  if (options.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
  const response = await fetch(`/api${path}`, { ...options, headers })
  let payload: Envelope<T>
  try {
    payload = await response.json()
  } catch {
    throw new ApiError('INVALID_RESPONSE', `服务器返回了无效响应 (${response.status})`, response.status)
  }
  if (!response.ok || !payload.success) {
    throw new ApiError(payload.error?.code || 'REQUEST_FAILED', payload.error?.message || '请求失败', response.status, payload.error?.details)
  }
  return payload.data
}

export const enc = (value: string) => encodeURIComponent(value)
