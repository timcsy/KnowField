import { useEffect, useLayoutEffect, useRef, useState } from "react"
import { createPortal } from "react-dom"
import { pages, type ConvRow } from "@/lib/api"

// 對話 ⋮ 選單（側欄＋總對話頁共用）。portal 到 body＋fixed 定位 → 不被捲動容器裁切（暫存在最底時的 bug）；
// 靠底自動往上開。刪除：被核心理解引用（由來）→擋刪、提示先刪核心理解（護溯源，原則 3）。
export function ConvMenu({ c, open, setOpen, anchorRef, onResume, onRename, onChange }: {
  c: ConvRow
  open: boolean
  setOpen: (v: boolean) => void
  anchorRef: React.RefObject<HTMLElement | null>
  onResume: () => void
  onRename: () => void
  onChange: () => void
}) {
  const menuRef = useRef<HTMLDivElement>(null)
  const [pos, setPos] = useState<{ right: number; top?: number; bottom?: number } | null>(null)

  useLayoutEffect(() => {
    if (!open) return
    const r = anchorRef.current?.getBoundingClientRect()
    if (!r) return
    const up = r.bottom + 220 > window.innerHeight   // 靠底→往上開，避免被裁切
    const right = window.innerWidth - r.right
    setPos(up ? { bottom: window.innerHeight - r.top + 4, right } : { top: r.bottom + 4, right })
  }, [open, anchorRef])

  useEffect(() => {
    if (!open) return
    const close = (e: Event) => {
      if (menuRef.current?.contains(e.target as Node)) return
      if (anchorRef.current?.contains(e.target as Node)) return
      setOpen(false)
    }
    const onScroll = () => setOpen(false)   // fixed 選單會脫離按鈕→捲動即關
    document.addEventListener("mousedown", close)
    document.addEventListener("touchstart", close)
    window.addEventListener("scroll", onScroll, true)
    return () => {
      document.removeEventListener("mousedown", close)
      document.removeEventListener("touchstart", close)
      window.removeEventListener("scroll", onScroll, true)
    }
  }, [open, anchorRef, setOpen])

  async function del() {
    setOpen(false)
    if (!confirm(`刪除對話「${c.title || "未命名"}」？`)) return
    const r = await pages.deleteConv(c.id)
    if (!r.deleted && r.blocked_by?.length) {
      alert("這段對話是下列核心理解的『由來』，刪不掉。\n請先到「💡 核心理解」把它們退回/刪掉，再刪這段對話：\n\n"
        + r.blocked_by.map((s) => "• " + s).join("\n"))
      return
    }
    onChange()
  }

  if (!open || !pos) return null
  const item = "block w-full px-3 py-2 text-left hover:bg-accent"
  return createPortal(
    <div ref={menuRef} style={{ position: "fixed", ...pos }}
         className="z-50 w-36 overflow-hidden rounded-md border bg-popover py-1 text-sm text-popover-foreground shadow-lg">
      {/* spec 047：不再分「檢視」與「接著聊」——一段對話只有一個去處（使用者裁決 2026-08-25）。 */}
      <button onClick={() => { setOpen(false); onResume() }} className={item}>打開</button>
      <button onClick={() => { setOpen(false); onRename() }} className={item}>改名</button>
      <button onClick={del} className={item + " text-destructive"}>刪除</button>
    </div>,
    document.body,
  )
}
