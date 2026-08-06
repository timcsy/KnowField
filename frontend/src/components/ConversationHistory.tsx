import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { pages, type ConvRow } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

// 對話頁的歷史側欄（桌面固定、手機抽屜共用）：列永久＋暫存對話，點一則＝接著聊。
export function ConversationHistory({
  currentId, onResume, onNew, refreshKey, onClose,
}: {
  currentId: number | null
  onResume: (id: number) => void
  onNew: () => void
  refreshKey: number
  onClose?: () => void
}) {
  const [perm, setPerm] = useState<ConvRow[]>([])
  const [temp, setTemp] = useState<ConvRow[]>([])
  const [msg, setMsg] = useState<string | null>(null)

  const load = () =>
    pages.conversations().then((r) => { setPerm(r.permanent); setTemp(r.temporary) }).catch(() => {})
  useEffect(() => { load() }, [refreshKey])

  async function dedupe() {
    const p = await pages.dedupePreview()
    if (p.n_extra === 0) { setMsg("沒有重複的對話。"); return }
    if (!confirm(`發現 ${p.n_extra} 份重複（${p.n_groups} 組）。併掉多餘、重指 ${p.n_roots} 條核心理解的由來？`)) return
    const r = await pages.dedupeApply()
    setMsg(`✅ 併掉 ${r.removed} 份、重指 ${r.repointed} 條由來。`)
    load()
  }

  const pick = (id: number) => { onResume(id); onClose?.() }

  return (
    <div className="flex h-full flex-col gap-2 p-2">
      <div className="flex items-center gap-1">
        <Button size="sm" className="flex-1" onClick={() => { onNew(); onClose?.() }}>＋ 新對話</Button>
        {onClose && <Button size="sm" variant="ghost" onClick={onClose} aria-label="關閉">✕</Button>}
      </div>
      {(perm.length > 0 || temp.length > 0) && (
        <button onClick={dedupe} className="self-start px-1 text-xs text-muted-foreground hover:underline">🧹 清理重複</button>
      )}
      {msg && <div className="rounded-md bg-muted px-2 py-1 text-xs">{msg}</div>}

      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto">
        {perm.length === 0 && temp.length === 0 && (
          <p className="px-1 text-xs text-muted-foreground">還沒有對話。聊一段會自動暫存到這裡。</p>
        )}
        {perm.length > 0 && (
          <Section title="永久">
            {perm.map((c) => <Row key={c.id} c={c} active={c.id === currentId} onPick={pick} onChange={load} />)}
          </Section>
        )}
        {temp.length > 0 && (
          <Section title="暫存（7 天沒碰會清）">
            {temp.map((c) => <Row key={c.id} c={c} active={c.id === currentId} onPick={pick} onChange={load} temp />)}
          </Section>
        )}
      </div>
    </div>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h3 className="mb-1 px-1 text-[11px] font-semibold uppercase text-muted-foreground">{title}</h3>
      <div className="space-y-0.5">{children}</div>
    </section>
  )
}

function Row({ c, active, onPick, onChange, temp }: {
  c: ConvRow; active: boolean; onPick: (id: number) => void; onChange: () => void; temp?: boolean
}) {
  const [renaming, setRenaming] = useState(false)
  const [title, setTitle] = useState(c.title)
  async function rename() { await pages.renameConv(c.id, title); setRenaming(false); onChange() }
  async function promote() { await pages.promoteConv(c.id); onChange() }

  if (renaming) return (
    <div className="flex items-center gap-1 px-1 py-1">
      <Input value={title} onChange={(e) => setTitle(e.target.value)} className="h-7" placeholder="改名…" autoFocus />
      <Button size="sm" onClick={rename}>存</Button>
    </div>
  )
  return (
    <div className={`group flex items-center gap-1 rounded-lg px-2 py-1.5 hover:bg-sidebar-accent ${active ? "bg-sidebar-accent" : ""}`}>
      <button onClick={() => onPick(c.id)} className="min-w-0 flex-1 text-left" title="接著聊">
        <div className="truncate text-sm">{c.title || "（未命名對話）"}</div>
        <div className="text-[11px] text-muted-foreground">
          {c.created_at.slice(0, 10)} · {c.count} 則
          {c.why_node_id && <span className="ml-1">· 由來</span>}
        </div>
      </button>
      <div className="flex shrink-0 items-center gap-1 text-xs text-muted-foreground opacity-0 transition group-hover:opacity-100">
        <Link to={`/conversations/${c.id}`} className="hover:text-foreground" title="唯讀檢視">檢視</Link>
        {temp && <button onClick={promote} className="hover:text-foreground" title="轉為永久保存">📌</button>}
        <button onClick={() => setRenaming(true)} className="hover:text-foreground" title="改名">✎</button>
      </div>
    </div>
  )
}
