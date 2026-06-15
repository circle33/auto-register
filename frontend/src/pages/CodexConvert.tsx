import { useEffect, useState, useCallback } from 'react'
import { apiFetch } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Copy, Download, RefreshCw, Check, ChevronRight, Search, Loader2 } from 'lucide-react'

interface CodexAccount {
  account_id: number
  email: string
  platform: string
  plan_type: string
  access_token_valid: boolean
  session_token_valid: boolean
  expires_at_unix: number
  auth_json: string
}

interface AccountItem {
  id: number
  email: string
  platform: string
  display_status: string
  plan_state: string
  plan_name: string
  extra?: Record<string, any>
}

function getPlatformLabel(p: string) {
  return p === 'chatgpt' ? 'ChatGPT' : p === 'chatgpt2' ? 'ChatGPT2' : p
}

export default function CodexConvert() {
  const [accounts, setAccounts] = useState<AccountItem[]>([])
  const [search, setSearch] = useState('')
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [codexData, setCodexData] = useState<CodexAccount | null>(null)
  const [loading, setLoading] = useState(false)
  const [copied, setCopied] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [loadingList, setLoadingList] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // ── 加载账号列表 ──
  const loadAccounts = useCallback(async () => {
    setLoadingList(true)
    setError(null)
    try {
      const [c1, c2] = await Promise.all([
        apiFetch('/accounts?platform=chatgpt&page_size=200'),
        apiFetch('/accounts?platform=chatgpt2&page_size=200'),
      ])
      const all = [...(c1?.items || []), ...(c2?.items || [])]
      setAccounts(all)
    } catch (e: any) {
      console.error('加载账号列表失败', e)
      setError(e?.message || '加载账号列表失败')
    } finally {
      setLoadingList(false)
    }
  }, [])

  useEffect(() => { loadAccounts() }, [])

  // ── 选择账号 → 加载 Codex 数据 ──
  const selectAccount = async (id: number) => {
    setSelectedId(id)
    setCopied(false)
    setError(null)
    setLoading(true)
    try {
      const data = await apiFetch(`/accounts/${id}/codex`)
      setCodexData(data)
    } catch (e: any) {
      console.error('加载 Codex 数据失败', e)
      setError(e?.message || '加载失败')
      setCodexData(null)
    } finally {
      setLoading(false)
    }
  }

  // ── 复制 auth.json ──
  const copyAuthJson = async () => {
    if (!codexData?.auth_json) return
    try {
      await navigator.clipboard.writeText(codexData.auth_json)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // fallback
      const ta = document.createElement('textarea')
      ta.value = codexData.auth_json
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  // ── 下载 auth.json ──
  const downloadAuthJson = () => {
    if (!codexData?.auth_json) return
    const blob = new Blob([codexData.auth_json], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'auth.json'
    a.click()
    URL.revokeObjectURL(url)
  }

  // ── 刷新 Token ──
  const refreshToken = async () => {
    if (!codexData) return
    setRefreshing(true)
    try {
      await apiFetch(`/actions/${codexData.platform}/${codexData.account_id}/refresh_token`, {
        method: 'POST',
        body: JSON.stringify({ params: {} }),
      })
      // 刷新后重新加载 Codex 数据
      await selectAccount(codexData.account_id)
    } catch (e: any) {
      console.error('Token 刷新失败', e)
      alert('Token 刷新失败: ' + (e?.message || '未知错误'))
    } finally {
      setRefreshing(false)
    }
  }

  // ── 过滤 ──
  const filtered = accounts.filter(a =>
    !search || a.email.toLowerCase().includes(search.toLowerCase())
  )

  // ── 过期时间显示 ──
  const expiresLabel = (unix: number) => {
    if (!unix || unix <= 0) return '未知'
    const d = new Date(unix * 1000)
    const now = Date.now()
    const diff = d.getTime() - now
    if (diff < 0) return '已过期'
    const days = Math.floor(diff / 86400000)
    if (days < 1) return '今天到期'
    if (days < 30) return `${days} 天后到期`
    return d.toLocaleDateString('zh-CN')
  }

  const expiresSoon = (unix: number) => {
    if (!unix) return false
    return unix * 1000 - Date.now() < 7 * 86400000
  }

  return (
    <div className="flex h-full min-h-0 gap-0 overflow-hidden">
      {/* ── 左侧账号列表 ── */}
      <div className="flex w-80 shrink-0 flex-col border-r border-[var(--border)] bg-[var(--bg-card)]">
        <div className="px-4 py-3 border-b border-[var(--border)]">
          <h2 className="text-sm font-semibold text-[var(--text-primary)]">Codex 转换</h2>
          <p className="text-xs text-[var(--text-muted)] mt-0.5">
            选择账号生成 auth.json
          </p>
        </div>
        <div className="px-3 py-2">
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[var(--text-muted)]" />
            <input
              className="w-full rounded-md border border-[var(--border)] bg-[var(--bg-input)] py-1.5 pl-8 pr-3 text-xs text-[var(--text-primary)] placeholder:text-[var(--text-muted)] outline-none focus:border-[var(--accent)]"
              placeholder="搜索邮箱..."
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
          </div>
        </div>
        <div className="flex-1 overflow-y-auto">
          {loadingList ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-5 w-5 animate-spin text-[var(--text-muted)]" />
            </div>
          ) : filtered.length === 0 ? (
            <p className="px-4 py-8 text-center text-xs text-[var(--text-muted)]">
              {search ? '无匹配账号' : '暂无 ChatGPT 账号'}
            </p>
          ) : (
            filtered.map(acc => (
              <button
                key={acc.id}
                onClick={() => selectAccount(acc.id)}
                className={
                  `flex w-full items-center gap-2.5 px-4 py-2.5 text-left text-xs transition-colors hover:bg-[var(--bg-hover)] border-b border-[var(--border-soft)] ` +
                  (selectedId === acc.id ? 'bg-[var(--accent-soft)] border-l-2 border-l-[var(--accent)]' : 'border-l-2 border-l-transparent')
                }
              >
                <div className="flex-1 min-w-0">
                  <div className="truncate font-medium text-[var(--text-primary)]">{acc.email}</div>
                  <div className="flex items-center gap-1.5 mt-0.5">
                    <span className="text-[10px] text-[var(--text-muted)]">{getPlatformLabel(acc.platform)}</span>
                    {acc.plan_name && (
                      <Badge variant="secondary" className="text-[9px] px-1 py-0">{acc.plan_name}</Badge>
                    )}
                  </div>
                </div>
                <ChevronRight className="h-3 w-3 shrink-0 text-[var(--text-muted)]" />
              </button>
            ))
          )}
        </div>
        <div className="px-4 py-2 border-t border-[var(--border)] text-[10px] text-[var(--text-muted)]">
          {accounts.length} 个账号
        </div>
      </div>

      {/* ── 右侧详情面板 ── */}
      <div className="flex-1 overflow-y-auto p-6">
        {!selectedId && (
          <div className="flex h-full items-center justify-center">
            <div className="text-center">
              <div className="text-4xl mb-3">🔑</div>
              <p className="text-sm text-[var(--text-muted)]">选择左侧账号查看 Codex auth.json</p>
              <p className="text-xs text-[var(--text-muted)] mt-1">
                支持 ChatGPT / ChatGPT2 平台
              </p>
            </div>
          </div>
        )}

        {loading && (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-6 w-6 animate-spin text-[var(--accent)]" />
          </div>
        )}

        {error && !loading && (
          <div className="flex flex-col items-center justify-center py-12 gap-2">
            <p className="text-sm text-red-400">{error}</p>
            <Button size="sm" variant="outline" onClick={() => selectedId && selectAccount(selectedId)}>重试</Button>
          </div>
        )}

        {codexData && !loading && !error && (
          <div className="space-y-4">
            {/* ── 账号信息 ── */}
            <Card className="p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h3 className="text-sm font-semibold text-[var(--text-primary)]">{codexData.email}</h3>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-xs text-[var(--text-muted)]">{getPlatformLabel(codexData.platform)}</span>
                    <Badge variant={codexData.plan_type && codexData.plan_type !== 'unknown' ? 'success' : 'secondary'}>
                      {codexData.plan_type || 'unknown'}
                    </Badge>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <div className="flex items-center gap-1.5 text-xs">
                    <span className={`h-2 w-2 rounded-full ${codexData.access_token_valid ? 'bg-green-500' : 'bg-red-500'}`} />
                    <span className="text-[var(--text-muted)]">access_token</span>
                  </div>
                  <div className="flex items-center gap-1.5 text-xs">
                    <span className={`h-2 w-2 rounded-full ${codexData.session_token_valid ? 'bg-green-500' : 'bg-yellow-500'}`} />
                    <span className="text-[var(--text-muted)]">session</span>
                  </div>
                </div>
              </div>
              <div className="mt-2 text-xs text-[var(--text-muted)]">
                过期时间: <span className={expiresSoon(codexData.expires_at_unix) ? 'text-red-400 font-medium' : ''}>
                  {expiresLabel(codexData.expires_at_unix)}
                </span>
              </div>
            </Card>

            {/* ── auth.json ── */}
            <Card className="p-4">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold text-[var(--text-primary)]">auth.json</h3>
                <div className="flex gap-2">
                  <Button size="sm" variant="outline" onClick={copyAuthJson} className="h-7 text-xs gap-1">
                    {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
                    {copied ? '已复制' : '复制'}
                  </Button>
                  <Button size="sm" variant="outline" onClick={downloadAuthJson} className="h-7 text-xs gap-1">
                    <Download className="h-3 w-3" />
                    下载
                  </Button>
                </div>
              </div>
              <pre className="rounded-lg border border-[var(--border)] bg-[var(--bg-code)] p-4 text-xs font-mono text-[var(--text-code)] overflow-auto max-h-96 whitespace-pre-wrap break-all">
                {codexData.auth_json || '(空)'}
              </pre>
              <p className="mt-2 text-[10px] text-[var(--text-muted)]">
                放到 <code className="text-[11px]">~/.codex/auth.json</code>（macOS/Linux）或{' '}
                <code className="text-[11px]">%USERPROFILE%\.codex\auth.json</code>（Windows）
              </p>
            </Card>

            {/* ── Token 刷新 ── */}
            <Card className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-semibold text-[var(--text-primary)]">Token 状态</h3>
                  <p className="text-xs text-[var(--text-muted)] mt-0.5">
                    如果 access_token 过期或即将过期，可以尝试刷新
                  </p>
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={refreshToken}
                  disabled={refreshing || !codexData.access_token_valid}
                  className="h-7 text-xs gap-1"
                >
                  <RefreshCw className={`h-3 w-3 ${refreshing ? 'animate-spin' : ''}`} />
                  {refreshing ? '刷新中...' : '刷新 Token'}
                </Button>
              </div>
            </Card>
          </div>
        )}
      </div>
    </div>
  )
}
