import { useState, useRef, useCallback } from 'react'
import { BrowserRouter, Routes, Route, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { RefreshCw, CheckCircle2, Trash2, Download, Zap } from 'lucide-react'
import { proxyApi, ProxyFilters, ValidationProgress as ValidationProgressType } from './services/api'
import { Dashboard } from './components/Dashboard'
import { ProxyFilters as Filters } from './components/ProxyFilters'
import { ProxyTable } from './components/ProxyTable'
import { Pagination } from './components/Pagination'
import { ProxyBrowser } from './pages/ProxyBrowser'
import { ValidationProgress } from './components/ValidationProgress'

function HomePage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [filters, setFilters] = useState<ProxyFilters>({
    page: 1,
    page_size: 50,
    sort_by: 'score',
    sort_order: 'desc',
    is_active: true,
  })

  // Validation state
  const [isValidating, setIsValidating] = useState(false)
  const [validationProgress, setValidationProgress] = useState<ValidationProgressType | null>(null)
  const validationAbortRef = useRef<{ abort: () => void } | null>(null)

  // Queries
  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ['stats'],
    queryFn: proxyApi.getStats,
  })

  const { data: proxies, isLoading: proxiesLoading } = useQuery({
    queryKey: ['proxies', filters],
    queryFn: () => proxyApi.list(filters),
  })

  // Mutations
  const refreshMutation = useMutation({
    mutationFn: () => proxyApi.refresh(filters.protocol, filters.country),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['proxies'] })
      queryClient.invalidateQueries({ queryKey: ['stats'] })
    },
  })

  // Start streaming validation
  const startValidation = useCallback((quick: boolean = false) => {
    setIsValidating(true)
    setValidationProgress(null)

    validationAbortRef.current = proxyApi.validateStream(
      (progress) => {
        setValidationProgress(progress)

        if (progress.done) {
          setIsValidating(false)
          // Refresh data after completion
          queryClient.invalidateQueries({ queryKey: ['proxies'] })
          queryClient.invalidateQueries({ queryKey: ['stats'] })
        }
      },
      undefined,
      0,  // 0 means no limit - validate all proxies
      quick
    )
  }, [queryClient])

  // Cancel validation
  const cancelValidation = useCallback(() => {
    validationAbortRef.current?.abort()
    setIsValidating(false)
    setValidationProgress(null)
  }, [])

  const deleteMutation = useMutation({
    mutationFn: proxyApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['proxies'] })
      queryClient.invalidateQueries({ queryKey: ['stats'] })
    },
  })

  const deleteInactiveMutation = useMutation({
    mutationFn: proxyApi.deleteInactive,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['proxies'] })
      queryClient.invalidateQueries({ queryKey: ['stats'] })
    },
  })

  const handleValidateSingle = async (proxyId: number) => {
    const result = await proxyApi.validateSingle(proxyId)
    // Refresh the proxy list to show updated data
    queryClient.invalidateQueries({ queryKey: ['proxies'] })
    queryClient.invalidateQueries({ queryKey: ['stats'] })
    return result
  }

  const handleBrowse = (proxyId: number) => {
    navigate(`/browser?proxy=${proxyId}`)
  }

  const handleExport = () => {
    if (!proxies?.items.length) return

    const content = proxies.items
      .map((p) => `${p.protocol}://${p.address}`)
      .join('\n')

    const blob = new Blob([content], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'proxies.txt'
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-bold text-gray-900">Proxy Finder</h1>
            <div className="flex items-center gap-2">
              <button
                onClick={() => refreshMutation.mutate()}
                disabled={refreshMutation.isPending}
                className="flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50"
              >
                <RefreshCw className={`h-4 w-4 ${refreshMutation.isPending ? 'animate-spin' : ''}`} />
                {refreshMutation.isPending ? 'Refreshing...' : 'Refresh'}
              </button>
              <button
                onClick={() => startValidation(false)}
                disabled={isValidating}
                className="flex items-center gap-2 px-4 py-2 bg-green-500 text-white rounded-lg hover:bg-green-600 disabled:opacity-50"
              >
                <CheckCircle2 className={`h-4 w-4 ${isValidating ? 'animate-pulse' : ''}`} />
                {isValidating ? 'Validating...' : 'Validate'}
              </button>
              <button
                onClick={() => startValidation(true)}
                disabled={isValidating}
                className="flex items-center gap-2 px-3 py-2 bg-yellow-500 text-white rounded-lg hover:bg-yellow-600 disabled:opacity-50"
                title="Quick validation - faster but less thorough"
              >
                <Zap className="h-4 w-4" />
                Quick
              </button>
              <button
                onClick={() => deleteInactiveMutation.mutate()}
                disabled={deleteInactiveMutation.isPending}
                className="flex items-center gap-2 px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600 disabled:opacity-50"
              >
                <Trash2 className="h-4 w-4" />
                Clean Inactive
              </button>
              <button
                onClick={handleExport}
                disabled={!proxies?.items.length}
                className="flex items-center gap-2 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50"
              >
                <Download className="h-4 w-4" />
                Export
              </button>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6">
        {/* Notification messages */}
        {refreshMutation.isSuccess && (
          <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-lg text-green-700">
            {refreshMutation.data.message}
          </div>
        )}
        {refreshMutation.isError && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700">
            An error occurred. Please try again.
          </div>
        )}
        {validationProgress?.error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700">
            Validation error: {validationProgress.error}
          </div>
        )}

        {/* Validation Progress */}
        <ValidationProgress
          progress={validationProgress}
          isValidating={isValidating}
          onCancel={cancelValidation}
        />

        <Dashboard stats={stats} isLoading={statsLoading} />

        <Filters filters={filters} onChange={setFilters} />

        <div className="mb-2 text-sm text-gray-500">
          {proxies && `Showing ${proxies.items.length} of ${proxies.total} proxies`}
        </div>

        <ProxyTable
          proxies={proxies?.items || []}
          onDelete={(id) => deleteMutation.mutate(id)}
          onValidate={handleValidateSingle}
          onBrowse={handleBrowse}
          isLoading={proxiesLoading}
        />

        {proxies && (
          <Pagination
            page={proxies.page}
            totalPages={proxies.total_pages}
            onPageChange={(page) => setFilters({ ...filters, page })}
          />
        )}
      </main>

      <footer className="border-t bg-white mt-8">
        <div className="max-w-7xl mx-auto px-4 py-4 text-center text-sm text-gray-500">
          Proxy Finder - Use responsibly and in accordance with applicable laws.
        </div>
      </footer>
    </div>
  )
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/browser" element={<ProxyBrowser />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
