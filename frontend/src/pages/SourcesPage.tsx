import { useEffect, useRef, useState } from "react"
import { Link } from "react-router-dom"
import { useCurrentDomain } from "@/lib/domain"
import { useScope } from "@/lib/scope"
import { pages, type SourceGroup } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

type Res = { status: string; count: number; err?: string }

function flashText(r: Res): string {
  if (r.status === "ingested") return `✅ 收進了（${r.count} 塊，聊天時能引用）`
  if (r.status === "exists") return "這個已經收過了（沒重複收）"
  if (r.status === "empty") return "沒有內容"
  return "⚠ " + (r.err || "收進失敗")
}

// 來源＝外部資料的一站：上方「＋收進」展開表單，下方已收進來源列表（原「知識庫」＋「收進」合併）。
export default function SourcesPage() {
  const { did } = useCurrentDomain()   // 收進來的來源生在你站的地方（spec 052 FR-006）
  const [allSources, setAllSources] = useState<SourceGroup[] | null>(null)
  // ⚠️ 來源的身分是 **url**，不是 id（一個來源＝多個塊）
  const { inScope, banner } = useScope("source")
  const sources = allSources === null ? null : allSources.filter((x) => inScope(x.url))
  const [showIngest, setShowIngest] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  // 貼上（rich-paste：contenteditable 收 HTML＋圖片）
  const pasteRef = useRef<HTMLDivElement>(null)
  const [title, setTitle] = useState("")
  const [sourceUrl, setSourceUrl] = useState("")
  const [note, setNote] = useState("")
  const [clean, setClean] = useState(false)
  const [pageUrl, setPageUrl] = useState("")
  const [ytUrl, setYtUrl] = useState("")
  const [pdfUrl, setPdfUrl] = useState("")
  const [pdfFile, setPdfFile] = useState<File | null>(null)
  const [paperUrl, setPaperUrl] = useState("")

  const load = () => pages.library().then((r) => setAllSources(r.sources)).catch(() => {})
  useEffect(() => { load() }, [])

  async function run(fn: () => Promise<Res>) {
    setBusy(true); setMsg("收進中…")
    try {
      const r = await fn()
      setMsg(flashText(r))
      if (r.status === "ingested") { load() }   // 收進成功→刷新列表
    } catch { setMsg("⚠ 收進失敗") }
    setBusy(false)
  }
  async function pastePost(): Promise<Res> {
    const el = pasteRef.current
    return pages.ingestPaste({
      domain_id: did,
      text: el?.innerText || "", html: el?.innerHTML || "",
      title, source_url: sourceUrl, note, clean,
    })
  }
  async function urlPost(): Promise<Res> { return pages.ingestUrl({ url: pageUrl, note, domain_id: did }) }
  async function paperPost(): Promise<Res> {
    // 論文走 ingestUrl（後端 normalize：arXiv abs/pdf→HTML＋Abstract/PDF 加料）。純 id→補成 abs 網址。
    const v = paperUrl.trim()
    const url = /^\d+\.\d+(v\d+)?$/.test(v) ? `https://arxiv.org/abs/${v}` : v
    return pages.ingestUrl({ url, note, domain_id: did })
  }
  async function ytPost(): Promise<Res> { return pages.ingestYoutube({ url: ytUrl, domain_id: did }) }
  async function pdfPost(): Promise<Res> {
    const fd = new FormData()
    if (pdfFile) fd.append("file", pdfFile)
    if (pdfUrl) fd.append("url", pdfUrl)
    const r = await fetch("/api/ingest/pdf", { method: "POST", body: fd })
    return r.json()
  }

  async function reclassify(s: SourceGroup) {
    await pages.reclassify(s.url, s.source_class === "explainer" ? "ordinary" : "explainer")
    load()
  }
  async function remove(url: string) {
    if (!confirm("刪除整份來源？（所有塊、不可復原）")) return
    await pages.removeSource(url)
    load()
  }

  return (
    <div className="space-y-5 pb-8">
      {banner}
      <div className="flex items-center gap-2">
        <h1 className="text-2xl font-bold">📚 來源</h1>
        <span className="hidden text-sm text-muted-foreground sm:inline">你收進的外部資料——聊天時能引用（標「你收藏的」）。</span>
        <Button size="sm" className="ml-auto" onClick={() => setShowIngest((v) => !v)}>
          {showIngest ? "收起" : "＋ 收進"}
        </Button>
      </div>

      {msg && <div className="rounded-md bg-muted px-3 py-2 text-sm">{msg}</div>}

      {showIngest && (
        <div className="space-y-6 rounded-xl border bg-card p-4">
          <section className="space-y-2">
            <h2 className="text-sm font-semibold">📋 貼上內容（AI 聊天頁／文章／討論串）</h2>
            <div className="flex flex-wrap gap-2">
              <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="標題（可留空，自動用原標題）" className="flex-1" />
              <Input value={sourceUrl} onChange={(e) => setSourceUrl(e.target.value)} placeholder="原網址（可選）" className="flex-1" />
            </div>
            <Input value={note} onChange={(e) => setNote(e.target.value)} placeholder="收進原因／脈絡（可選）" />
            <div
              ref={pasteRef}
              contentEditable
              suppressContentEditableWarning
              data-placeholder="把內容貼進來（含圖片、格式）——可先刪掉不要的雜訊，再收進。"
              className="min-h-32 rounded-md border bg-background p-3 text-[15px] leading-relaxed outline-none [&_img]:my-2 [&_img]:max-w-full [&_img]:rounded"
            />
            <div className="flex items-center gap-3">
              <Button disabled={busy} onClick={() => run(pastePost)}>收進這段</Button>
              <label className="flex items-center gap-1 text-xs text-muted-foreground">
                <input type="checkbox" checked={clean} onChange={(e) => setClean(e.target.checked)} />
                🧹 收進前用 AI 清雜訊（只剝 UI、不改寫）
              </label>
            </div>
          </section>

          <section className="space-y-2">
            <h2 className="text-sm font-semibold">🌐 收整篇網頁（開放的 Blog／文章）</h2>
            <div className="flex gap-2">
              <Input value={pageUrl} onChange={(e) => setPageUrl(e.target.value)} placeholder="貼網址（如 blog 文章）" className="flex-1" />
              <Button disabled={busy} onClick={() => run(urlPost)}>收進網頁</Button>
            </div>
          </section>

          <section className="space-y-2">
            <h2 className="text-sm font-semibold">▶️ 收進 YouTube 逐字稿</h2>
            <div className="flex gap-2">
              <Input value={ytUrl} onChange={(e) => setYtUrl(e.target.value)} placeholder="貼 YouTube 網址（抓字幕；抓不到請改用貼上）" className="flex-1" />
              <Button disabled={busy} onClick={() => run(ytPost)}>收進字幕</Button>
            </div>
          </section>

          <section className="space-y-2">
            <h2 className="text-sm font-semibold">🎓 收進論文（arXiv）</h2>
            <div className="flex gap-2">
              <Input value={paperUrl} onChange={(e) => setPaperUrl(e.target.value)}
                     placeholder="貼 arXiv 網址或 id（如 arxiv.org/abs/1706.03762 或 1706.03762）" className="flex-1" />
              <Button disabled={busy} onClick={() => run(paperPost)}>收進論文</Button>
            </div>
            <p className="text-xs text-muted-foreground">走論文管線：HTML 版（數學/圖最準）＋抓 Abstract／作者／原始 PDF → 來源頁論文展示。</p>
          </section>

          <section className="space-y-2">
            <h2 className="text-sm font-semibold">📄 收進 PDF（一般報告／檔案）</h2>
            <input type="file" accept="application/pdf"
                   onChange={(e) => setPdfFile(e.target.files?.[0] ?? null)}
                   className="text-sm" />
            <div className="flex gap-2">
              <Input value={pdfUrl} onChange={(e) => setPdfUrl(e.target.value)} placeholder="或貼 PDF 網址（非 arXiv；arXiv 論文請用上方「收進論文」）" className="flex-1" />
              <Button disabled={busy} onClick={() => run(pdfPost)}>收進 PDF</Button>
            </div>
          </section>
        </div>
      )}

      {sources === null ? (
        <p className="text-sm text-muted-foreground">載入中…</p>
      ) : sources.length === 0 ? (
        <p className="text-sm text-muted-foreground">還沒收進任何來源。按上面「＋ 收進」貼一段、收個 PDF 或網頁吧。</p>
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
