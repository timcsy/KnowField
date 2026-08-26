import { useState } from "react"
import { pages, type SuggestedFolder } from "@/lib/api"
import { Button } from "@/components/ui/button"

// spec 065：建議怎麼整理。
//
// ⚠️ **這裡沒有「全部套用」，而且不會有。** 提議不違反原則 5，套用才違反——
// 「提議 ＋ 一個全部套用的按鈕」＝ 自動分類多按一下。
//
// ⚠️ 每一夾的**理由**要原樣列出來（不摘要）：理由是可查證的結構事實
// （「這 7 條來自〈某段互動〉」），你能反駁它才代表你真的看過。
// 換成「都跟 X 有關」那種不可反駁的說法，這個介面就會被橡皮圖章化。
export function SuggestOrganize({ onApplied }: { onApplied: () => void }) {
  const [folders, setFolders] = useState<SuggestedFolder[] | null>(null)
  const [busy, setBusy] = useState(false)
  const [names, setNames] = useState<Record<number, string>>({})
  const [done, setDone] = useState<Record<number, string>>({})
  const [err, setErr] = useState<string | null>(null)

  async function load() {
    setBusy(true); setErr(null)
    try {
      const r = await pages.suggestDomains()
      setFolders(r.folders || [])
      setNames(Object.fromEntries((r.folders || []).map((f, i) => [i, f.name])))
    } catch { setErr("拿不到建議，稍後再試。") }
    setBusy(false)
  }

  async function apply(f: SuggestedFolder, i: number) {
    const name = (names[i] || f.name).trim()
    if (!name) return
    const r = await pages.applySuggestion(name, f.items)
    if (r.error) { setErr(r.error); return }
    const n = r.tangles?.length || 0
    setDone((d) => ({ ...d, [i]: `已建立「${name}」，搬進 ${r.moved} 件${n ? `（拆散了 ${n} 條連結）` : ""}` }))
    onApplied()
  }

  if (!folders) {
    return (
      <Button variant="outline" size="sm" onClick={load} disabled={busy}>
        {busy ? "看看怎麼整理…" : "✨ 建議怎麼整理"}
      </Button>
    )
  }

  return (
    <section className="max-h-[70vh] w-full space-y-3 overflow-y-auto rounded-xl border bg-card p-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold">✨ 建議怎麼整理</h2>
        <button onClick={() => setFolders(null)}
                className="text-xs text-muted-foreground hover:text-foreground">收起</button>
      </div>
      <p className="text-xs text-muted-foreground">
        分群<b className="text-foreground">只根據既有的連結</b>（由來／來源），所以每一條理由你都查得到。
        <b className="text-foreground">一次接受一夾</b>——沒有「全部套用」。
      </p>

      {err && <p className="text-xs text-destructive">{err}</p>}
      {folders.length === 0 && (
        <p className="text-sm text-muted-foreground">根領域裡沒有待整理的東西。</p>
      )}

      {folders.map((f, i) => (
        <div key={i} className={`space-y-2 rounded-lg border p-3 ${f.lonely ? "border-dashed opacity-80" : ""}`}>
          <div className="flex flex-wrap items-center gap-2">
            {f.suggest_apply ? (
              <input value={names[i] ?? f.name}
                     onChange={(e) => setNames((n) => ({ ...n, [i]: e.target.value }))}
                     className="min-w-40 flex-1 rounded-md border bg-background px-2 py-1 text-sm font-medium" />
            ) : (
              <span className="flex-1 text-sm font-medium">📄 {f.name}</span>
            )}
            <span className="text-xs text-muted-foreground">{f.count} 件</span>
          </div>
          <ul className="space-y-0.5 text-xs text-muted-foreground">
            {f.reasons.map((r, k) => <li key={k}>· {r}</li>)}
          </ul>
          {done[i] ? (
            <p className="text-xs text-primary">✅ {done[i]}</p>
          ) : f.suggest_apply ? (
            <div className="flex gap-2">
              <Button size="sm" onClick={() => apply(f, i)}>建立這一夾</Button>
              <button onClick={() => setFolders((fs) => (fs || []).filter((_, k) => k !== i))}
                      className="text-xs text-muted-foreground hover:text-foreground">略過</button>
            </div>
          ) : (
            // ⚠️ 留白：分不出來的**不給套用按鈕**，而且說出為什麼
            <p className="text-xs text-muted-foreground">留著就好——硬分出來的資料夾之後還要拆。</p>
          )}
        </div>
      ))}
    </section>
  )
}
