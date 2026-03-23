import { CheckCircle, XCircle, Loader2, Zap } from 'lucide-react'
import { ValidationProgress as ValidationProgressType } from '../services/api'

interface ValidationProgressProps {
  progress: ValidationProgressType | null
  isValidating: boolean
  onCancel?: () => void
}

export function ValidationProgress({ progress, isValidating, onCancel }: ValidationProgressProps) {
  if (!isValidating && !progress) {
    return null
  }

  // Show completion summary if done
  if (progress?.done && !isValidating) {
    return (
      <div className="bg-white rounded-lg border p-4 mb-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 text-green-600">
              <CheckCircle className="h-5 w-5" />
              <span className="font-medium">{progress.successful} Working</span>
            </div>
            <div className="flex items-center gap-2 text-red-500">
              <XCircle className="h-5 w-5" />
              <span className="font-medium">{progress.failed} Failed</span>
            </div>
            <div className="text-gray-500 text-sm">
              Success rate: {progress.total > 0 ? Math.round((progress.successful / progress.total) * 100) : 0}%
            </div>
          </div>
          <span className="text-sm text-gray-500">Validation complete</span>
        </div>
      </div>
    )
  }

  // Show progress while validating
  return (
    <div className="bg-white rounded-lg border p-4 mb-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Loader2 className="h-5 w-5 text-blue-500 animate-spin" />
          <span className="font-medium text-gray-900">Validating Proxies</span>
        </div>
        {onCancel && (
          <button
            onClick={onCancel}
            className="text-sm text-red-500 hover:text-red-600"
          >
            Cancel
          </button>
        )}
      </div>

      {/* Progress bar */}
      <div className="relative h-3 bg-gray-200 rounded-full overflow-hidden mb-3">
        <div
          className="absolute inset-y-0 left-0 bg-gradient-to-r from-blue-500 to-blue-600 transition-all duration-300"
          style={{ width: `${progress?.percent || 0}%` }}
        />
        {/* Success portion */}
        {progress && progress.successful > 0 && (
          <div
            className="absolute inset-y-0 left-0 bg-green-500 transition-all duration-300"
            style={{ width: `${(progress.successful / progress.total) * 100}%` }}
          />
        )}
      </div>

      {/* Stats */}
      <div className="flex items-center justify-between text-sm">
        <div className="flex items-center gap-4">
          <span className="text-gray-600">
            {progress?.completed || 0} / {progress?.total || 0}
          </span>
          <div className="flex items-center gap-1 text-green-600">
            <CheckCircle className="h-4 w-4" />
            <span>{progress?.successful || 0}</span>
          </div>
          <div className="flex items-center gap-1 text-red-500">
            <XCircle className="h-4 w-4" />
            <span>{progress?.failed || 0}</span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {progress?.current_proxy && (
            <code className="text-xs bg-gray-100 px-2 py-0.5 rounded">
              {progress.current_proxy}
            </code>
          )}
          <span className="text-gray-500">{Math.round(progress?.percent || 0)}%</span>
        </div>
      </div>

      {/* Latest result indicator */}
      {progress?.latest_result && (
        <div className={`mt-2 text-xs flex items-center gap-1 ${
          progress.latest_result.is_valid ? 'text-green-600' : 'text-red-500'
        }`}>
          {progress.latest_result.is_valid ? (
            <>
              <Zap className="h-3 w-3" />
              <span>{progress.latest_result.speed}ms</span>
            </>
          ) : (
            <>
              <XCircle className="h-3 w-3" />
              <span>{progress.latest_result.error || 'Failed'}</span>
            </>
          )}
        </div>
      )}
    </div>
  )
}
