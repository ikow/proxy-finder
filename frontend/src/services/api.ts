import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
})

export interface Proxy {
  id: number
  ip: string
  port: number
  protocol: string
  country: string | null
  country_name: string | null
  city: string | null
  anonymity: string | null
  speed: number | null
  score: number
  last_check: string | null
  success_count: number
  fail_count: number
  is_active: boolean
  source: string | null
  created_at: string
  updated_at: string
  address: string
  success_rate: number
}

export interface ProxyListResponse {
  items: Proxy[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface ProxyStats {
  total: number
  active: number
  inactive: number
  by_protocol: Record<string, number>
  by_country: Record<string, number>
  by_anonymity: Record<string, number>
  average_speed: number | null
  average_score: number
}

export interface ProxyFilters {
  page?: number
  page_size?: number
  protocol?: string
  country?: string
  anonymity?: string
  min_score?: number
  is_active?: boolean
  sort_by?: string
  sort_order?: string
}

export interface RefreshResponse {
  message: string
  new_proxies: number
  total_proxies: number
}

export interface ValidationResult {
  proxy_id: number
  is_valid: boolean
  speed: number | null
  anonymity: string | null
  error: string | null
  test_url: string | null
  response_ip: string | null
}

export interface SingleValidationResponse extends ValidationResult {
  proxy: Proxy | null
}

export interface BrowseRequest {
  url: string
  timeout?: number
}

export interface ValidationProgress {
  total: number
  completed: number
  successful: number
  failed: number
  percent: number
  current_proxy?: string
  done: boolean
  error?: string
  latest_result?: {
    proxy_id: number
    is_valid: boolean
    speed: number | null
    error: string | null
  }
}

export interface BrowseResponse {
  success: boolean
  url: string
  status_code: number | null
  content_type: string | null
  content: string | null
  headers: Record<string, string> | null
  elapsed_ms: number | null
  error: string | null
  proxy_address: string
}

export const proxyApi = {
  list: async (filters: ProxyFilters = {}): Promise<ProxyListResponse> => {
    const params = new URLSearchParams()
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        params.append(key, String(value))
      }
    })
    const { data } = await api.get(`/proxies?${params.toString()}`)
    return data
  },

  getById: async (id: number): Promise<Proxy> => {
    const { data } = await api.get(`/proxies/${id}`)
    return data
  },

  getBest: async (limit = 10, protocol?: string, country?: string): Promise<Proxy[]> => {
    const params = new URLSearchParams({ limit: String(limit) })
    if (protocol) params.append('protocol', protocol)
    if (country) params.append('country', country)
    const { data } = await api.get(`/proxies/best?${params.toString()}`)
    return data
  },

  getByCountry: async (countryCode: string, limit = 50, protocol?: string): Promise<Proxy[]> => {
    const params = new URLSearchParams({ limit: String(limit) })
    if (protocol) params.append('protocol', protocol)
    const { data } = await api.get(`/proxies/by-country/${countryCode}?${params.toString()}`)
    return data
  },

  getStats: async (): Promise<ProxyStats> => {
    const { data } = await api.get('/proxies/stats')
    return data
  },

  refresh: async (protocol?: string, country?: string): Promise<RefreshResponse> => {
    const params = new URLSearchParams()
    if (protocol) params.append('protocol', protocol)
    if (country) params.append('country', country)
    const { data } = await api.post(`/proxies/refresh?${params.toString()}`)
    return data
  },

  validate: async (proxyIds?: number[], limit = 0, quick = false): Promise<ValidationResult[]> => {
    const { data } = await api.post('/proxies/validate', {
      proxy_ids: proxyIds,
      validate_all: !proxyIds,
      limit,  // 0 means no limit
      quick,
    })
    return data
  },

  validateStream: (
    onProgress: (progress: ValidationProgress) => void,
    proxyIds?: number[],
    limit = 0,  // 0 means no limit - validate all
    quick = false
  ): { abort: () => void } => {
    const controller = new AbortController()

    // Use fetch with streaming for SSE
    fetch('/api/proxies/validate/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        proxy_ids: proxyIds,
        validate_all: !proxyIds,
        limit,
        quick,
      }),
      signal: controller.signal,
    })
      .then(async (response) => {
        const reader = response.body?.getReader()
        if (!reader) return

        const decoder = new TextDecoder()
        let buffer = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() || ''

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6))
                onProgress(data)
              } catch {
                // Ignore parse errors
              }
            }
          }
        }
      })
      .catch((err) => {
        if (err.name !== 'AbortError') {
          onProgress({ total: 0, completed: 0, successful: 0, failed: 0, percent: 0, done: true, error: err.message })
        }
      })

    return { abort: () => controller.abort() }
  },

  validateSingle: async (proxyId: number): Promise<SingleValidationResponse> => {
    const { data } = await api.post(`/proxies/${proxyId}/validate`)
    return data
  },

  delete: async (id: number): Promise<void> => {
    await api.delete(`/proxies/${id}`)
  },

  deleteInactive: async (): Promise<{ message: string }> => {
    const { data } = await api.delete('/proxies')
    return data
  },

  browse: async (proxyId: number, url: string, timeout = 30): Promise<BrowseResponse> => {
    const { data } = await api.post(`/proxies/${proxyId}/browse`, {
      url,
      timeout,
    })
    return data
  },
}
