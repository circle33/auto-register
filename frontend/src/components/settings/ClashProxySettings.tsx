import { useEffect, useState } from 'react'
import { apiFetch } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import { Save, RefreshCw, Wifi, WifiOff, Globe, Activity } from 'lucide-react'

/* ------------------------------------------------------------------ */
/*  Setting group card (copied from SettingsPage)                       */
/* ------------------------------------------------------------------ */
function SettingGroup({ title, desc, children }: { title: string; desc?: string; children: React.ReactNode }) {
  return (
    <div className="space-y-3">
      <div>
        <h3 className="text-[15px] font-semibold text-[var(--text-primary)]">{title}</h3>
        {desc && <p className="mt-0.5 text-[13px] text-[var(--text-muted)]">{desc}</p>}
      </div>
      {children}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Clash Proxy Settings                                                */
/* ------------------------------------------------------------------ */
export default function ClashProxySettings() {
  const [status, setStatus] = useState<any>(null)
  const [nodes, setNodes] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [testing, setTesting] = useState(false)
  const [delayTesting, setDelayTesting] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  const [form, setForm] = useState({
    clash_api_url: 'http://127.0.0.1:9097',
    clash_secret: '123456',
    clash_proxy_host: '127.0.0.1',
    clash_proxy_port: '7897',
    clash_strategy: 'global',
    clash_max_fails: '3',
    clash_group: 'GLOBAL',
  })

  useEffect(() => {
    loadConfig()
    loadStatus()
  }, [])

  const loadConfig = async () => {
    try {
      const cfg = await apiFetch('/clash/config')
      if (cfg) {
        setForm((prev) => ({
          ...prev,
          clash_api_url: cfg.clash_api_url || prev.clash_api_url,
          clash_secret: cfg.clash_secret || prev.clash_secret,
          clash_proxy_host: cfg.clash_proxy_host || prev.clash_proxy_host,
          clash_proxy_port: String(cfg.clash_proxy_port || prev.clash_proxy_port),
          clash_strategy: cfg.clash_strategy || prev.clash_strategy,
          clash_max_fails: String(cfg.clash_max_fails || prev.clash_max_fails),
          clash_group: cfg.clash_group || prev.clash_group,
        }))
      }
    } catch {
      // 使用默认值
    }
  }

  const loadStatus = async () => {
    setLoading(true)
    try {
      const s = await apiFetch('/clash/status')
      setStatus(s)
      if (s.connected) {
        const n = await apiFetch('/clash/nodes?test_delay=false')
        setNodes(n || [])
      }
    } catch {
      setStatus(null)
    } finally {
      setLoading(false)
    }
  }

  const testConnection = async () => {
    setTesting(true)
    try {
      const r = await apiFetch('/clash/test', { method: 'POST' })
      setStatus((prev: any) => ({ ...prev, ...r }))
    } catch {
      setStatus((prev: any) => ({ ...prev, connected: false }))
    } finally {
      setTesting(false)
    }
  }

  const saveConfig = async () => {
    setSaving(true)
    try {
      await apiFetch('/clash/config', {
        method: 'PUT',
        body: JSON.stringify({
          ...form,
          clash_proxy_port: parseInt(form.clash_proxy_port) || 7890,
          clash_max_fails: parseInt(form.clash_max_fails) || 3,
        }),
      })
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
      loadStatus()
    } finally {
      setSaving(false)
    }
  }

  const testDelays = async () => {
    setDelayTesting(true)
    try {
      const n = await apiFetch('/clash/nodes?test_delay=true')
      setNodes(n || [])
    } finally {
      setDelayTesting(false)
    }
  }

  const switchNode = async (nodeName: string) => {
    try {
      await apiFetch('/clash/switch', {
        method: 'POST',
        body: JSON.stringify({ group: form.clash_group, node: nodeName }),
      })
      loadStatus()
    } catch (e) {
      console.error(e)
    }
  }

  const set = (k: string, v: string) => setForm((f) => ({ ...f, [k]: v }))

  const Input = ({ label, k, type = 'text', placeholder = '' }: any) => (
    <div className="flex items-center justify-between gap-4 px-4 py-3.5 border-b border-[var(--border)]/50 last:border-0">
      <label className="shrink-0 text-sm font-medium text-[var(--text-secondary)]">{label}</label>
      <input
        type={type}
        value={(form as any)[k]}
        onChange={(e) => set(k, e.target.value)}
        placeholder={placeholder}
        className="control-surface max-w-[280px]"
      />
    </div>
  )

  const Select = ({ label, k, options }: any) => (
    <div className="flex items-center justify-between gap-4 px-4 py-3.5 border-b border-[var(--border)]/50 last:border-0">
      <label className="shrink-0 text-sm font-medium text-[var(--text-secondary)]">{label}</label>
      <select
        value={(form as any)[k]}
        onChange={(e) => set(k, e.target.value)}
        className="control-surface max-w-[280px] appearance-none"
      >
        {options.map(([v, l]: any) => (
          <option key={v} value={v}>{l}</option>
        ))}
      </select>
    </div>
  )

  const connected = status?.connected
  const nodeCount = status?.node_count ?? nodes.length

  return (
    <div className="space-y-8">
      {/* Connection Status */}
      <SettingGroup title="连接状态" desc="Clash 外部控制 API 连接状态与当前节点。">
        <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-card)] p-4">
          <div className="flex items-center gap-4 flex-wrap">
            <div className="flex items-center gap-2">
              {connected === null ? (
                <Activity className="h-5 w-5 text-[var(--text-muted)]" />
              ) : connected ? (
                <Wifi className="h-5 w-5 text-emerald-400" />
              ) : (
                <WifiOff className="h-5 w-5 text-red-400" />
              )}
              <span className="text-sm font-medium text-[var(--text-primary)]">
                {connected === null ? '检测中...' : connected ? '已连接' : '未连接'}
              </span>
              {connected && <Badge variant="success">{status?.mode || 'running'}</Badge>}
              {connected && !status?.proxy_ok && (
                <Badge variant="warning">代理端口未开放</Badge>
              )}
              {connected && status?.proxy_ok && (
                <Badge variant="success">代理就绪</Badge>
              )}
            </div>
            <div className="flex-1" />
            <div className="flex items-center gap-3 text-xs text-[var(--text-muted)]">
              <span>节点: <span className="text-[var(--text-primary)]">{status?.current_node || '-'}</span></span>
              <span>共 <span className="text-[var(--text-primary)]">{nodeCount}</span> 个</span>
              <span className="font-mono text-[var(--text-secondary)]">{status?.proxy_url || '-'}</span>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={testConnection} disabled={testing}>
                <RefreshCw className={`h-3.5 w-3.5 mr-1 ${testing ? 'animate-spin' : ''}`} />
                测试连接
              </Button>
              <Button variant="outline" size="sm" onClick={loadStatus} disabled={loading}>
                <RefreshCw className={`h-3.5 w-3.5 mr-1 ${loading ? 'animate-spin' : ''}`} />
                刷新
              </Button>
            </div>
          </div>
        </div>
        <p className="mt-2 text-xs text-[var(--text-muted)] leading-relaxed">
          代理仅对本应用的注册请求生效，不会修改系统代理设置或影响其他应用的网络。
        </p>
      </SettingGroup>

      <div className="border-t border-[var(--border)]" />

      {/* Config */}
      <SettingGroup title="基本配置" desc="Clash 外部控制 API 地址与本地代理端口。">
        <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-card)] divide-y divide-[var(--border)]/50">
          <Input label="Clash API URL" k="clash_api_url" placeholder="http://127.0.0.1:9097" />
          <Input label="API Secret" k="clash_secret" placeholder="123456" />
          <Input label="代理地址" k="clash_proxy_host" placeholder="127.0.0.1" />
          <Input label="代理端口" k="clash_proxy_port" type="number" placeholder="7897" />
          <Input label="节点分组" k="clash_group" placeholder="GLOBAL" />
        </div>
      </SettingGroup>

      <div className="border-t border-[var(--border)]" />

      {/* Strategy */}
      <SettingGroup title="均衡策略" desc="控制何时自动切换代理节点。">
        <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-card)] divide-y divide-[var(--border)]/50">
          <Select label="策略" k="clash_strategy" options={[
            ['global', '全局（不自动切换）'],
            ['round_robin', '轮询（每次请求切换）'],
            ['lowest_delay', '低延迟（选最快的）'],
            ['failover', '故障转移（失败 N 次后切换）'],
          ]} />
          {form.clash_strategy === 'failover' && (
            <Input label="故障阈值" k="clash_max_fails" type="number" placeholder="3" />
          )}
        </div>
      </SettingGroup>

      <div className="border-t border-[var(--border)]" />

      {/* Node List */}
      <SettingGroup title="节点列表" desc="当前分组的可用节点。点击「测延迟」并行检测所有节点延迟。">
        <Card className="overflow-hidden p-0">
          <div className="flex items-center justify-between border-b border-[var(--border)] px-4 py-2.5">
            <span className="text-sm font-medium text-[var(--text-primary)]">节点列表</span>
            <Button variant="outline" size="sm" onClick={testDelays} disabled={delayTesting}>
              <Activity className={`h-3.5 w-3.5 mr-1 ${delayTesting ? 'animate-spin' : ''}`} />
              {delayTesting ? '检测中...' : '测延迟'}
            </Button>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--border)] bg-[var(--bg-pane)]">
                  <th className="px-4 py-2.5 text-left text-xs font-medium text-[var(--text-muted)]">节点名</th>
                  <th className="px-4 py-2.5 text-left text-xs font-medium text-[var(--text-muted)]">类型</th>
                  <th className="px-4 py-2.5 text-left text-xs font-medium text-[var(--text-muted)]">延迟</th>
                  <th className="px-4 py-2.5 text-left text-xs font-medium text-[var(--text-muted)]">操作</th>
                </tr>
              </thead>
              <tbody>
                {nodes.length === 0 && (
                  <tr>
                    <td colSpan={4} className="px-4 py-8 text-center text-sm text-[var(--text-muted)]">
                      {connected ? '未获取到节点列表' : '请先确保 Clash API 已连接'}
                    </td>
                  </tr>
                )}
                {nodes.map((node: any) => (
                  <tr
                    key={node.name}
                    className={`border-b border-[var(--border)]/30 hover:bg-[var(--bg-hover)] ${
                      node.name === status?.current_node ? 'bg-[var(--accent-soft)]' : ''
                    }`}
                  >
                    <td className="px-4 py-2.5 font-medium text-[var(--text-primary)]">
                      {node.name}
                      {node.name === status?.current_node && (
                        <Badge variant="success" className="ml-2">当前</Badge>
                      )}
                    </td>
                    <td className="px-4 py-2.5 text-[var(--text-muted)]">{node.type || '-'}</td>
                    <td className="px-4 py-2.5">
                      {node.delay > 0 ? (
                        <span className={node.delay < 100 ? 'text-emerald-400' : node.delay < 300 ? 'text-amber-400' : 'text-red-400'}>
                          {node.delay}ms
                        </span>
                      ) : node.delay === -1 ? (
                        <span className="text-red-400">超时</span>
                      ) : (
                        <span className="text-[var(--text-muted)]">-</span>
                      )}
                    </td>
                    <td className="px-4 py-2.5">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => switchNode(node.name)}
                        disabled={node.name === status?.current_node}
                      >
                        <Globe className="h-3.5 w-3.5 mr-1" />
                        切换
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </SettingGroup>

      <Button onClick={saveConfig} disabled={saving} className="w-full">
        <Save className="mr-2 h-4 w-4" />
        {saved ? '已保存 ✓' : saving ? '保存中...' : '保存设置'}
      </Button>
    </div>
  )
}
