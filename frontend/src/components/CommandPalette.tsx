import { useEffect, useRef, useState } from "react"
import { useNavigate } from "react-router-dom"
import { pages, type SearchGroup, type SearchHit } from "@/lib/api"

// spec 066：全域搜尋（⌘K）。
//
// 領域的存在理由換了：**搜尋負責「更快找到目標」，領域頁負責「找的過程中複習」**。
// ⚠️ 所以這裡**刻意不做**「你可能也想看」——那是逛的工作。
// 摻進來的話，兩個介面都會說不清自己是幹嘛的。
// ⚠️ spec 074：**⌘K 必須跨模式**——分模式而搜不到彼此，正是 Spark 跟即時通訊那個病。
//    而外部知識**每一筆都標來源**：看不出是誰的，就等於冒充你自己的知識。
const KIND_LABEL: Record<string, string> = {
  why_node: "💡 理解", conversation: "💬 互動", source: "📚 來源", article: "🧩 應用",
  ext: "🌍 別的知識庫",
}

function hrefOf(h: SearchHit): string {
  // 跨模式：外部知識點下去跳到**開發模式**那一邊
  if (h.kind === "ext") return `/dev?base=${h.base_id ?? ""}&layer=${h.layer ?? ""}&doc=${h.ref}`
  if (h.kind === "conversation") return `/?resume=${h.ref}`
  if (h.kind === "source") return `/source?u=${encodeURIComponent(String(h.ref))}`
  if (h.kind === "article") return `/articles/${h.ref}`
  return "/roots"
}

export function CommandPalette() {
  const nav = useNavigate()
  const [open, setOpen] = useState(false)
  const [q, setQ] = useState("")
  const [groups, setGroups] = useState<SearchGroup[]>([])
  const [sel, setSel] = useState(0)
  const box = useRef<HTMLInputElement>(null)

  // ⌘K／Ctrl-K 開。⚠️ 在輸入框裡也要能開——它是全域的，不是頁面的。
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault(); setOpen((v) => !v)
      } else if (e.key === "Escape") setOpen(false)
    }
    window.addEventListener("keydown", h)
    return () => window.removeEventListener("keydown", h)
  }, [])

  useEffect(() => { if (open) setTimeout(() => box.current?.focus(), 0) }, [open])

  useEffect(() => {
    if (!open) return
    const t = setTimeout(() => {
      if (!q.trim()) { setGroups([]); return }
      pages.search(q).then((r) => { setGroups(r.groups || []); setSel(0) }).catch(() => setGroups([]))
    }, 180)
    return () => clearTimeout(t)
  }, [q, open])

  if (!open) return null
  const flat = groups.flatMap((g) => g.items)

  function go(h: SearchHit) { setOpen(false); setQ(""); nav(hrefOf(h)) }

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/40 pt-[12vh]"
         onClick={() => setOpen(false)}>
      <div className="w-[92%] max-w-2xl overflow-hidden rounded-xl border bg-background shadow-2xl"
           onClick={(e) => e.stopPropagation()}>
        <input ref={box} value={q} onChange={(e) => setQ(e.target.value)}
               placeholder="找任何東西——來源、互動、理解、應用（比對標題與內容）"
               onKeyDown={(e) => {
                 if (e.key === "ArrowDown") { e.preventDefault(); setSel((i) => Math.min(i + 1, flat.length - 1)) }
                 else if (e.key === "ArrowUp") { e.preventDefault(); setSel((i) => Math.max(i - 1, 0)) }
                 else if (e.key === "Enter" && flat[sel]) { e.preventDefault(); go(flat[sel]) }
               }}
               className="w-full border-b bg-transparent px-4 py-3 text-sm outline-none" />
        <div className="max-h-[60vh] overflow-y-auto p-2">
          {q.trim() && flat.length === 0 && (
            <p className="px-3 py-6 text-center text-sm text-muted-foreground">沒有找到「{q.trim()}」。</p>
          )}
          {groups.map((g) => (
            <div key={g.kind} className="mb-2">
              <div className="px-3 py-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground/60">
                {KIND_LABEL[g.kind] || g.kind} · {g.count}
              </div>
              {g.items.map((h) => {
                const i = flat.indexOf(h)
                return (
                  <button key={`${h.kind}-${h.ref}`} onClick={() => go(h)}
                          onMouseEnter={() => setSel(i)}
                          className={`block w-full truncate rounded px-3 py-1.5 text-left text-sm ${
                            i === sel ? "bg-accent" : "hover:bg-accent/50"}`}>
                    {/* ⚠️ 外部知識一定標來源——它排在最後，而且看得出是別人的 */}
                    {h.base && <span className="mr-1.5 rounded bg-muted px-1 text-xs">{h.base}</span>}
                    {h.label}
                  </button>
                )
              })}
            </div>
          ))}
          {!q.trim() && (
            <p className="px-3 py-6 text-center text-xs text-muted-foreground">
              打字開始找。<kbd className="rounded border px-1">↑↓</kbd> 選、
              <kbd className="rounded border px-1">Enter</kbd> 開、
              <kbd className="rounded border px-1">Esc</kbd> 關。
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
