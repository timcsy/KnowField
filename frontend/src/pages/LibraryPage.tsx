import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { pages, type SourceGroup } from "@/lib/api"

export default function LibraryPage() {
  const [sources, setSources] = useState<SourceGroup[] | null>(null)
  const load = () => pages.library().then((r) => setSources(r.sources)).catch(() => {})
  useEffect(() => { load() }, [])

  async function reclassify(s: SourceGroup) {
    await pages.reclassify(s.url, s.source_class === "explainer" ? "ordinary" : "explainer")
    load()
  }
  async function remove(url: string) {
    if (!confirm("刪除整份來源？（所有塊、不可復原）")) return
    await pages.removeSource(url)
    load()
  }

  if (!sources) return <p className="text-sm text-muted-foreground">載入中…</p>
  return (
    <div className="space-y-4 pb-8">
      <div>
        <h1 className="text-2xl font-bold">📚 我的知識庫</h1>
        <p className="text-xs text-muted-foreground">你收進的來源（可檢視／刪除／重分類）。</p>
      </div>
      {sources.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          知識庫還沒有東西。到「<Link to="/ingest" className="text-primary hover:underline">收進</Link>」貼一段、收個 PDF 或網頁吧。
        </p>
      ) : (
        <div className="space-y-2">
          {sources.map((s) => (
            <div key={s.url} className="group flex items-start justify-between gap-3 rounded-xl bg-card px-4 py-3 shadow-sm">
              <div className="min-w-0">
                <div className="font-medium">
                  <Link to={`/source?u=${encodeURIComponent(s.url)}`} className="hover:underline">{s.title}</Link>
                  {s.count > 1 && <span className="ml-1 text-xs text-muted-foreground">· {s.count} 塊</span>}
                  <span className="ml-2 rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">
                    {s.source_class === "explainer" ? "解說文" : "一般"}
                  </span>
                </div>
                <div className="mt-0.5 break-all text-xs text-muted-foreground">
                  {s.ingested_at && <span className="mr-2">🗓 {s.ingested_at}</span>}
                  {s.url.startsWith("http") ? (
                    <a href={s.url} target="_blank" rel="noopener" className="text-primary hover:underline">{s.url}</a>
                  ) : (
                    <span className="opacity-60">{s.url}</span>
                  )}
                </div>
                {s.note && <div className="mt-0.5 text-xs text-muted-foreground">📌 {s.note}</div>}
              </div>
              <div className="flex shrink-0 items-center gap-3 text-xs text-muted-foreground opacity-0 transition group-hover:opacity-100">
                <Link to={`/source?u=${encodeURIComponent(s.url)}`} className="hover:text-foreground">檢視</Link>
                <button onClick={() => reclassify(s)} className="hover:text-foreground">
                  {s.source_class === "explainer" ? "改一般" : "標解說文"}
                </button>
                <button onClick={() => remove(s.url)} className="hover:text-destructive">刪除</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
