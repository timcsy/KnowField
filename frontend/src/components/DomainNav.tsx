import { useEffect, useRef, useState } from "react"
import { useNavigate } from "react-router-dom"
import { pages } from "@/lib/api"
import { ROOT_NAME, useCurrentDomain } from "@/lib/domain"
import { cn } from "@/lib/utils"

// 麵包屑（spec 052）＝換地方的主要路徑，也是「**我現在會影響誰**」的唯一指示。
// ⚠️ 它不是裝飾：換了領域，下一個 ＋新對話／冊封／收來源就歸到新地方去了。
// 每段可點（往上跳）· `▾` 展開同層兄弟（往旁邊跳）——Finder 路徑列的做法，一行三個方向。
type Domain = { id: number; name: string; parent_id: number | null }

export function DomainNav({ onNavigate }: { onNavigate?: () => void }) {
  const { did, go } = useCurrentDomain()
  const [domains, setDomains] = useState<Domain[]>([])
  const [path, setPath] = useState<{ id: number; name: string }[]>([])
  const [open, setOpen] = useState<number | "root" | null>(null)
  const box = useRef<HTMLDivElement>(null)

  useEffect(() => { pages.domains().then((r) => setDomains(r.domains)).catch(() => {}) }, [])
  useEffect(() => {
    const d = domains.find((x) => x.id === did)
    if (!did) { setPath([]); return }
    // 路徑由後端從 parent_id 導出；這裡本地重建以免每次換領域都多打一趟
    const out: { id: number; name: string }[] = []
    let cur: number | null = did, guard = 0
    while (cur !== null && guard++ < 64) {
      const n = domains.find((x) => x.id === cur)
      if (!n) break
      out.unshift({ id: n.id, name: n.name })
      cur = n.parent_id
    }
    setPath(d ? out : [])
  }, [did, domains])

  useEffect(() => {
    const h = (e: MouseEvent) => { if (!box.current?.contains(e.target as Node)) setOpen(null) }
    window.addEventListener("mousedown", h)
    return () => window.removeEventListener("mousedown", h)
  }, [])

  const siblingsOf = (id: number | "root") => {
    if (id === "root") return domains.filter((d) => d.parent_id === null)
    const me = domains.find((d) => d.id === id)
    return domains.filter((d) => d.parent_id === (me?.parent_id ?? null))
  }
  const jump = (to: number | null) => { setOpen(null); go(to); onNavigate?.() }

  const Crumb = ({ id, name }: { id: number | "root"; name: string }) => (
    <span className="relative inline-flex items-center">
      <button onClick={() => jump(id === "root" ? null : id)}
              className={cn("max-w-[9rem] truncate rounded px-1 py-0.5 hover:bg-sidebar-accent",
                            ((id === "root" && did === null) || id === did) && "font-semibold text-foreground")}>
        {name}
      </button>
      <button onClick={() => setOpen(open === id ? null : id)} aria-label="同層領域"
              className="rounded px-0.5 text-muted-foreground hover:bg-sidebar-accent hover:text-foreground">▾</button>
      {open === id && (
        <div className="absolute left-0 top-full z-30 mt-1 max-h-64 w-52 overflow-y-auto rounded-lg border bg-popover p-1 shadow-lg">
          {siblingsOf(id).length === 0 && (
            <p className="px-2 py-1 text-xs text-muted-foreground">同層沒有別的領域。</p>
          )}
          {siblingsOf(id).map((s) => (
            <button key={s.id} onClick={() => jump(s.id)}
                    className={cn("block w-full truncate rounded px-2 py-1 text-left text-sm hover:bg-accent",
                                  s.id === did && "font-semibold")}>
              📁 {s.name}
            </button>
          ))}
        </div>
      )}
    </span>
  )

  return (
    <div ref={box} className="flex flex-wrap items-center gap-0.5 px-1 text-sm text-muted-foreground">
      <Crumb id="root" name={`🗂 ${ROOT_NAME}`} />
      {path.map((p) => (
        <span key={p.id} className="flex items-center gap-0.5">
          <span className="text-muted-foreground/50">/</span>
          <Crumb id={p.id} name={p.name} />
        </span>
      ))}
    </div>
  )
}

/** 返回鍵：⚠️ **要說出它要去哪**，一個裸箭頭等於沒有記住怎麼來的。 */
export function BackTo({ label, to }: { label: string; to: number | null }) {
  const { go } = useCurrentDomain()
  const navigate = useNavigate()
  return (
    <button onClick={() => { if (window.history.length > 1) navigate(-1); else go(to) }}
            className="rounded px-1 py-0.5 text-xs text-muted-foreground hover:bg-sidebar-accent hover:text-foreground">
      ← 回 {label}
    </button>
  )
}
