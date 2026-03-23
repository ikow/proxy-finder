import { useState, useEffect, useMemo } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  ArrowLeft,
  Globe,
  Loader2,
  AlertCircle,
  CheckCircle,
  Clock,
  FileText,
  ExternalLink,
  Code,
  Eye,
  Maximize2,
  X
} from 'lucide-react'
import { proxyApi, BrowseResponse } from '../services/api'

export function ProxyBrowser() {
  const [searchParams] = useSearchParams()
  const proxyId = searchParams.get('proxy')

  const [url, setUrl] = useState('http://httpbin.org/ip')
  const [timeout, setTimeout] = useState(30)
  const [browseResult, setBrowseResult] = useState<BrowseResponse | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [viewMode, setViewMode] = useState<'rendered' | 'source'>('rendered')
  const [isFullscreen, setIsFullscreen] = useState(false)

  // Fetch proxy details (for initial selection)
  useQuery({
    queryKey: ['proxy', proxyId],
    queryFn: () => proxyApi.getById(Number(proxyId)),
    enabled: !!proxyId,
  })

  // Fetch all proxies for dropdown
  const { data: proxies } = useQuery({
    queryKey: ['proxies-for-browser'],
    queryFn: () => proxyApi.list({ page_size: 200, is_active: true, sort_by: 'score', sort_order: 'desc' }),
  })

  const [selectedProxyId, setSelectedProxyId] = useState<number | null>(
    proxyId ? Number(proxyId) : null
  )

  useEffect(() => {
    if (proxyId) {
      setSelectedProxyId(Number(proxyId))
    }
  }, [proxyId])

  const handleBrowse = async () => {
    if (!selectedProxyId || !url) return

    setIsLoading(true)
    setError(null)
    setBrowseResult(null)

    try {
      const result = await proxyApi.browse(selectedProxyId, url, timeout)
      setBrowseResult(result)
    } catch (err) {
      setError('Failed to send request')
    } finally {
      setIsLoading(false)
    }
  }

  const selectedProxy = proxies?.items.find(p => p.id === selectedProxyId)

  // Process HTML content to add base tag for relative URLs
  const processedHtmlContent = useMemo(() => {
    if (!browseResult?.content || !browseResult.content_type?.includes('text/html')) {
      return null
    }

    let html = browseResult.content

    // Extract base URL from the response URL
    try {
      const urlObj = new URL(browseResult.url)
      const baseUrl = `${urlObj.protocol}//${urlObj.host}`

      // Check if there's already a base tag
      if (!/<base\s/i.test(html)) {
        // Add base tag after <head> or at the beginning
        if (/<head[^>]*>/i.test(html)) {
          html = html.replace(/<head[^>]*>/i, `$&<base href="${baseUrl}/" target="_blank">`)
        } else if (/<html[^>]*>/i.test(html)) {
          html = html.replace(/<html[^>]*>/i, `$&<head><base href="${baseUrl}/" target="_blank"></head>`)
        } else {
          html = `<base href="${baseUrl}/" target="_blank">${html}`
        }
      }

      // Add some basic styles to make content more readable in iframe
      const styleTag = `
        <style>
          body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.5;
            padding: 16px;
            max-width: 100%;
            overflow-x: auto;
          }
          img { max-width: 100%; height: auto; }
          pre { overflow-x: auto; }
        </style>
      `
      if (/<head[^>]*>/i.test(html)) {
        html = html.replace(/<\/head>/i, `${styleTag}</head>`)
      } else {
        html = styleTag + html
      }
    } catch (e) {
      // URL parsing failed, return original
    }

    return html
  }, [browseResult])

  const isHtmlContent = browseResult?.content_type?.includes('text/html')
  const isJsonContent = browseResult?.content_type?.includes('application/json')

  // Format JSON content
  const formattedContent = useMemo(() => {
    if (!browseResult?.content) return ''
    if (isJsonContent) {
      try {
        return JSON.stringify(JSON.parse(browseResult.content), null, 2)
      } catch {
        return browseResult.content
      }
    }
    return browseResult.content
  }, [browseResult, isJsonContent])

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Fullscreen Modal */}
      {isFullscreen && browseResult?.content && (
        <div className="fixed inset-0 bg-black bg-opacity-75 z-50 flex flex-col">
          <div className="bg-white p-2 flex items-center justify-between">
            <span className="text-sm font-medium px-2">{browseResult.url}</span>
            <button
              onClick={() => setIsFullscreen(false)}
              className="p-2 hover:bg-gray-100 rounded"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
          <div className="flex-1 bg-white">
            {isHtmlContent && processedHtmlContent ? (
              <iframe
                srcDoc={processedHtmlContent}
                className="w-full h-full border-0"
                sandbox="allow-same-origin allow-scripts allow-popups allow-forms"
                title="Fullscreen preview"
              />
            ) : (
              <pre className="p-4 h-full overflow-auto font-mono text-sm whitespace-pre-wrap">
                {formattedContent}
              </pre>
            )}
          </div>
        </div>
      )}

      <header className="bg-white border-b">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center gap-4">
            <Link
              to="/"
              className="flex items-center gap-2 text-gray-600 hover:text-gray-900"
            >
              <ArrowLeft className="h-5 w-5" />
              Back
            </Link>
            <h1 className="text-2xl font-bold text-gray-900">Proxy Browser</h1>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6">
        {/* Input Section */}
        <div className="bg-white rounded-lg border p-6 mb-6">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {/* Proxy Selector */}
            <div className="md:col-span-1">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Select Proxy
              </label>
              <select
                value={selectedProxyId || ''}
                onChange={(e) => setSelectedProxyId(Number(e.target.value) || null)}
                className="w-full border rounded-lg px-3 py-2 text-sm"
              >
                <option value="">Choose a proxy...</option>
                {proxies?.items.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.protocol.toUpperCase()} | {p.address} | {p.country || 'Unknown'} | Score: {p.score.toFixed(0)}
                  </option>
                ))}
              </select>
              {selectedProxy && (
                <div className="mt-2 text-xs text-gray-500">
                  <span className={`inline-block px-2 py-0.5 rounded mr-2 ${
                    selectedProxy.protocol === 'socks5' ? 'bg-purple-100 text-purple-800' :
                    selectedProxy.protocol === 'socks4' ? 'bg-indigo-100 text-indigo-800' :
                    selectedProxy.protocol === 'https' ? 'bg-green-100 text-green-800' :
                    'bg-blue-100 text-blue-800'
                  }`}>
                    {selectedProxy.protocol.toUpperCase()}
                  </span>
                  {selectedProxy.speed && `${selectedProxy.speed.toFixed(0)}ms`}
                  {selectedProxy.anonymity && ` | ${selectedProxy.anonymity}`}
                </div>
              )}
            </div>

            {/* URL Input */}
            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                URL to Browse
              </label>
              <input
                type="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleBrowse()}
                placeholder="https://example.com"
                className="w-full border rounded-lg px-3 py-2 text-sm"
              />
              <div className="mt-2 flex gap-2 flex-wrap">
                <button
                  onClick={() => setUrl('http://httpbin.org/ip')}
                  className="text-xs px-2 py-1 bg-green-100 text-green-700 rounded hover:bg-green-200"
                >
                  httpbin.org/ip (HTTP)
                </button>
                <button
                  onClick={() => setUrl('http://ip-api.com/json')}
                  className="text-xs px-2 py-1 bg-green-100 text-green-700 rounded hover:bg-green-200"
                >
                  ip-api.com (HTTP)
                </button>
                <button
                  onClick={() => setUrl('http://example.com')}
                  className="text-xs px-2 py-1 bg-green-100 text-green-700 rounded hover:bg-green-200"
                >
                  example.com (HTTP)
                </button>
                <button
                  onClick={() => setUrl('http://neverssl.com')}
                  className="text-xs px-2 py-1 bg-green-100 text-green-700 rounded hover:bg-green-200"
                >
                  neverssl.com (HTTP)
                </button>
                <button
                  onClick={() => setUrl('https://api.ipify.org?format=json')}
                  className="text-xs px-2 py-1 bg-yellow-100 text-yellow-700 rounded hover:bg-yellow-200"
                >
                  ipify.org (HTTPS)
                </button>
              </div>
              {selectedProxy?.protocol === 'http' && url.startsWith('https://') && (
                <div className="mt-2 text-xs text-yellow-600 bg-yellow-50 px-2 py-1 rounded">
                  Note: HTTP proxies may not support HTTPS URLs. Try using HTTP URLs or a SOCKS proxy.
                </div>
              )}
            </div>

            {/* Timeout & Go Button */}
            <div className="md:col-span-1">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Timeout (seconds)
              </label>
              <div className="flex gap-2">
                <input
                  type="number"
                  value={timeout}
                  onChange={(e) => setTimeout(Number(e.target.value))}
                  min={5}
                  max={60}
                  className="w-20 border rounded-lg px-3 py-2 text-sm"
                />
                <button
                  onClick={handleBrowse}
                  disabled={!selectedProxyId || !url || isLoading}
                  className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isLoading ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Loading...
                    </>
                  ) : (
                    <>
                      <Globe className="h-4 w-4" />
                      Go
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Error Display */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6 flex items-center gap-2 text-red-700">
            <AlertCircle className="h-5 w-5" />
            {error}
          </div>
        )}

        {/* Results Section */}
        {browseResult && (
          <div className="space-y-4">
            {/* Status Bar */}
            <div className={`rounded-lg border p-4 ${
              browseResult.success ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'
            }`}>
              <div className="flex items-center justify-between flex-wrap gap-4">
                <div className="flex items-center gap-4">
                  {browseResult.success ? (
                    <CheckCircle className="h-6 w-6 text-green-600" />
                  ) : (
                    <AlertCircle className="h-6 w-6 text-red-600" />
                  )}
                  <div>
                    <div className="font-medium">
                      {browseResult.success ? 'Request Successful' : 'Request Failed'}
                    </div>
                    <div className="text-sm text-gray-600">
                      via {browseResult.proxy_address}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-6 text-sm">
                  {browseResult.status_code && (
                    <div className="flex items-center gap-1">
                      <span className={`px-2 py-1 rounded font-medium ${
                        browseResult.status_code < 300 ? 'bg-green-100 text-green-800' :
                        browseResult.status_code < 400 ? 'bg-yellow-100 text-yellow-800' :
                        'bg-red-100 text-red-800'
                      }`}>
                        HTTP {browseResult.status_code}
                      </span>
                    </div>
                  )}
                  {browseResult.elapsed_ms && (
                    <div className="flex items-center gap-1 text-gray-600">
                      <Clock className="h-4 w-4" />
                      {browseResult.elapsed_ms.toFixed(0)}ms
                    </div>
                  )}
                  {browseResult.content_type && (
                    <div className="flex items-center gap-1 text-gray-600">
                      <FileText className="h-4 w-4" />
                      {browseResult.content_type.split(';')[0]}
                    </div>
                  )}
                  <a
                    href={browseResult.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1 text-blue-600 hover:text-blue-800"
                  >
                    <ExternalLink className="h-4 w-4" />
                    Open directly
                  </a>
                </div>
              </div>

              {browseResult.error && (
                <div className="mt-2 text-red-600">
                  Error: {browseResult.error}
                </div>
              )}
            </div>

            {/* Response Headers */}
            {browseResult.headers && Object.keys(browseResult.headers).length > 0 && (
              <details className="bg-white rounded-lg border">
                <summary className="px-4 py-3 cursor-pointer font-medium text-gray-700 hover:bg-gray-50">
                  Response Headers ({Object.keys(browseResult.headers).length})
                </summary>
                <div className="px-4 pb-4">
                  <div className="bg-gray-50 rounded p-3 text-sm font-mono overflow-x-auto">
                    {Object.entries(browseResult.headers).map(([key, value]) => (
                      <div key={key} className="flex">
                        <span className="text-blue-600 mr-2">{key}:</span>
                        <span className="text-gray-700 break-all">{value}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </details>
            )}

            {/* Response Content */}
            {browseResult.content && (
              <div className="bg-white rounded-lg border">
                <div className="px-4 py-3 border-b font-medium text-gray-700 flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <span>Response Content</span>
                    <span className="text-sm font-normal text-gray-500">
                      {browseResult.content.length.toLocaleString()} characters
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    {/* View mode toggle for HTML content */}
                    {isHtmlContent && (
                      <div className="flex border rounded-lg overflow-hidden">
                        <button
                          onClick={() => setViewMode('rendered')}
                          className={`px-3 py-1 text-sm flex items-center gap-1 ${
                            viewMode === 'rendered'
                              ? 'bg-blue-500 text-white'
                              : 'bg-gray-50 text-gray-600 hover:bg-gray-100'
                          }`}
                        >
                          <Eye className="h-3 w-3" />
                          Preview
                        </button>
                        <button
                          onClick={() => setViewMode('source')}
                          className={`px-3 py-1 text-sm flex items-center gap-1 ${
                            viewMode === 'source'
                              ? 'bg-blue-500 text-white'
                              : 'bg-gray-50 text-gray-600 hover:bg-gray-100'
                          }`}
                        >
                          <Code className="h-3 w-3" />
                          Source
                        </button>
                      </div>
                    )}
                    <button
                      onClick={() => setIsFullscreen(true)}
                      className="p-1 hover:bg-gray-100 rounded"
                      title="Fullscreen"
                    >
                      <Maximize2 className="h-4 w-4 text-gray-500" />
                    </button>
                  </div>
                </div>
                <div className="p-4">
                  {isHtmlContent && viewMode === 'rendered' && processedHtmlContent ? (
                    <div className="border rounded bg-white overflow-hidden">
                      <iframe
                        srcDoc={processedHtmlContent}
                        className="w-full border-0"
                        style={{ height: '600px' }}
                        sandbox="allow-same-origin allow-scripts allow-popups allow-forms"
                        title="Response preview"
                      />
                    </div>
                  ) : (
                    <pre className="bg-gray-50 rounded p-4 text-sm overflow-auto font-mono whitespace-pre-wrap break-all" style={{ maxHeight: '600px' }}>
                      {formattedContent}
                    </pre>
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Empty State */}
        {!browseResult && !isLoading && (
          <div className="bg-white rounded-lg border p-12 text-center text-gray-500">
            <Globe className="h-12 w-12 mx-auto mb-4 opacity-50" />
            <p>Select a proxy and enter a URL to browse through the proxy.</p>
            <p className="text-sm mt-2">
              This allows you to test if the proxy works and see what content it returns.
            </p>
          </div>
        )}
      </main>
    </div>
  )
}
