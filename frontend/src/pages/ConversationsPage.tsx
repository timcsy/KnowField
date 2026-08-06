import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { pages, type ConvRow } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

export default function ConversationsPage() {
  const [perm, setPerm] = useState<ConvRow[]>([])
  const [temp, setTemp] = useState<ConvRow[]>([])
  const [loaded, setLoaded] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)

  const load = () =>
    pages.conversations().then((r) => {
      setPerm(r.permanent); setTemp(r.temporary); setLoaded(true)
    }).catch(() => setLoaded(true))
  useEffect(() => { load() }, [])

  async function dedupe() {
    const p = await pages.dedupePreview()
    if (p.n_extra === 0) { setMsg("沒有重複的對話。"); return }
    if (!confirm(`發現 ${p.n_extra} 份重複（${p.n_groups} 組）。併掉多餘、重指 ${p.n_roots} 條核心理解的由來？`)) return
    const r = await pages.dedupeApply()
    setMsg(`✅ 已清理：併掉 ${r.removed} 份、重指 ${r.repointed} 條由來。`)
    load()
  }

  if (!loaded) return <p className="text-sm text-muted-foreground">載入中…</p>
  return (
    <div className="space-y-5 pb-8">
      <div className="flex items-center gap-2">
        <h1 className="text-2xl font-bold">🗂️ 對話存檔</h1>
        <span className="text-sm text-muted-foreground">存下來的對話——當初怎麼想到的「由來」，隨時回來查。</span>
        {perm.length > 0 && (
          <button onClick={dedupe} className="ml-auto text-sm text-muted-foreground hover:underline">🧹 清理重複對話</button>
        )}
      </div>
      {msg && <div className="rounded-md bg-muted px-3 py-2 text-sm">{msg}</div>}

      {perm.length > 0 && (
        <section>
          <h2 className="mb-2 text-sm font-semibold text-muted-foreground">永久</h2>
          <div className="space-y-2">{perm.map((c) => <Row key={c.id} c={c} onChange={load} />)}</div>
        </section>
      )}

      {temp.length > 0 && (
        <section>
          <h2 className="mb-2 text-sm font-semibold text-muted-foreground">
            暫存 <span className="font-normal text-xs">（自動存、7 天沒碰會清；想留就「📌 轉永久」）</span>
          </h2>
          <div className="space-y-2 opacity-80">{temp.map((c) => <Row key={c.id} c={c} onChange={load} temp />)}</div>
        </section>
      )}

      {perm.length === 0 && temp.length === 0 && (
        <p className="text-sm text-muted-foreground">還沒存過對話。到「跟知識聊」聊一段——會自動暫存。</p>
      )}
    </div>
  )
}

function Row({ c, onChange, temp }: { c: ConvRow; onChange: () => void; temp?: boolean }) {
  const [renaming, setRenaming] = useState(false)
  const [title, setTitle] = useState(c.title)
  async function rename() { await pages.renameConv(c.id, title); setRenaming(false); onChange() }
  async function promote() { await pages.promoteConv(c.id); onChange() }
  return (
    <div className="group rounded-xl bg-card px-4 py-3 shadow-sm">
      <div className="flex flex-wrap items-center gap-2">
        <Link to={`/?resume=${c.id}`} className="font-medium hover:underline">{c.title || "（未命名對話）"}</Link>
        {temp && <Button size="sm" variant="ghost" onClick={promote} title="轉為永久保存">📌 轉永久</Button>}
        {renaming ? (
          <span className="ml-auto flex items-center gap-1">
            <Input value={title} onChange={(e) => setTitle(e.target.value)} className="h-7 w-40" placeholder="改名…" />
            <Button size="sm" onClick={rename}>存</Button>
          </span>
        ) : (
          <button onClick={() => setRenaming(true)}
                  className="ml-auto text-xs text-muted-foreground opacity-0 transition hover:text-foreground group-hover:opacity-100">改名</button>
        )}
      </div>
      <div className="mt-1 text-xs text-muted-foreground">
        {c.created_at.slice(0, 10)}
        {c.why_node_id && <span className="ml-1 rounded bg-muted px-1 py-0.5">某條核心理解的由來</span>}
        <span className="ml-1">· {c.count} 則</span>
      </div>
    </div>
  )
}
