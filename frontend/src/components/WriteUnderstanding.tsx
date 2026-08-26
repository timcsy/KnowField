import { useEffect, useState } from "react"
import { pages, type ConvRow, type SourceGroup } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { useCurrentDomain } from "@/lib/domain"

// spec 062：人自己寫一條理解。
//
// ⚠️ **出處必填是原則問題，不是體驗問題**：AI 蒸餾的候選會經過 gradient oracle
// （原則 5 要它對自己 adversarial，防 folie à deux），人自己寫**跳過了那道檢查**
// ⇒ 出處是它的替代品。所以這裡不做「先存起來之後再補」。
//
// ⚠️ 第四個選項（沒有外部依據）**不是逃生門**——它是信任鏈的第三種終點，
// 要被**宣告**、被記下來。它跟「欄位忘了填」在資料上長得一樣，所以必須是一個明確的選擇。
type Basis = "conversation" | "source" | "url" | "judgment"

export function WriteUnderstanding({ onDone }: { onDone: () => void }) {
  const { did } = useCurrentDomain()
  const [open, setOpen] = useState(false)
  const [claim, setClaim] = useState("")
  const [kind, setKind] = useState("推論")
  const [ladder, setLadder] = useState("")
  const [basis, setBasis] = useState<Basis>("conversation")
  const [convId, setConvId] = useState(0)
  const [srcUrl, setSrcUrl] = useState("")
  const [url, setUrl] = useState("")
  const [convs, setConvs] = useState<ConvRow[]>([])
  const [srcs, setSrcs] = useState<SourceGroup[]>([])
  const [msg, setMsg] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!open) return
    pages.conversations().then((r) => setConvs(r.conversations || [])).catch(() => {})
    pages.library().then((r) => setSrcs(r.sources || [])).catch(() => {})
  }, [open])

  async function submit() {
    if (!claim.trim() || busy) return
    setBusy(true); setMsg(null)
    const p: Parameters<typeof pages.writeUnderstanding>[0] = {
      claim: claim.trim(), kind, ladder, domain_id: did,
    }
    if (basis === "conversation") p.conversation_id = convId
    else if (basis === "source") p.source_url = srcUrl
    else if (basis === "url") p.evidence_urls = url
    else p.origin = "self:judgment"
    try {
      const r = await pages.writeUnderstanding(p)
      setBusy(false)
      if (r.error) { setMsg(r.error); return }        // ⚠️ 後端擋下來的話照原話顯示
      setClaim(""); setLadder(""); setOpen(false); onDone()
      // 側欄的件數也要跟著動——不然「理解 34」在你剛存完之後還說 34。
      // ⓘ 沿用既有事件名（它其實是「知識變了」，不只是對話）：改名要動好幾個檔而且零功能收益。
      window.dispatchEvent(new Event("kf-conversations-changed"))
    } catch { setBusy(false); setMsg("存不進去，稍後再試。") }
  }

  if (!open) {
    return (
      <Button variant="outline" size="sm" onClick={() => setOpen(true)}>
        ✍️ 自己寫一條
      </Button>
    )
  }

  return (
    <section className="w-full space-y-3 rounded-xl border bg-card p-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold">✍️ 自己寫一條理解</h2>
        <button onClick={() => { setOpen(false); setMsg(null) }}
                className="text-xs text-muted-foreground hover:text-foreground">收起</button>
      </div>
      <p className="text-xs text-muted-foreground">
        已經知道的事不必先聊一輪。<b className="text-foreground">但要標出處</b>
        ——AI 提的候選會先被反駁一次，自己寫的沒有，出處是那道檢查的替代品。
      </p>

      <textarea value={claim} onChange={(e) => setClaim(e.target.value)} rows={2}
                placeholder="一句你想長期留著的主張"
                className="w-full rounded-md border bg-background px-3 py-2 text-sm" />

      <div className="flex flex-wrap items-center gap-2 text-sm">
        <label className="text-xs text-muted-foreground">這條有多確定</label>
        <select value={kind} onChange={(e) => setKind(e.target.value)}
                className="rounded-md border bg-background px-2 py-1 text-sm">
          <option>已證實</option><option>推論</option><option>類比</option><option>猜想</option>
        </select>
        <span className="text-xs text-muted-foreground">（AI 生的會自己判，自己寫的要自己標）</span>
      </div>

      <textarea value={ladder} onChange={(e) => setLadder(e.target.value)} rows={2}
                placeholder="為什麼？（選填，一行一層）"
                className="w-full rounded-md border bg-background px-3 py-2 text-sm" />

      <div className="space-y-2 rounded-lg border border-dashed p-3">
        <div className="text-xs font-medium">出處（必填）</div>
        {([
          ["conversation", "💬 某段互動"],
          ["source", "📚 某份來源"],
          ["url", "🔗 一個網址"],
          ["judgment", "🧠 這是我自己的判斷，沒有外部依據"],
        ] as [Basis, string][]).map(([v, label]) => (
          <label key={v} className="flex items-center gap-2 text-sm">
            <input type="radio" checked={basis === v} onChange={() => setBasis(v)} />
            <span>{label}</span>
          </label>
        ))}
        {basis === "conversation" && (
          <select value={convId} onChange={(e) => setConvId(Number(e.target.value))}
                  className="w-full rounded-md border bg-background px-2 py-1 text-sm">
            <option value={0}>選一段…</option>
            {convs.map((c) => <option key={c.id} value={c.id}>{c.title || `互動 #${c.id}`}</option>)}
          </select>
        )}
        {basis === "source" && (
          <select value={srcUrl} onChange={(e) => setSrcUrl(e.target.value)}
                  className="w-full rounded-md border bg-background px-2 py-1 text-sm">
            <option value="">選一份…</option>
            {srcs.map((s) => <option key={s.url} value={s.url}>{s.title || s.url}</option>)}
          </select>
        )}
        {basis === "url" && (
          <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://…"
                 className="w-full rounded-md border bg-background px-2 py-1 text-sm" />
        )}
        {basis === "judgment" && (
          <p className="text-xs text-muted-foreground">
            會標成「個人判斷」——那是信任鏈的一種終點，讀的人看得出這條沒有外部依據。
          </p>
        )}
      </div>

      {msg && <p className="text-xs text-destructive">{msg}</p>}
      <Button size="sm" onClick={submit} disabled={busy || !claim.trim()}>
        {busy ? "存入中…" : "存進知識庫"}
      </Button>
    </section>
  )
}
