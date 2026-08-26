import { useEffect, useRef, useState } from "react"
import { pages, type Persona } from "@/lib/api"

// spec 067：persona ＝ 隱私的**硬**隔離（不是領域那種軟過濾）。
//
// ⚠️ 這個元件存在的理由不是「方便切換」，是**讓你知道自己是誰**：
// 切錯身分而不自知**不會報錯**，私人的東西會安靜地寫進工作的場。
// 理由沿用階段 49：**你按下它之前，要先看得到它會生在哪。**
// ⇒ 所以它在導航列**之上**，而且會把整條側欄染色——文字標籤太弱。
const PALETTE = ["#2563eb", "#059669", "#d97706", "#dc2626", "#7c3aed", "#0891b2"]

export function usePersonaColor(): string {
  const [c, setC] = useState("")
  useEffect(() => {
    pages.personas().then((r) => {
      const cur = r.personas.find((p) => p.id === r.current)
      setC(cur?.color || "")
    }).catch(() => {})
  }, [])
  return c
}

export function PersonaSwitcher() {
  const [list, setList] = useState<Persona[]>([])
  const [cur, setCur] = useState<number | null>(null)
  const [open, setOpen] = useState(false)
  const [adding, setAdding] = useState("")
  const box = useRef<HTMLDivElement>(null)

  const load = () => pages.personas()
    .then((r) => { setList(r.personas || []); setCur(r.current) }).catch(() => {})
  useEffect(() => { load() }, [])
  useEffect(() => {
    if (!open) return
    const close = (e: Event) => { if (!box.current?.contains(e.target as Node)) setOpen(false) }
    document.addEventListener("mousedown", close); document.addEventListener("touchstart", close)
    return () => {
      document.removeEventListener("mousedown", close); document.removeEventListener("touchstart", close)
    }
  }, [open])

  // ⚠️ 切換要**整頁重載**。既有教訓說「要停留在脈絡的操作別用整頁重載」——
  //    這裡正好相反：任何殘留的前端狀態都是**跨身分的殘留**，而那就是洩漏。
  async function go(id: number | null) {
    await pages.switchPersona(id)
    location.href = "/"
  }
  async function create() {
    const name = adding.trim()
    if (!name) return
    const r = await pages.createPersona(name, PALETTE[list.length % PALETTE.length])
    if ((r as { id?: number }).id) go((r as { id: number }).id)
  }

  const now = list.find((p) => p.id === cur)
  return (
    <div ref={box} className="relative px-3 pb-1 pt-2">
      <button onClick={() => setOpen((v) => !v)}
              className="flex w-full items-center gap-2 rounded-md border px-2 py-1.5 text-sm hover:bg-accent">
        <span className="size-2.5 shrink-0 rounded-full"
              style={{ background: now?.color || "var(--muted-foreground)" }} />
        <span className="truncate">{now ? now.name : "共用（不分身分）"}</span>
        <span className="ml-auto text-xs text-muted-foreground">▾</span>
      </button>
      {open && (
        <div className="absolute left-3 right-3 z-30 mt-1 rounded-md border bg-background p-1 shadow-lg">
          <button onClick={() => go(null)}
                  className="block w-full rounded px-2 py-1 text-left text-sm hover:bg-accent">
            共用（不分身分）
          </button>
          {list.map((p) => (
            <button key={p.id} onClick={() => go(p.id)}
                    className="flex w-full items-center gap-2 rounded px-2 py-1 text-left text-sm hover:bg-accent">
              <span className="size-2.5 rounded-full" style={{ background: p.color || "#888" }} />
              {p.name}
            </button>
          ))}
          <div className="mt-1 border-t pt-1">
            <input value={adding} onChange={(e) => setAdding(e.target.value)}
                   onKeyDown={(e) => { if (e.key === "Enter" && !e.nativeEvent.isComposing) create() }}
                   placeholder="＋ 新身分…"
                   className="w-full rounded bg-transparent px-2 py-1 text-sm outline-none" />
          </div>
          <p className="px-2 pb-1 pt-1 text-[10px] leading-snug text-muted-foreground">
            身分之間是<b>硬隔離</b>：切過去就看不到，也搜不到。
            沒指定身分時寫的東西是<b>共用</b>，每個身分都拿得到。
          </p>
        </div>
      )}
    </div>
  )
}
