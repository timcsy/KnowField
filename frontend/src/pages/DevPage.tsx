import { useEffect, useState } from "react"
import { useSearchParams } from "react-router-dom"
import { Link } from "react-router-dom"
import { pages, type ExtBase, type ExtItem } from "@/lib/api"
import { Markdown } from "@/components/Markdown"
import { cn } from "@/lib/utils"

// spec 074：開發模式——**有狀態、有產物、會回頭看的工作**那一側。
// ⚠️ 它讀的正是階段 68 抓進來的六層。在這一刀之前，那 514 個檔案沒有任何消費者。
// ⚠️ **唯讀**：外部知識不編輯、不搬動。「寫在哪就算哪邊」——所以沒有「移動」這個動作，
//    也就沒有「我到底搬過去了沒」那種狀態（雙模式介面第三個坑）。

const LAYERS = [
  { key: "vision", label: "📐 路線圖" },
  { key: "principles", label: "📖 原則" },
  { key: "experience", label: "🧪 經驗" },
  { key: "draft", label: "✍️ draft" },
  { key: "history", label: "🕰 轉移" },
  { key: "episodes", label: "🎬 場景" },
  { key: "concepts", label: "🧠 概念" },
  { key: "skills", label: "🛠 skills" },
]

export default function DevPage() {
  const [sp, setSp] = useSearchParams()
  const [bases, setBases] = useState<ExtBase[] | null>(null)
  const [items, setItems] = useState<{ id: number; path: string }[]>([])
  const [doc, setDoc] = useState<ExtItem | null>(null)
  // ⚠️ FR-002：模式與位置走 **URL**，不是元件狀態——可分享、上一頁有用、重整不掉
  const bid = Number(sp.get("base") || 0)
  const layer = sp.get("layer") || "experience"
  const iid = Number(sp.get("doc") || 0)

  useEffect(() => { pages.bases().then((d) => setBases(d.bases.filter((b) => b.status === "ok"))).catch(() => setBases([])) }, [])
  useEffect(() => {
    if (!bases?.length) return
    if (!bid) { const s = new URLSearchParams(sp); s.set("base", String(bases[0].id)); setSp(s, { replace: true }) }
  }, [bases, bid, sp, setSp])
  useEffect(() => {
    if (!bid) return
    setItems([]); pages.baseLayer(bid, layer).then((d) => setItems(d.items)).catch(() => {})
  }, [bid, layer])
  useEffect(() => {
    if (!iid) { setDoc(null); return }
    pages.extItem(iid).then(setDoc).catch(() => setDoc(null))
  }, [iid])

  const go = (patch: Record<string, string>) => {
    const s = new URLSearchParams(sp)
    for (const [k, v] of Object.entries(patch)) v ? s.set(k, v) : s.delete(k)
    setSp(s)
  }

  if (!bases) return <p className="text-sm text-muted-foreground">載入中…</p>
  if (bases.length === 0) {
    // ⚠️ FR-008：空狀態要**說怎麼開始**，不是留白
    return (
      <div className="space-y-3 pb-8">
        <h1 className="text-2xl font-bold">🧰 開發</h1>
        <p className="text-sm text-muted-foreground">
          這裡讀的是你其他專案的知識庫。還沒有任何一個——
          到 <Link to="/bases" className="text-primary hover:underline">🌍 別的知識庫</Link> 加一個進來。
        </p>
      </div>
    )
  }
  const base = bases.find((b) => b.id === bid)
  return (
    <div className="space-y-4 pb-8">
      <div className="flex flex-wrap items-center gap-3">
        <select value={bid || ""} onChange={(e) => go({ base: e.target.value, doc: "" })}
          className="rounded-md border bg-background px-2 py-1 text-sm">
          {bases.map((b) => <option key={b.id} value={b.id}>📁 {b.name || b.repo}</option>)}
        </select>
        {base && (
          <span className="text-xs text-muted-foreground">
            {base.branch} · {base.n_items} 份知識
            {base.fetched_at && ` · ${Math.max(0, Math.floor((Date.now() - Date.parse(base.fetched_at)) / 86400000))} 天前抓的`}
          </span>
        )}
      </div>

      <nav className="flex flex-wrap gap-1">
        {LAYERS.filter((l) => (base?.layers?.[l.key] ?? 0) > 0).map((l) => (
          <button key={l.key} onClick={() => go({ layer: l.key, doc: "" })}
            className={cn("rounded-lg px-2.5 py-1 text-sm hover:bg-sidebar-accent",
              layer === l.key && "bg-sidebar-accent font-medium")}>
            {l.label} <span className="text-xs text-muted-foreground">{base?.layers?.[l.key]}</span>
          </button>
        ))}
      </nav>

      <div className="grid gap-4 md:grid-cols-[minmax(0,18rem)_1fr]">
        <ul className="max-h-[70vh] space-y-0.5 overflow-y-auto">
          {items.map((it) => (
            <li key={it.id}>
              <button onClick={() => go({ doc: String(it.id) })}
                className={cn("w-full truncate rounded px-2 py-1 text-left text-xs hover:bg-sidebar-accent",
                  iid === it.id && "bg-sidebar-accent font-medium")}>
                {it.path.replace(/^knowledge\//, "")}
              </button>
            </li>
          ))}
          {items.length === 0 && <li className="px-2 text-xs text-muted-foreground">這一層是空的。</li>}
        </ul>
        <div className="min-w-0 rounded-xl border bg-card p-4">
          {doc ? (
            <>
              <p className="mb-2 text-xs text-muted-foreground">
                {doc.repo} · {doc.path}
              </p>
              <Markdown text={doc.body} prefix={`ext${doc.id}`} />
            </>
          ) : (
            <p className="text-sm text-muted-foreground">左邊挑一份來看。</p>
          )}
        </div>
      </div>
    </div>
  )
}
