import { ProxyFilters as Filters } from '../services/api'

interface ProxyFiltersProps {
  filters: Filters
  onChange: (filters: Filters) => void
}

const protocols = ['', 'http', 'https', 'socks4', 'socks5']
const anonymityLevels = ['', 'transparent', 'anonymous', 'elite']
const sortOptions = [
  { value: 'score', label: 'Score' },
  { value: 'speed', label: 'Speed' },
  { value: 'last_check', label: 'Last Check' },
  { value: 'created_at', label: 'Created' },
]

export function ProxyFilters({ filters, onChange }: ProxyFiltersProps) {
  const updateFilter = (key: keyof Filters, value: string | number | boolean | undefined) => {
    onChange({ ...filters, [key]: value || undefined, page: 1 })
  }

  return (
    <div className="bg-white rounded-lg border p-4 mb-4">
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Protocol</label>
          <select
            className="w-full border rounded-md px-3 py-2 text-sm"
            value={filters.protocol || ''}
            onChange={(e) => updateFilter('protocol', e.target.value)}
          >
            <option value="">All</option>
            {protocols.filter(Boolean).map((p) => (
              <option key={p} value={p}>
                {p.toUpperCase()}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Country</label>
          <input
            type="text"
            className="w-full border rounded-md px-3 py-2 text-sm"
            placeholder="e.g., US"
            maxLength={2}
            value={filters.country || ''}
            onChange={(e) => updateFilter('country', e.target.value.toUpperCase())}
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Anonymity</label>
          <select
            className="w-full border rounded-md px-3 py-2 text-sm"
            value={filters.anonymity || ''}
            onChange={(e) => updateFilter('anonymity', e.target.value)}
          >
            <option value="">All</option>
            {anonymityLevels.filter(Boolean).map((a) => (
              <option key={a} value={a}>
                {a.charAt(0).toUpperCase() + a.slice(1)}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Min Score</label>
          <input
            type="number"
            className="w-full border rounded-md px-3 py-2 text-sm"
            placeholder="0-100"
            min={0}
            max={100}
            value={filters.min_score || ''}
            onChange={(e) => updateFilter('min_score', e.target.value ? Number(e.target.value) : undefined)}
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Sort By</label>
          <select
            className="w-full border rounded-md px-3 py-2 text-sm"
            value={filters.sort_by || 'score'}
            onChange={(e) => updateFilter('sort_by', e.target.value)}
          >
            {sortOptions.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Order</label>
          <select
            className="w-full border rounded-md px-3 py-2 text-sm"
            value={filters.sort_order || 'desc'}
            onChange={(e) => updateFilter('sort_order', e.target.value)}
          >
            <option value="desc">Descending</option>
            <option value="asc">Ascending</option>
          </select>
        </div>
      </div>
    </div>
  )
}
