export const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1';

export const ACTOR_ID = import.meta.env.VITE_ACTOR_ID || 'ops-coordinator';
export const ACTOR_NAME = import.meta.env.VITE_ACTOR_NAME || 'Ops Coordinator';

export interface ApiResponse<T> {
  data: T;
  totalCount?: number;
}

export class ApiError extends Error {
  status: number;
  errorType?: string;
  details?: unknown;

  constructor(message: string, status: number, errorType?: string, details?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.errorType = errorType;
    this.details = details;
  }
}

export async function apiFetch<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<ApiResponse<T>> {
  const url = endpoint.startsWith('http') ? endpoint : `${API_BASE}${endpoint.startsWith('/') ? '' : '/'}${endpoint}`;
  
  const headers = new Headers(options.headers || {});
  
  // Set JSON headers if sending a body
  if (options.body && !(options.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  // Set Actor headers for mutations or audit logging
  if (!headers.has('X-Actor-ID')) {
    headers.set('X-Actor-ID', ACTOR_ID);
  }
  if (!headers.has('X-Actor-Name')) {
    headers.set('X-Actor-Name', ACTOR_NAME);
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  const totalCountHeader = response.headers.get('X-Total-Count');
  const totalCount = totalCountHeader ? parseInt(totalCountHeader, 10) : undefined;

  if (!response.ok) {
    let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
    let errorType: string | undefined;
    let details: unknown;

    try {
      const errorJson = await response.json();
      if (errorJson.message) {
        errorMessage = errorJson.message;
      } else if (errorJson.detail) {
        if (typeof errorJson.detail === 'string') {
          errorMessage = errorJson.detail;
        } else if (Array.isArray(errorJson.detail)) {
          errorMessage = errorJson.detail.map((d: { msg?: string }) => d.msg || JSON.stringify(d)).join('; ');
        }
      } else if (errorJson.error) {
        errorMessage = errorJson.error;
      }
      errorType = errorJson.error;
      details = errorJson;
    } catch {
      // If response body is not JSON, fallback to status text
    }

    throw new ApiError(errorMessage, response.status, errorType, details);
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return { data: undefined as unknown as T, totalCount };
  }

  const data = (await response.json()) as T;
  return { data, totalCount };
}
