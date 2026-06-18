import { useEffect, useState } from 'react'
import { apiFetch } from '@/lib/utils'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { RefreshCw, Wifi, WifiOff, Activity, Key, ShieldOff } from 'lucide-react'

export default function Chat2APIStatus() {
  const [status, setStatus] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  const load = async () => {
    setLoading(true)
    try {
      const data = await apiFetch('/chat2api/status')
      setStatus(data)
    } catch {
      setStatus(null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    /* eslint-disable-next-line react-hooks/set-state-in-effect */
    load()
  }, [])

  const enabled = status?.enabled
  const activeAccounts = status?.active_accounts ?? 0
  const totalAccounts = status?.total_accounts ?? 0
  const apiKeyConfigured = status?.api_key_configured
  const accounts = (status?.accounts || []) as any[]

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-[var(--text-primary)]">Chat2API</h1>
        <Button variant="outline" size="sm" onClick={load} disabled={loading}>
          <RefreshCw className={`h-3.5 w-3.5 mr-1 ${loading ? 'animate-spin' : ''}`} />
          刷新
        </Button>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="服务状态"
          value={status == null ? '--' : enabled ? '已启用' : '已禁用'}
          icon={enabled ? Wifi : WifiOff}
          color={enabled ? 'text-emerald-400' : 'text-[var(--text-muted)]'}
        />
        <StatCard
          label="可用账号"
          value={`${activeAccounts} / ${totalAccounts}`}
          icon={Activity}
          color={activeAccounts > 0 ? 'text-emerald-400' : 'text-amber-400'}
        />
        <StatCard
          label="API Key"
          value={apiKeyConfigured ? '已设置' : '未设置'}
          icon={apiKeyConfigured ? Key : ShieldOff}
          color={apiKeyConfigured ? 'text-emerald-400' : 'text-[var(--text-muted)]'}
        />
        <StatCard
          label="API 地址"
          value="/v1/chat/completions"
          icon={Activity}
          color="text-[var(--text-secondary)]"
        />
      </div>

      {!enabled && status != null && (
        <Card>
          <CardContent className="py-4 text-center text-sm text-[var(--text-muted)]">
            服务未启用。前往 <a href="/settings?tab=general" className="text-[var(--accent)] underline">设置</a> 开启 chat2api_enabled。
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader><CardTitle>账号列表</CardTitle></CardHeader>
        <CardContent className="overflow-x-auto p-0">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--border)] bg-[var(--bg-pane)]">
                <th className="px-4 py-2.5 text-left text-xs font-medium text-[var(--text-muted)]">邮箱</th>
                <th className="px-4 py-2.5 text-left text-xs font-medium text-[var(--text-muted)]">状态</th>
                <th className="px-4 py-2.5 text-left text-xs font-medium text-[var(--text-muted)]">access_token</th>
                <th className="px-4 py-2.5 text-left text-xs font-medium text-[var(--text-muted)]">可用</th>
              </tr>
            </thead>
            <tbody>
              {accounts.length === 0 && (
                <tr>
                  <td colSpan={4} className="px-4 py-8 text-center text-sm text-[var(--text-muted)]">
                    {loading ? '加载中...' : '暂无 gpt2 账号'}
                  </td>
                </tr>
              )}
              {accounts.map((acc: any) => (
                <tr key={acc.id} className="border-b border-[var(--border)]/30 hover:bg-[var(--bg-hover)]">
                  <td className="px-4 py-2.5 text-[var(--text-primary)]">{acc.email}</td>
                  <td className="px-4 py-2.5">
                    <Badge variant={
                      acc.lifecycle === 'subscribed' ? 'success' :
                      acc.lifecycle === 'trial' ? 'success' :
                      acc.lifecycle === 'invalid' ? 'danger' :
                      acc.lifecycle === 'expired' ? 'warning' :
                      'secondary'
                    }>
                      {acc.lifecycle || 'unknown'}
                    </Badge>
                  </td>
                  <td className="px-4 py-2.5">
                    {acc.has_access_token ? (
                      <span className="font-mono text-xs text-[var(--text-secondary)]">
                        {acc.credentials?.access_token || '***'}
                      </span>
                    ) : (
                      <span className="text-[var(--text-muted)]">--</span>
                    )}
                  </td>
                  <td className="px-4 py-2.5">
                    <Badge variant={acc.active && acc.has_access_token ? 'success' : 'secondary'}>
                      {acc.active && acc.has_access_token ? '可用' : '不可用'}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  )
}

function StatCard({ label, value, icon: Icon, color }: {
  label: string; value: string; icon: any; color: string
}) {
  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--bg-pane)]/45 px-3 py-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-[11px] tracking-[0.16em] text-[var(--text-muted)]">{label}</p>
          <p className="mt-1 text-lg font-semibold tracking-[-0.03em] text-[var(--text-primary)]">{value}</p>
        </div>
        <div className="flex h-9 w-9 items-center justify-center rounded-md border border-[var(--border)] bg-[var(--chip-bg)]">
          <Icon className={`h-4.5 w-4.5 ${color} opacity-90`} />
        </div>
      </div>
    </div>
  )
}
