import { useEffect, useState } from "react"
import { Link, useSearchParams } from "react-router-dom"
import { pages, type ExtBase } from "@/lib/api"
import { cn } from "@/lib/utils"

// spec 074：開發模式的側欄＝**專案樹**（IDE 的形狀：左邊是檔案、右邊是那份檔案）。
// ⚠️ 狀態全部走 **URL**（`?base=&layer=&doc=`）⇒ 側欄與主區**不用共享狀態**，
//    而且分享、上一頁、重整都成立。這是模式走 URL 那個決定順下來的紅利。
// ⚠️ 互動那邊的東西（領域／對話歷史／persona）一個都不進來——
//    專案 base 天然就是隔離的，硬把兩套導覽疊在一起就是雙模式介面的第一個坑。

const LAYERS = [
  { key: "vision", label: "📐 路線圖" },
  { key: "principles", label: "📖 原則" },
  { key: "experience", label: "🧪 經驗" },
  { key: "draft", label: "✍️ draft" },
  { key: "concepts", label: "🧠 概念" },
  { key: "history", label: "🕰 轉移" },
  { key: "episodes", label: "🎬 場景" },
  { key: "skills", label: "🛠 skills" },
  { key: "other", label: "· 其他" },
]

export function DevSidebar({ onNavigate }: { onNavigate?: () => void }) {
  const [sp, setSp] = useSearchParams()
  const [bases, setBases] = useState<ExtBase[] | null>(null)
  const [items, setItems] = useState<{ id: number; path: string }[]>([])
  const bid = Number(sp.get("base") || 0)
  const layer = sp.get("layer") || "experience"
  const iid = Number(sp.get("doc") || 0)

  useEffect(() => {
    pages.bases().then((d) => setBases(d.bases.filter((b) => b.status === "ok")))
      .catch(() => setBases([]))
  }, [])
  useEffect(() => {
    if (bases?.length && !bid) {
      const s = new URLSearchParams(sp); s.set("base", String(bases[0].id))
      setSp(s, { replace: true })
    }
  }, [bases, bid, sp, setSp])
  useEffect(() => {
    if (!bid) { setItems([]); return }
    pages.baseLayer(bid, layer).then((d) => setItems(d.items)).catch(() => setItems([]))
  }, [bid, layer])

  const go = (patch: Record<string, string>) => {
    const s = new URLSearchParams(sp)
    for (const [k, v] of Object.entries(patch)) v ? s.set(k, v) : s.delete(k)
    setSp(s)
  }
  const base = bases?.find((b) => b.id === bid)

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-2">
      {bases === null ? (
        <p className="px-2 text-xs text-muted-foreground">載入中…</p>
      ) : bases.length === 0 ? (
        // ⚠️ 空狀態要**說怎麼開始**，不是留白
        <p className="px-2 text-xs text-muted-foreground">
          還沒有專案。到{" "}
          <Link to="/bases" onClick={onNavigate} className="text-primary hover:underline">🌍 別的知識庫</Link>
          {" "}加一個進來。
        </p>
      ) : (
        <>
          <select value={bid || ""} onChange={(e) => go({ base: e.target.value, doc: "" })}
            className="mx-1 rounded-md border bg-background px-2 py-1 text-sm">
            {bases.map((b) => <option key={b.id} value={b.id}>📁 {b.name || b.repo}</option>)}
          </select>

          <nav className="flex flex-col gap-0.5">
            {LAYERS.filter((l) => (base?.layers?.[l.key] ?? 0) > 0).map((l) => (
              <button key={l.key} onClick={() => go({ layer: l.key, doc: "" })}
                className={cn("flex items-center gap-2 rounded-lg px-3 py-1 text-sm hover:bg-sidebar-accent",
                  layer === l.key && "bg-sidebar-accent font-medium")}>
                <span className="min-w-0 flex-1 truncate text-left">{l.label}</span>
                <span className="shrink-0 text-xs text-muted-foreground">{base?.layers?.[l.key]}</span>
              </button>
            ))}
          </nav>

          <ul className="min-h-0 flex-1 space-y-0.5 overflow-y-auto border-t pt-1">
            {items.map((it) => (
              <li key={it.id}>
                <button onClick={() => { go({ doc: String(it.id) }); onNavigate?.() }}
                  title={it.path}
                  className={cn("w-full truncate rounded px-2 py-1 text-left text-xs hover:bg-sidebar-accent",
                    iid === it.id && "bg-sidebar-accent font-medium")}>
                  {it.path.replace(/^knowledge\//, "").replace(new RegExp(`^${layer}/`), "")}
                </button>
              </li>
            ))}
            {items.length === 0 && <li className="px-2 text-xs text-muted-foreground">這一層是空的。</li>}
          </ul>

          <Link to="/bases" onClick={onNavigate}
            className={cn("rounded-lg px-3 py-1 text-xs text-muted-foreground hover:bg-sidebar-accent hover:text-foreground",
              window.location.pathname === "/bases" && "bg-sidebar-accent")}>
            ⚙ 管理專案
          </Link>
          {base && (
            <p className="px-2 text-[11px] text-muted-foreground">
              {base.branch} · {base.n_items} 份
              {base.fetched_at &&
                ` · ${Math.max(0, Math.floor((Date.now() - Date.parse(base.fetched_at)) / 86400000))} 天前抓的`}
            </p>
          )}
        </>
      )}
    </div>
  )
}
