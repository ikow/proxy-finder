import { Copy, CheckCircle, Trash2, Play, Loader2, AlertCircle, Globe } from 'lucide-react'
import { useState } from 'react'
import { Proxy, ValidationResult } from '../services/api'

interface ProxyTableProps {
  proxies: Proxy[]
  onDelete?: (id: number) => void
  onValidate?: (id: number) => Promise<ValidationResult>
  onBrowse?: (id: number) => void
  isLoading?: boolean
}

// Track validation state per proxy
type ValidationState = 'idle' | 'validating' | 'success' | 'failed'

interface ValidationStatus {
  state: ValidationState
  result?: ValidationResult
}

function formatSpeed(speed: number | null): string {
  if (speed === null) return '-'
  if (speed < 1000) return `${Math.round(speed)}ms`
  return `${(speed / 1000).toFixed(1)}s`
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return 'Never'
  const date = new Date(dateStr)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)

  if (diffMins < 1) return 'Just now'
  if (diffMins < 60) return `${diffMins}m ago`
  const diffHours = Math.floor(diffMins / 60)
  if (diffHours < 24) return `${diffHours}h ago`
  const diffDays = Math.floor(diffHours / 24)
  return `${diffDays}d ago`
}

function getScoreColor(score: number): string {
  if (score >= 70) return 'text-green-600'
  if (score >= 40) return 'text-yellow-600'
  return 'text-red-600'
}

function getSpeedColor(speed: number | null): string {
  if (speed === null) return 'text-gray-400'
  if (speed < 500) return 'text-green-600'
  if (speed < 1000) return 'text-blue-600'
  if (speed < 2000) return 'text-yellow-600'
  return 'text-red-600'
}

function getAnonymityBadge(anonymity: string | null): { color: string; text: string } {
  switch (anonymity) {
    case 'elite':
      return { color: 'bg-green-100 text-green-800', text: 'Elite' }
    case 'anonymous':
      return { color: 'bg-blue-100 text-blue-800', text: 'Anonymous' }
    case 'transparent':
      return { color: 'bg-yellow-100 text-yellow-800', text: 'Transparent' }
    default:
      return { color: 'bg-gray-100 text-gray-800', text: 'Unknown' }
  }
}

function getProtocolBadge(protocol: string): { color: string } {
  switch (protocol) {
    case 'socks5':
      return { color: 'bg-purple-100 text-purple-800' }
    case 'socks4':
      return { color: 'bg-indigo-100 text-indigo-800' }
    case 'https':
      return { color: 'bg-green-100 text-green-800' }
    default:
      return { color: 'bg-blue-100 text-blue-800' }
  }
}

export function ProxyTable({ proxies, onDelete, onValidate, onBrowse, isLoading }: ProxyTableProps) {
  const [copiedId, setCopiedId] = useState<number | null>(null)
  const [validationStatus, setValidationStatus] = useState<Record<number, ValidationStatus>>({})

  const copyToClipboard = async (proxy: Proxy) => {
    try {
      await navigator.clipboard.writeText(proxy.address)
      setCopiedId(proxy.id)
      setTimeout(() => setCopiedId(null), 2000)
    } catch (err) {
      console.error('Failed to copy:', err)
    }
  }

  const handleValidate = async (proxy: Proxy) => {
    if (!onValidate) return

    setValidationStatus((prev) => ({
      ...prev,
      [proxy.id]: { state: 'validating' },
    }))

    try {
      const result = await onValidate(proxy.id)
      setValidationStatus((prev) => ({
        ...prev,
        [proxy.id]: {
          state: result.is_valid ? 'success' : 'failed',
          result,
        },
      }))

      // Clear status after 10 seconds
      setTimeout(() => {
        setValidationStatus((prev) => {
          const newStatus = { ...prev }
          delete newStatus[proxy.id]
          return newStatus
        })
      }, 10000)
    } catch (err) {
      setValidationStatus((prev) => ({
        ...prev,
        [proxy.id]: {
          state: 'failed',
          result: {
            proxy_id: proxy.id,
            is_valid: false,
            speed: null,
            anonymity: null,
            error: 'Validation request failed',
            test_url: null,
            response_ip: null,
          },
        },
      }))
    }
  }

  const renderValidationButton = (proxy: Proxy) => {
    const status = validationStatus[proxy.id]

    if (status?.state === 'validating') {
      return (
        <button className="p-1 rounded" disabled title="Validating...">
          <Loader2 className="h-4 w-4 text-blue-500 animate-spin" />
        </button>
      )
    }

    if (status?.state === 'success') {
      return (
        <button
          className="p-1 rounded"
          title={`Valid - ${status.result?.speed}ms via ${status.result?.test_url?.split('/')[2] || 'unknown'}`}
        >
          <CheckCircle className="h-4 w-4 text-green-600" />
        </button>
      )
    }

    if (status?.state === 'failed') {
      return (
        <button
          className="p-1 rounded"
          title={`Failed: ${status.result?.error || 'Unknown error'}`}
        >
          <AlertCircle className="h-4 w-4 text-red-500" />
        </button>
      )
    }

    return (
      <button
        onClick={() => handleValidate(proxy)}
        className="p-1 hover:bg-blue-50 rounded"
        title="Test this proxy"
      >
        <Play className="h-4 w-4 text-blue-500" />
      </button>
    )
  }

  if (isLoading) {
    return (
      <div className="bg-white rounded-lg border p-8 text-center">
        <div className="animate-spin h-8 w-8 border-4 border-blue-500 border-t-transparent rounded-full mx-auto"></div>
        <p className="mt-4 text-gray-500">Loading proxies...</p>
      </div>
    )
  }

  if (proxies.length === 0) {
    return (
      <div className="bg-white rounded-lg border p-8 text-center">
        <p className="text-gray-500">No proxies found. Click "Refresh" to fetch proxies.</p>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-lg border overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-600">Address</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-600">Protocol</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-600">Country</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-600">Anonymity</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-600">Speed</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-600">Score</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-600">Success Rate</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-600">Last Check</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-600">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {proxies.map((proxy) => {
              const anonymityBadge = getAnonymityBadge(proxy.anonymity)
              const protocolBadge = getProtocolBadge(proxy.protocol)
              const status = validationStatus[proxy.id]

              // Highlight row based on validation status
              let rowClass = 'hover:bg-gray-50'
              if (status?.state === 'success') {
                rowClass = 'bg-green-50 hover:bg-green-100'
              } else if (status?.state === 'failed') {
                rowClass = 'bg-red-50 hover:bg-red-100'
              } else if (status?.state === 'validating') {
                rowClass = 'bg-blue-50'
              }

              return (
                <tr key={proxy.id} className={rowClass}>
                  <td className="px-4 py-3">
                    <code className="text-sm bg-gray-100 px-2 py-1 rounded font-mono">
                      {proxy.address}
                    </code>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`text-xs px-2 py-1 rounded font-medium uppercase ${protocolBadge.color}`}>
                      {proxy.protocol}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-sm">
                      {proxy.country || '-'}
                      {proxy.country_name && (
                        <span className="text-gray-400 ml-1 text-xs">({proxy.country_name})</span>
                      )}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`text-xs px-2 py-1 rounded ${anonymityBadge.color}`}>
                      {anonymityBadge.text}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`text-sm font-medium ${getSpeedColor(proxy.speed)}`}>
                      {formatSpeed(proxy.speed)}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`text-sm font-bold ${getScoreColor(proxy.score)}`}>
                      {proxy.score.toFixed(1)}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <div className="w-16 bg-gray-200 rounded-full h-2">
                        <div
                          className={`h-2 rounded-full ${
                            proxy.success_rate >= 70
                              ? 'bg-green-500'
                              : proxy.success_rate >= 40
                              ? 'bg-yellow-500'
                              : 'bg-red-500'
                          }`}
                          style={{ width: `${Math.min(100, proxy.success_rate)}%` }}
                        ></div>
                      </div>
                      <span className="text-xs text-gray-500">
                        {proxy.success_rate.toFixed(0)}%
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-sm text-gray-500">{formatDate(proxy.last_check)}</span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1">
                      {onValidate && renderValidationButton(proxy)}
                      {onBrowse && (
                        <button
                          onClick={() => onBrowse(proxy.id)}
                          className="p-1 hover:bg-purple-50 rounded"
                          title="Browse with this proxy"
                        >
                          <Globe className="h-4 w-4 text-purple-500" />
                        </button>
                      )}
                      <button
                        onClick={() => copyToClipboard(proxy)}
                        className="p-1 hover:bg-gray-100 rounded"
                        title="Copy address"
                      >
                        {copiedId === proxy.id ? (
                          <CheckCircle className="h-4 w-4 text-green-600" />
                        ) : (
                          <Copy className="h-4 w-4 text-gray-400" />
                        )}
                      </button>
                      {onDelete && (
                        <button
                          onClick={() => onDelete(proxy.id)}
                          className="p-1 hover:bg-red-50 rounded"
                          title="Delete proxy"
                        >
                          <Trash2 className="h-4 w-4 text-red-400" />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Validation Legend */}
      <div className="px-4 py-2 bg-gray-50 border-t text-xs text-gray-500 flex items-center gap-4 flex-wrap">
        <span className="flex items-center gap-1">
          <Play className="h-3 w-3 text-blue-500" /> Test proxy
        </span>
        <span className="flex items-center gap-1">
          <Globe className="h-3 w-3 text-purple-500" /> Browse with proxy
        </span>
        <span className="flex items-center gap-1">
          <Loader2 className="h-3 w-3 text-blue-500" /> Testing...
        </span>
        <span className="flex items-center gap-1">
          <CheckCircle className="h-3 w-3 text-green-600" /> Working
        </span>
        <span className="flex items-center gap-1">
          <AlertCircle className="h-3 w-3 text-red-500" /> Failed
        </span>
      </div>
    </div>
  )
}
