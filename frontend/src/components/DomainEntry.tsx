import { useEffect, useRef, useState } from "react"
import { pages } from "@/lib/api"
import { ROOT_NAME, useCurrentDomain } from "@/lib/domain"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"

// 「領域」入口（spec 053）：側欄的第一格，**點下去就地展開**——
// 往上（祖先）· 往旁（同層）· 往下（子領域）· 在這裡新增。
// ⚠️ 刻意**不另開一頁**：整理是偶爾的事，導覽是每天的事，把導覽送進另一頁
//    等於每次換位置都要離開你正在做的事。
type Domain = { id: number; name: string; parent_id: number | null; path: { id: number; name: string }[] }

export function DomainEntry({ onNavigate, onChanged }: {
  onNavigate?: () => void; onChanged?: () => void }) {
  const { did, go } = useCurrentDomain()
  const [domains, setDomains] = useState<Domain[]>([])
  const [open, setOpen] = useState(false)
  const [name, setName] = useState("")
  const [err, setErr] = useState<string | null>(null)
  const box = useRef<HTMLDivElement>(null)

  const load = () => pages.domains().then((r) => setDomains(r.domains)).catch(() => {})
  useEffect(() => { load() }, [])
  useEffect(() => {
    if (!open) return
    const h = (e: MouseEvent) => { if (!box.current?.contains(e.target as Node)) setOpen(false) }
    window.addEventListener("mousedown", h)
    return () => window.removeEventListener("mousedown", h)
  }, [open])

  const me = domains.find((d) => d.id === did) || null
  const path = me?.path || []
  const parentId = me?.parent_id ?? null
  const kids = domains.filter((d) => d.parent_id === did)
  const siblings = domains.filter((d) => d.parent_id === parentId && d.id !== did)

  const jump = (to: number | null) => { setOpen(false); go(to); onNavigate?.() }

  async function create() {
    if (!name.trim()) return
    const r = await pages.createDomain(name.trim(), did)
    if (!r.ok) { setErr(r.err || "建不起來"); return }
    setName(""); setErr(null)
    await load(); onChanged?.()
  }

  // 當前位置寫成一行；⚠️ 它是「**我現在會影響誰**」的指示，不是裝飾
  // ——新東西（對話／理解／應用／來源）就生在這裡。
  const here = path.length ? path.map((p) => p.name).join(" / ") : ROOT_NAME

  return (
    <div ref={box} className="relative">
      <button onClick={() => setOpen((v) => !v)}
              title={`你在「${here}」——新東西會生在這裡`}
              className={cn("flex w-full items-center gap-2 rounded-lg px-3 py-1.5 text-left text-sm hover:bg-sidebar-accent",
                            open && "bg-sidebar-accent")}>
        <span className="shrink-0">🗂 領域</span>
        <span className="min-w-0 flex-1 truncate text-xs text-muted-foreground">{here}</span>
        <span className="shrink-0 text-muted-foreground">{open ? "▴" : "▾"}</span>
      </button>

      {open && (
        <div className="absolute left-0 right-0 top-full z-30 mt-1 max-h-[70vh] space-y-2 overflow-y-auto rounded-lg border bg-popover p-2 shadow-lg">
          {/* 往上：祖先鏈，每一段都可點 */}
          <section>
            <h4 className="px-1 pb-0.5 text-[10px] uppercase tracking-wide text-muted-foreground/60">往上</h4>
            <button onClick={() => jump(null)}
                    className={cn("block w-full truncate rounded px-2 py-1 text-left text-sm hover:bg-accent",
                                  did === null && "font-semibold")}>
              🗂 {ROOT_NAME}
            </button>
            {path.slice(0, -1).map((p) => (
              <button key={p.id} onClick={() => jump(p.id)}
                      className="block w-full truncate rounded px-2 py-1 text-left text-sm hover:bg-accent">
                📁 {p.name}
              </button>
            ))}
          </section>

          {siblings.length > 0 && (
            <section className="border-t pt-1">
              <h4 className="px-1 pb-0.5 text-[10px] uppercase tracking-wide text-muted-foreground/60">同層</h4>
              {siblings.map((d) => (
                <button key={d.id} onClick={() => jump(d.id)}
                        className="block w-full truncate rounded px-2 py-1 text-left text-sm hover:bg-accent">
                  📁 {d.name}
                </button>
              ))}
            </section>
          )}

          <section className="border-t pt-1">
            <h4 className="px-1 pb-0.5 text-[10px] uppercase tracking-wide text-muted-foreground/60">子領域</h4>
            {kids.length === 0 && (
              <p className="px-2 py-1 text-xs text-muted-foreground">還沒有子領域。</p>
            )}
            {kids.map((d) => (
              <button key={d.id} onClick={() => jump(d.id)}
                      className="block w-full truncate rounded px-2 py-1 text-left text-sm hover:bg-accent">
                📁 {d.name}
              </button>
            ))}
            <div className="flex items-center gap-1 px-1 pt-1">
              <Input value={name} onChange={(e) => setName(e.target.value)}
                     onKeyDown={(e) => { if (e.key === "Enter" && !e.nativeEvent.isComposing) create() }}
                     placeholder={`在${path.length ? path[path.length - 1].name : ROOT_NAME}底下新增…`}
                     className="h-7 text-xs" />
              <button onClick={create} className="shrink-0 rounded px-2 py-1 text-xs hover:bg-accent">＋</button>
            </div>
            {err && <p className="px-2 pt-1 text-xs text-destructive">{err}</p>}
          </section>
        </div>
      )}
    </div>
  )
}
