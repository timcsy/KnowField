import { useEffect, useState } from "react"
import { Link, useSearchParams } from "react-router-dom"
import { pages, type WhyNode } from "@/lib/api"
import { Markdown } from "@/components/Markdown"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"

type Src = { found: boolean; url: string; title: string; markdown: string; note: string; ingested_at: string }
const KINDS = ["已證實", "推論", "類比", "猜想"]

export default function SourcePage() {
  const [sp] = useSearchParams()
  const u = sp.get("u") || ""
  const [src, setSrc] = useState<Src | null>(null)
  const [note, setNote] = useState("")
  const [at, setAt] = useState("")
  const [msg, setMsg] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [cands, setCands] = useState<WhyNode[]>([])

  // 這份來源蒸餾出的候選（evidence_urls 帶著來源網址）→ 直接在這頁精選
  const loadCands = () =>
    pages.roots().then((r) => setCands(r.candidates.filter((c) => c.evidence_urls.includes(u)))).catch(() => {})

  useEffect(() => {
    pages.source(u).then((s) => { setSrc(s); setNote(s.note || ""); setAt(s.ingested_at || "") }).catch(() => {})
    loadCands()
  }, [u])

  async function saveMeta() {
    await pages.sourceMeta(u, note, at)
    setMsg("已存脈絡")
  }
  async function distill() {
    setBusy(true); setMsg("整理中…")
    const r = await pages.sourceDistill(u)
    setBusy(false)
    setMsg(r.ok ? "整理出候選了——在下面挑要精選的（順便標層次）。" : r.err || "整理失敗")
    if (r.ok) loadCands()
  }

  if (!src) return <p className="text-sm text-muted-foreground">載入中…</p>
  if (!src.found)
    return (
      <p className="text-sm text-muted-foreground">
        找不到這份來源。<Link to="/sources" className="text-primary hover:underline">← 來源</Link>
      </p>
    )

  return (
    <div className="space-y-4 pb-8">
      <div>
        <Link to="/sources" className="text-sm text-muted-foreground hover:underline">← 來源</Link>
        <h1 className="mt-1 text-2xl font-bold">{src.title}</h1>
        {src.url.startsWith("http") && (
          <a href={src.url} target="_blank" rel="noopener" className="break-all text-xs text-primary hover:underline">{src.url}</a>
        )}
        <p className="mt-1 text-xs text-muted-foreground">收進的原文（供回顧）；聊天引用時會標「📎 你收藏的」。</p>

        <div className="mt-2 flex flex-wrap items-center gap-2 text-sm">
          <span>📌</span>
          <Input value={note} onChange={(e) => setNote(e.target.value)}
                 placeholder="收進原因／脈絡（為何存它）" className="w-72 max-w-full" />
          <span>🗓</span>
          <Input value={at} onChange={(e) => setAt(e.target.value)} placeholder="日期（可大概）" className="w-36" />
          <Button size="sm" variant="ghost" onClick={saveMeta}>存</Button>
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <Button size="sm" disabled={busy} onClick={distill}>🧠 整理成核心理解</Button>
          <span className="text-xs text-muted-foreground">AI 從這份來源抽候選，你在下面挑認同的收進——不會自動變地基。</span>
        </div>
        {msg && <div className="mt-2 rounded-md bg-muted px-3 py-2 text-sm">{msg}</div>}
      </div>

      {/* 這份來源的候選——直接在這裡精選（不用跳到核心理解頁） */}
      {cands.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-sm font-semibold">整理出這幾條——挑要精選的（你決定，順便標層次）</h2>
          {cands.map((c) => <SourceCandidateCard key={c.id} w={c} onDone={loadCands} />)}
        </section>
      )}

      <div className="rounded-xl bg-card p-4 shadow-sm">
        <Markdown text={src.markdown} prefix="src" />
      </div>
    </div>
  )
}

function SourceCandidateCard({ w, onDone }: { w: WhyNode; onDone: () => void }) {
  const [claim, setClaim] = useState(w.claim)
  const [kind, setKind] = useState(w.kind || "")
  const [done, setDone] = useState(false)

  async function anoint() { await pages.whynodeAnoint(w.id, claim, kind); setDone(true); onDone() }
  async function remove() { if (confirm("退回這條候選？")) { await pages.whynodeRemove(w.id); onDone() } }

  if (done) return <div className="rounded-xl border bg-card p-3 text-sm text-primary">✅ 已精選收進核心理解</div>
  return (
    <div className="space-y-2 rounded-xl border bg-card p-4">
      <div className="flex items-center gap-2">
        <span className="shrink-0 rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">候選</span>
        <Input value={claim} onChange={(e) => setClaim(e.target.value)} className="flex-1 font-medium" />
      </div>
      {w.ladder.length > 0 && (
        <ol className="ml-1 space-y-0.5 border-l-2 pl-3 text-xs text-muted-foreground">
          {w.ladder.map((s, i) => (
            <li key={i}>{i === w.ladder.length - 1 ? <b className="text-foreground">↓ 最底層：</b> : "↓ "}{s}</li>
          ))}
        </ol>
      )}
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="text-xs text-muted-foreground">層次：</span>
        {KINDS.map((k) => (
          <button key={k} onClick={() => setKind(kind === k ? "" : k)}
                  className={cn("rounded px-2 py-0.5 text-xs transition",
                    kind === k ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground hover:text-foreground")}>
            {k}
          </button>
        ))}
      </div>
      <div className="flex gap-2">
        <Button size="sm" onClick={anoint}>精選</Button>
        <Button size="sm" variant="ghost" onClick={remove}>退回</Button>
      </div>
    </div>
  )
}
