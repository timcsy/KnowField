import { useEffect, useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { pages, type ConvRow } from "@/lib/api"
import { Button } from "@/components/ui/button"

// 對話列表頁（導覽「💬 對話」的落點）：列出所有對話，點一則接著聊、或檢視。
// 開新對話走「＋新對話」（→ 聊天頁）。與側欄歷史共用 pages.conversations()＋事件同步。
export default function ConversationsPage() {
  const nav = useNavigate()
  const [perm, setPerm] = useState<ConvRow[]>([])
  const [temp, setTemp] = useState<ConvRow[]>([])
  const load = () => pages.conversations().then((r) => { setPerm(r.permanent); setTemp(r.temporary) }).catch(() => {})
  useEffect(() => {
    load()
    const h = () => load()
    window.addEventListener("kf-conversations-changed", h)
    return () => window.removeEventListener("kf-conversations-changed", h)
  }, [])

  const empty = perm.length === 0 && temp.length === 0

  return (
    <div className="space-y-6 pb-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">💬 對話</h1>
          <p className="mt-1 text-sm text-muted-foreground">你聊過的每一段——點一則接著聊，或檢視。</p>
        </div>
        <Button onClick={() => nav("/?new=" + Date.now())}>＋ 新對話</Button>
      </div>

      {empty && (
        <div className="rounded-xl border border-dashed p-10 text-center text-sm text-muted-foreground">
          還沒有對話。<button onClick={() => nav("/?new=" + Date.now())} className="text-primary hover:underline">開一段新對話</button>，聊一句就會自動暫存到這裡。
        </div>
      )}

      {perm.length > 0 && (
        <Section title="對話">
          {perm.map((c) => <Card key={c.id} c={c} onResume={() => nav(`/?resume=${c.id}`)} />)}
        </Section>
      )}
      {temp.length > 0 && (
        <Section title="暫存" hint="自動存、7 天沒碰會清；想留就到側欄 📌 轉永久">
          {temp.map((c) => <Card key={c.id} c={c} temp onResume={() => nav(`/?resume=${c.id}`)} />)}
        </Section>
      )}
    </div>
  )
}

function Section({ title, hint, children }: { title: string; hint?: string; children: React.ReactNode }) {
  return (
    <section className="space-y-2">
      <h2 title={hint} className="text-xs font-medium uppercase tracking-wide text-muted-foreground/70">{title}</h2>
      <div className="space-y-2">{children}</div>
    </section>
  )
}

function Card({ c, temp, onResume }: { c: ConvRow; temp?: boolean; onResume: () => void }) {
  return (
    <div className="group flex items-center gap-3 rounded-xl border bg-card px-4 py-3 shadow-sm transition hover:border-primary/40 hover:bg-muted/40">
      <button onClick={onResume} className="min-w-0 flex-1 text-left" title="接著聊">
        <div className="truncate font-medium">{c.title || "（未命名對話）"}</div>
        <div className="mt-0.5 flex flex-wrap gap-x-3 text-xs text-muted-foreground">
          <span>{c.created_at.slice(0, 10)}</span>
          <span>{c.count} 則</span>
          {temp && <span>暫存</span>}
          {c.why_node_id && <span>某條核心理解的由來</span>}
        </div>
      </button>
      <div className="flex shrink-0 items-center gap-3 text-xs text-muted-foreground">
        <button onClick={onResume} className="hover:text-foreground">接著聊 →</button>
        <Link to={`/conversations/${c.id}`} className="hover:text-foreground">檢視</Link>
      </div>
    </div>
  )
}
