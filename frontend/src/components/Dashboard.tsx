import { Globe, Server, Zap, Shield, Clock, TrendingUp } from 'lucide-react'
import { ProxyStats } from '../services/api'
import { StatsCard } from './StatsCard'

interface DashboardProps {
  stats: ProxyStats | undefined
  isLoading: boolean
}

function ProtocolBar({ protocol, count, total, color }: { protocol: string; count: number; total: number; color: string }) {
  const percent = total > 0 ? (count / total) * 100 : 0
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs uppercase text-gray-500 w-14">{protocol}</span>
      <div className="flex-1 h-4 bg-gray-100 rounded-full overflow-hidden">
        <div
          className={`h-full ${color} transition-all duration-500`}
          style={{ width: `${percent}%` }}
        />
      </div>
      <span className="text-xs text-gray-600 w-12 text-right">{count.toLocaleString()}</span>
    </div>
  )
}

function AnonymityBadge({ level, count }: { level: string; count: number }) {
  const colors: Record<string, string> = {
    elite: 'bg-green-100 text-green-700 border-green-200',
    anonymous: 'bg-blue-100 text-blue-700 border-blue-200',
    transparent: 'bg-yellow-100 text-yellow-700 border-yellow-200',
  }
  return (
    <div className={`px-3 py-2 rounded-lg border ${colors[level] || 'bg-gray-100 text-gray-700 border-gray-200'}`}>
      <div className="text-lg font-bold">{count.toLocaleString()}</div>
      <div className="text-xs capitalize">{level}</div>
    </div>
  )
}

export function Dashboard({ stats, isLoading }: DashboardProps) {
  if (isLoading) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="bg-gray-100 rounded-lg h-24 animate-pulse" />
        ))}
      </div>
    )
  }

  if (!stats) {
    return null
  }

  const protocolColors: Record<string, string> = {
    http: 'bg-blue-500',
    https: 'bg-green-500',
    socks4: 'bg-purple-500',
    socks5: 'bg-indigo-500',
  }

  const totalProtocol = Object.values(stats.by_protocol).reduce((a, b) => a + b, 0)

  return (
    <div className="space-y-6 mb-6">
      {/* Main Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatsCard
          title="Total Proxies"
          value={stats.total.toLocaleString()}
          subtitle={`${stats.active.toLocaleString()} active`}
          icon={<Server />}
          color="blue"
        />
        <StatsCard
          title="Active Rate"
          value={`${stats.total ? Math.round((stats.active / stats.total) * 100) : 0}%`}
          subtitle={`${stats.inactive.toLocaleString()} inactive`}
          icon={<Zap />}
          color={stats.active / stats.total > 0.5 ? 'green' : 'yellow'}
        />
        <StatsCard
          title="Avg Speed"
          value={stats.average_speed ? `${Math.round(stats.average_speed)}ms` : '-'}
          subtitle={stats.average_speed && stats.average_speed < 1000 ? 'Good' : stats.average_speed ? 'Moderate' : 'No data'}
          icon={<Clock />}
          color={stats.average_speed && stats.average_speed < 1000 ? 'green' : 'yellow'}
        />
        <StatsCard
          title="Avg Score"
          value={stats.average_score.toFixed(1)}
          subtitle="out of 100"
          icon={<TrendingUp />}
          color={stats.average_score >= 50 ? 'green' : stats.average_score >= 30 ? 'yellow' : 'red'}
        />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Protocol Distribution */}
        <div className="bg-white rounded-lg border p-4">
          <h3 className="font-medium text-gray-900 mb-4 flex items-center gap-2">
            <Shield className="h-4 w-4 text-gray-400" />
            Protocol Distribution
          </h3>
          <div className="space-y-3">
            {['http', 'https', 'socks4', 'socks5'].map((proto) => (
              <ProtocolBar
                key={proto}
                protocol={proto}
                count={stats.by_protocol[proto] || 0}
                total={totalProtocol}
                color={protocolColors[proto]}
              />
            ))}
          </div>
        </div>

        {/* Anonymity Levels */}
        <div className="bg-white rounded-lg border p-4">
          <h3 className="font-medium text-gray-900 mb-4 flex items-center gap-2">
            <Shield className="h-4 w-4 text-gray-400" />
            Anonymity Levels
          </h3>
          <div className="flex gap-2 flex-wrap">
            {['elite', 'anonymous', 'transparent'].map((level) => (
              <AnonymityBadge
                key={level}
                level={level}
                count={stats.by_anonymity[level] || 0}
              />
            ))}
          </div>
          <div className="mt-3 text-xs text-gray-500">
            <span className="text-green-600 font-medium">Elite</span> = Fully anonymous •
            <span className="text-blue-600 font-medium ml-1">Anonymous</span> = Hides IP •
            <span className="text-yellow-600 font-medium ml-1">Transparent</span> = Reveals IP
          </div>
        </div>

        {/* Top Countries */}
        <div className="bg-white rounded-lg border p-4">
          <h3 className="font-medium text-gray-900 mb-3 flex items-center gap-2">
            <Globe className="h-4 w-4 text-gray-400" />
            Top Countries
          </h3>
          <div className="space-y-2 max-h-40 overflow-y-auto">
            {Object.entries(stats.by_country)
              .sort(([, a], [, b]) => b - a)
              .slice(0, 8)
              .map(([country, count], index) => (
                <div key={country} className="flex justify-between items-center">
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-gray-400 w-4">{index + 1}.</span>
                    <span className="text-sm text-gray-700 font-medium">{country}</span>
                  </div>
                  <span className="text-sm text-gray-500">{count.toLocaleString()}</span>
                </div>
              ))}
          </div>
        </div>
      </div>
    </div>
  )
}
