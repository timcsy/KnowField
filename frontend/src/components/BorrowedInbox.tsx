import { useState } from "react"
import { pages, borrowedBases, type WhyNode } from "@/lib/api"
import { Button } from "@/components/ui/button"

// spec 071：跨 base 判準的**收件匣**。
// ⚠️ 形狀是「東西停在門口，直到你收進自己的場」——不是資料庫，是佇列。
// ⚠️ 每條**給原文，不給分數**：相似度只是篩子（把 1,393² 降到十分鐘看得完），
//    判準是「你能不能像肉眼校驗那樣判斷它」，而分數不可反駁。

// 一條成員 ＝ `<base>｜原文`（後端 ladder 的格式）
function member(rung: string): { base: string; text: string } {
  const i = rung.indexOf("｜")
  return i < 0 ? { base: "", text: rung } : { base: rung.slice(0, i), text: rung.slice(i + 1) }
}

function Card({ w, onDone }: { w: WhyNode; onDone: () => void }) {
  const [claim, setClaim] = useState(w.claim)
  const [busy, setBusy] = useState(false)
  const bases = borrowedBases(w.origin)
  const act = async (fn: () => Promise<unknown>) => { setBusy(true); await fn(); onDone() }
  return (
    <div className="rounded-xl border bg-card px-5 py-4">
      <div className="flex flex-wrap items-center gap-1.5 text-[11px] text-muted-foreground">
        <span title="這條不是你在這個場撞出來的——是從別的知識庫借來的">🛬 借來的</span>
        <span>· 跨 {bases.length} 個知識庫</span>
        {bases.map((b) => (
          <span key={b} className="rounded bg-muted px-1.5 py-0.5 font-medium text-foreground">{b}</span>
        ))}
      </div>
      {/* 代表句可改——合併成自己的話是**人**的事，這裡不替他合成 */}
      <textarea value={claim} onChange={(e) => setClaim(e.target.value)} rows={2}
                className="mt-2 w-full resize-y rounded-md border bg-background px-3 py-2 text-[15px] leading-loose"
                placeholder="收下時想怎麼寫它？" />
      <details className="mt-2" open>
        <summary className="cursor-pointer text-xs text-muted-foreground hover:text-foreground">
          各自的原文（{w.ladder.length}）——判斷它們是不是真的同一條
        </summary>
        <ul className="mt-1.5 space-y-1.5 border-t pt-2">
          {w.ladder.map((rung, i) => {
            const m = member(rung)
            return (
              <li key={i} className="text-xs leading-relaxed">
                {m.base && <b className="mr-1.5 text-foreground">{m.base}</b>}
                <span className="text-muted-foreground">{m.text}</span>
              </li>
            )
          })}
        </ul>
      </details>
      <div className="mt-3 flex items-center gap-3">
        <Button size="sm" disabled={busy || !claim.trim()}
                onClick={() => act(() => pages.whynodeAnoint(w.id, claim.trim()))}>收進我的場</Button>
        <button disabled={busy} onClick={() => act(() => pages.whynodeRemove(w.id))}
                title="這條不適用——它不會再出現在收件匣"
                className="text-xs text-muted-foreground hover:text-destructive">略過</button>
      </div>
    </div>
  )
}

export function BorrowedInbox({ candidates, onDone }: { candidates: WhyNode[]; onDone: () => void }) {
  const [paste, setPaste] = useState("")
  const [msg, setMsg] = useState<string | null>(null)
  const [open, setOpen] = useState(false)
  const items = candidates.filter((w) => borrowedBases(w.origin).length > 0)

  async function doImport() {
    let groups: unknown[]
    try {
      const v = JSON.parse(paste)
      groups = Array.isArray(v) ? v : (v?.groups ?? [])
      if (!Array.isArray(groups)) throw new Error()
    } catch { setMsg("讀不懂這份 JSON——要是群的陣列，或 { groups: [...] }"); return }
    const r = await pages.borrowedImport(groups)
    if (r.error) { setMsg(r.error); return }
    setPaste("")
    // ⚠️ 略過過的會被算進 skipped ⇒ 要說清楚，否則使用者以為匯入壞了
    setMsg(`收件匣多了 ${r.added} 條${r.skipped ? `；${r.skipped} 條跳過（已經收過或略過過的）` : ""}`)
    onDone()
  }

  if (items.length === 0 && !open) {
    return (
      <button onClick={() => setOpen(true)}
              className="text-xs text-muted-foreground hover:text-foreground hover:underline">
        🛬 從別的知識庫收判準…
      </button>
    )
  }
  return (
    <section className="space-y-3 rounded-xl border bg-card p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold">🛬 從別的知識庫來的判準（{items.length}）</h2>
          <p className="text-xs text-muted-foreground">
            幾個獨立的知識庫各自撞出同一條——所以它值得你看一眼。
            一條一條看，收進來的才進你的場。
          </p>
        </div>
        <button onClick={() => setOpen(!open)} className="text-xs text-muted-foreground hover:text-foreground">
          {open ? "收起匯入" : "匯入…"}
        </button>
      </div>
      {open && (
        <div className="space-y-2 rounded-lg border bg-background p-3">
          <p className="text-xs text-muted-foreground">
            在有那些知識庫的機器上跑 <code className="rounded bg-muted px-1">knowie-crosscheck</code>，把它印出來的 JSON 貼進來。
          </p>
          <textarea value={paste} onChange={(e) => setPaste(e.target.value)} rows={4}
                    className="w-full resize-y rounded-md border bg-background px-3 py-2 font-mono text-xs"
                    placeholder='{"groups": [{"claim": "…", "members": [{"base": "VizGPT", "text": "…"}]}]}' />
          <div className="flex items-center gap-3">
            <Button size="sm" disabled={!paste.trim()} onClick={doImport}>匯入</Button>
            {msg && <span className="text-xs text-muted-foreground">{msg}</span>}
          </div>
        </div>
      )}
      {items.map((w) => <Card key={w.id} w={w} onDone={onDone} />)}
    </section>
  )
}
