import { useState } from "react"
import { pages } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"

type Res = { status: string; count: number; err?: string }

function flashText(r: Res): string {
  if (r.status === "ingested") return `✅ 收進了（${r.count} 塊，聊天時能引用）`
  if (r.status === "exists") return "這個已經收過了（沒重複收）"
  if (r.status === "empty") return "沒有內容"
  return "⚠ " + (r.err || "收進失敗")
}

export default function IngestPage() {
  const [msg, setMsg] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  // 貼上
  const [text, setText] = useState("")
  const [title, setTitle] = useState("")
  const [sourceUrl, setSourceUrl] = useState("")
  const [note, setNote] = useState("")
  const [clean, setClean] = useState(false)
  // URL / PDF
  const [pageUrl, setPageUrl] = useState("")
  const [pdfUrl, setPdfUrl] = useState("")
  const [pdfFile, setPdfFile] = useState<File | null>(null)

  async function run(fn: () => Promise<Res>) {
    setBusy(true); setMsg("收進中…")
    try { setMsg(flashText(await fn())) } catch { setMsg("⚠ 收進失敗") }
    setBusy(false)
  }

  async function pastePost(): Promise<Res> {
    return pages.ingestPaste({ text, title, source_url: sourceUrl, note, clean })
  }
  async function urlPost(): Promise<Res> {
    return pages.ingestUrl({ url: pageUrl, note })
  }
  async function pdfPost(): Promise<Res> {
    const fd = new FormData()
    if (pdfFile) fd.append("file", pdfFile)
    if (pdfUrl) fd.append("url", pdfUrl)
    const r = await fetch("/api/ingest/pdf", { method: "POST", body: fd })
    return r.json()
  }

  return (
    <div className="space-y-8 pb-8">
      <div>
        <h1 className="text-2xl font-bold">🌱 收進知識庫</h1>
        <p className="text-xs text-muted-foreground">貼上／PDF／網頁——收進的內容聊天時能引用（標「你收藏的」）。</p>
      </div>

      {msg && <div className="rounded-md bg-muted px-3 py-2 text-sm">{msg}</div>}

      <section className="space-y-2">
        <h2 className="text-sm font-semibold">📋 貼上內容（AI 聊天頁／文章／討論串）</h2>
        <div className="flex flex-wrap gap-2">
          <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="標題（可留空，自動用原標題）" className="flex-1" />
          <Input value={sourceUrl} onChange={(e) => setSourceUrl(e.target.value)} placeholder="原網址（可選）" className="flex-1" />
        </div>
        <Input value={note} onChange={(e) => setNote(e.target.value)} placeholder="收進原因／脈絡（可選）" />
        <Textarea value={text} onChange={(e) => setText(e.target.value)} rows={8}
                  placeholder="把內容貼進來——你可以先刪掉不要的雜訊，再收進。" />
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
        <h2 className="text-sm font-semibold">📄 收進 PDF（論文／報告）</h2>
        <input type="file" accept="application/pdf"
               onChange={(e) => setPdfFile(e.target.files?.[0] ?? null)}
               className="text-sm" />
        <div className="flex gap-2">
          <Input value={pdfUrl} onChange={(e) => setPdfUrl(e.target.value)} placeholder="或貼 PDF 網址（如 arXiv PDF）" className="flex-1" />
          <Button disabled={busy} onClick={() => run(pdfPost)}>收進 PDF</Button>
        </div>
      </section>
    </div>
  )
}
