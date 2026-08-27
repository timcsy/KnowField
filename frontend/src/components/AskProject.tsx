import { useEffect, useState } from "react"
import { pages, type BaseAsk, type BaseCorpus } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

// spec 076：站在某個專案裡，問它的 knowledge/。
// ⚠️ **這是換一個場，不是把外部知識放進你的場**——切回互動模式就問不到了。
// ⚠️ 而**哪幾層進了語料一定要說**：說不出來的話，「答不出來」會被讀成「它不知道」。

const LABEL: Record<string, string> = {
  experience: "經驗", concepts: "概念", principles: "原則", vision: "路線圖",
  history: "轉移", episodes: "場景", draft: "draft", skills: "skills", other: "其他",
}

export function AskProject({ bid, onOpen }: { bid: number; onOpen: (iid: number) => void }) {
  const [c, setC] = useState<BaseCorpus | null>(null)
  const [q, setQ] = useState("")
  const [r, setR] = useState<BaseAsk | null>(null)
  const [busy, setBusy] = useState(false)
  useEffect(() => { setR(null); setC(null); pages.baseCorpus(bid).then(setC).catch(() => {}) }, [bid])

  async function ask() {
    if (!q.trim() || busy) return
    setBusy(true); setR(null)
    try { setR(await pages.baseAsk(bid, q.trim())) } finally { setBusy(false) }
  }
  const missing = Object.keys(c?.layers ?? {}).length === 0

  return (
    <section className="space-y-2 border-b px-4 py-3 md:px-6">
      <div className="flex flex-wrap gap-2">
        <Input value={q} onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.nativeEvent.isComposing) ask() }}
          placeholder="在這個專案的知識庫裡找⋯（例：它對測試假綠有什麼判準？）"
          className="min-w-48 flex-1" />
        <Button size="sm" disabled={busy || !q.trim()} onClick={ask}>{busy ? "找…" : "問"}</Button>
      </div>

      {/* ⚠️ 一定先講清楚它讀得到什麼——不然「沒有」會被當成「它不知道」 */}
      <p className="text-xs text-muted-foreground">
        {c === null ? "…" : missing
          ? "還沒建立索引——問一次就會自動建（大的專案要一兩分鐘）。"
          : <>讀得到：{c.in_corpus.map((k) => `${LABEL[k] || k}${c.layers[k] ? ` ${c.layers[k]}` : " 0"}`).join("・")}
              <span className="mx-1">·</span>共 {c.n_chunks} 段。
              <b className="ml-1">轉移／場景／draft 不在裡面</b>——那些是場景與未定的，不是判準。</>}
      </p>

      {r && (r.hits?.length ? (
        <ul className="space-y-1.5 border-t pt-2">
          {/* ⚠️ 這是**相關的段落**，不是答案——所以每一段都標出處，由你判斷。
              實測沒有一個門檻切得掉「技術性但不在這個 base」的問題。 */}
          {r.hits.map((h, i) => (
            <li key={i} className="text-xs">
              <button onClick={() => onOpen(0)} className="mr-2 rounded bg-muted px-1.5 py-0.5 hover:bg-muted/70">
                {h.path.replace(/^knowledge\//, "")}#{h.seq}
              </button>
              <span className="text-muted-foreground">{h.text.replace(/\s+/g, " ").slice(0, 160)}…</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="border-t pt-2 text-xs text-muted-foreground">
          {r.indexing ? "正在建索引，等一下再問一次。"
            : r.error ? r.error
            : "這個專案的知識庫裡沒有相關的段落。"}
        </p>
      ))}
    </section>
  )
}
