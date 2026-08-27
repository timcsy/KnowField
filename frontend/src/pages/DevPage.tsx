import { useEffect, useState } from "react"
import { Link, useSearchParams } from "react-router-dom"
import { pages, type ExtBase, type ExtItem } from "@/lib/api"
import { Markdown } from "@/components/Markdown"
import { cn } from "@/lib/utils"

// spec 074：開發模式的主區＝**檔案樹｜預覽**（IDE 的中段與右段；最左的專案在側欄）。
// ⚠️ 選取全部走 URL（`?base=&layer=&doc=`）⇒ 側欄與這兩塊各自讀，不用共享狀態。

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

export default function DevPage() {
  const [sp, setSp] = useSearchParams()
  const [bases, setBases] = useState<ExtBase[] | null>(null)
  const [items, setItems] = useState<{ id: number; path: string }[]>([])
  const [doc, setDoc] = useState<ExtItem | null>(null)
  const bid = Number(sp.get("base") || 0)
  const layer = sp.get("layer") || "experience"
  const iid = Number(sp.get("doc") || 0)

  useEffect(() => { pages.bases().then((d) => setBases(d.bases)).catch(() => setBases([])) }, [])
  useEffect(() => {
    if (!bid) { setItems([]); return }
    pages.baseLayer(bid, layer).then((d) => setItems(d.items)).catch(() => setItems([]))
  }, [bid, layer])
  useEffect(() => {
    if (!iid) { setDoc(null); return }
    setDoc(null); pages.extItem(iid).then(setDoc).catch(() => setDoc(null))
  }, [iid])

  const go = (patch: Record<string, string>) => {
    const s = new URLSearchParams(sp)
    for (const [k, v] of Object.entries(patch)) v ? s.set(k, v) : s.delete(k)
    setSp(s)
  }
  const base = bases?.find((b) => b.id === bid)
  const has = (k: string) => (base?.layers?.[k] ?? 0) > 0

  if (bases && bases.length === 0) {
    return (
      <div className="flex h-full items-center justify-center px-6 text-center">
        <p className="max-w-sm text-sm text-muted-foreground">
          這裡讀的是你其他專案的知識庫。還沒有任何一個——
          到 <Link to="/bases" className="text-primary hover:underline">⚙ 管理專案</Link> 加一個進來。
        </p>
      </div>
    )
  }
  return (
    <div className="flex h-full min-h-0">
      {/* ── 檔案樹：層是資料夾、檔案是葉子 ── */}
      <div className="flex w-56 shrink-0 flex-col border-r lg:w-64">
        <nav className="flex flex-wrap gap-0.5 border-b p-1.5">
          {LAYERS.filter((l) => has(l.key)).map((l) => (
            <button key={l.key} onClick={() => go({ layer: l.key, doc: "" })}
              className={cn("rounded px-1.5 py-0.5 text-xs hover:bg-muted",
                layer === l.key && "bg-muted font-medium")}>
              {l.label} <span className="text-muted-foreground">{base?.layers?.[l.key]}</span>
            </button>
          ))}
        </nav>
        <ul className="min-h-0 flex-1 space-y-px overflow-y-auto p-1">
          {items.map((it) => (
            <li key={it.id}>
              <button onClick={() => go({ doc: String(it.id) })} title={it.path}
                className={cn("w-full truncate rounded px-2 py-1 text-left text-xs hover:bg-muted",
                  iid === it.id && "bg-muted font-medium")}>
                {it.path.replace(/^knowledge\//, "").replace(new RegExp(`^${layer}/`), "")}
              </button>
            </li>
          ))}
          {items.length === 0 && <li className="px-2 py-1 text-xs text-muted-foreground">這一層是空的。</li>}
        </ul>
      </div>

      {/* ── 預覽：⚠️ 這一塊要**好讀** ⇒ 給它整片剩下的寬度，而字行本身收在舒服的行寬 ── */}
      <div className="min-w-0 flex-1 overflow-y-auto">
        {doc ? (
          <>
            <div className="sticky top-0 z-10 border-b bg-background/95 px-6 py-2 backdrop-blur">
              {/* ⚠️ 每一份都標它來自哪個 repo——看不出是誰的，就等於冒充你自己的知識 */}
              <p className="truncate text-xs text-muted-foreground">
                <span className="rounded bg-muted px-1.5 py-0.5">{doc.repo}</span>
                <span className="mx-2">/</span>{doc.path.replace(/^knowledge\//, "")}
              </p>
            </div>
            <div className="mx-auto max-w-4xl px-8 py-6">
              <Markdown text={doc.body} prefix={`ext${doc.id}`} />
            </div>
          </>
        ) : (
          <div className="flex h-full items-center justify-center px-6 text-center">
            <p className="max-w-sm text-sm text-muted-foreground">
              左邊挑一份來看。{base && `（${base.name || base.repo}）`}
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
