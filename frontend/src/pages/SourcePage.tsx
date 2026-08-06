import { useEffect, useState } from "react"
import { Link, useSearchParams } from "react-router-dom"
import { pages } from "@/lib/api"
import { Markdown } from "@/components/Markdown"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

type Src = { found: boolean; url: string; title: string; markdown: string; note: string; ingested_at: string }

export default function SourcePage() {
  const [sp] = useSearchParams()
  const u = sp.get("u") || ""
  const [src, setSrc] = useState<Src | null>(null)
  const [note, setNote] = useState("")
  const [at, setAt] = useState("")
  const [msg, setMsg] = useState<string | null>(null)

  useEffect(() => {
    pages.source(u).then((s) => {
      setSrc(s)
      setNote(s.note || "")
      setAt(s.ingested_at || "")
    }).catch(() => {})
  }, [u])

  async function saveMeta() {
    await pages.sourceMeta(u, note, at)
    setMsg("已存脈絡")
  }
  async function distill() {
    setMsg("整理中…")
    const r = await pages.sourceDistill(u)
    setMsg(r.ok ? "已整理出候選——到「核心理解」頁精選你認同的。" : r.err || "整理失敗")
  }

  if (!src) return <p className="text-sm text-muted-foreground">載入中…</p>
  if (!src.found)
    return (
      <p className="text-sm text-muted-foreground">
        找不到這份來源。<Link to="/library" className="text-primary hover:underline">← 知識庫</Link>
      </p>
    )

  return (
    <div className="space-y-4 pb-8">
      <div>
        <Link to="/library" className="text-sm text-muted-foreground hover:underline">← 知識庫</Link>
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
          <Button size="sm" onClick={distill}>🧠 整理成核心理解</Button>
          <span className="text-xs text-muted-foreground">AI 從這份來源抽候選，你到「核心理解」挑認同的收進——不會自動變地基。</span>
        </div>
        {msg && <div className="mt-2 rounded-md bg-muted px-3 py-2 text-sm">{msg}</div>}
      </div>

      <div className="rounded-xl bg-card p-4 shadow-sm">
        <Markdown text={src.markdown} prefix="src" />
      </div>
    </div>
  )
}
