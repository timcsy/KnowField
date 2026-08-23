import { useEffect, useRef, useState } from "react"
import { Link, useLocation, useNavigate } from "react-router-dom"
import { pages, type ConvRow } from "@/lib/api"
import { ConvMenu } from "@/components/ConvMenu"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"

// nav 順序＝膜的流向：來源（原料）→ 對話（消化）→ 核心理解（沉澱地基）→ 文章（輸出）
const NAV = [
  { label: "📚 來源", to: "/sources" },
  { label: "💬 對話", to: "/conversations" },
  { label: "💡 核心理解", to: "/roots" },
  { label: "📝 文章", to: "/articles" },
]

// 單一側欄（各大 AI 手順）：Logo＋新對話＋導覽＋對話歷史，全在一欄。
// 與聊天頁靠 URL（?new/?resume）＋事件（kf-conversations-changed）解耦溝通。
export function ConversationSidebar({ onNavigate }: { onNavigate?: () => void }) {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  // spec 040：不再分暫存/永久——對話就是對話。
  const [convs, setConvs] = useState<ConvRow[]>([])
  const [msg, setMsg] = useState<string | null>(null)
  const [me, setMe] = useState<{ user: string | null; auth_enabled: boolean }>({ user: null, auth_enabled: false })
  const load = () => pages.conversations().then((r) => setConvs(r.conversations)).catch(() => {})
  useEffect(() => {
    load()
    pages.me().then(setMe).catch(() => {})
    const h = () => load()
    window.addEventListener("kf-conversations-changed", h)
    return () => window.removeEventListener("kf-conversations-changed", h)
  }, [])

  const isActive = (to: string) =>
    to === "/conversations" ? pathname === "/" || pathname.startsWith("/conversations")
      : to === "/sources" ? pathname.startsWith("/source")
      : pathname.startsWith(to)

  const goNew = () => { navigate("/?new=" + Date.now()); onNavigate?.() }
  const goResume = (id: number) => { navigate("/?resume=" + id); onNavigate?.() }

  async function dedupe() {
    const p = await pages.dedupePreview()
    if (p.n_extra === 0) { setMsg("沒有重複的對話。"); return }
    if (!confirm(`發現 ${p.n_extra} 份重複（${p.n_groups} 組）。併掉多餘、重指 ${p.n_roots} 條核心理解的由來？`)) return
    const r = await pages.dedupeApply()
    setMsg(`✅ 併掉 ${r.removed} 份、重指 ${r.repointed} 條由來。`); load()
  }

  return (
    <div className="flex h-full flex-col gap-2 p-2">
      <div className="flex items-center justify-between px-1">
        <Link to="/" onClick={onNavigate} className="py-1 text-lg font-bold">🧠 KnowField</Link>
        {onNavigate && <button onClick={onNavigate} aria-label="關閉" className="px-1 text-muted-foreground">✕</button>}
      </div>
      <Button size="sm" onClick={goNew}>＋ 新對話</Button>
      <nav className="flex flex-col gap-0.5">
        {NAV.map((n) => (
          <Link key={n.to} to={n.to} onClick={onNavigate}
            className={cn("rounded-lg px-3 py-1.5 text-sm text-sidebar-foreground hover:bg-sidebar-accent",
              isActive(n.to) && "bg-sidebar-accent font-medium")}>
            {n.label}
          </Link>
        ))}
      </nav>

      <div className="mt-1 flex items-center justify-between border-t px-2 pt-2">
        <span className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground/60">對話紀錄</span>
        {convs.length > 0 && (
          <button onClick={dedupe} className="text-[11px] text-muted-foreground hover:underline">🧹 清理重複</button>
        )}
      </div>
      {msg && <div className="rounded-md bg-muted px-2 py-1 text-xs">{msg}</div>}

      <div className="min-h-0 flex-1 space-y-2 overflow-y-auto">
        {convs.length === 0 && (
          <p className="px-2 text-xs text-muted-foreground">還沒有對話。聊一段會自動存到這裡。</p>
        )}
        {convs.length > 0 && (
          <Group title="對話">
            {convs.map((c) => <Row key={c.id} c={c} active={pathname === `/conversations/${c.id}`} onPick={goResume} onChange={load} onNav={onNavigate} />)}
          </Group>
        )}
      </div>

      {/* 登入身分＋登出（只在門鎖啟用時顯示） */}
      {me.auth_enabled && (
        <div className="mt-1 flex items-center justify-between gap-2 border-t px-2 pt-2 text-xs text-muted-foreground">
          <span className="min-w-0 truncate" title={me.user || ""}>👤 {me.user}</span>
          <a href="/auth/logout" className="shrink-0 hover:text-foreground hover:underline">登出</a>
        </div>
      )}
    </div>
  )
}

function Group({ title, hint, children }: { title: string; hint?: string; children: React.ReactNode }) {
  return (
    <section>
      <h3 title={hint} className="mb-0.5 px-2 text-[10px] font-medium uppercase tracking-wide text-muted-foreground/60">{title}</h3>
      <div>{children}</div>
    </section>
  )
}

function Row({ c, active, onPick, onChange, onNav}: {
  c: ConvRow; active: boolean; onPick: (id: number) => void; onChange: () => void; onNav?: () => void; }) {
  const [renaming, setRenaming] = useState(false)
  const [title, setTitle] = useState(c.title)
  const [menu, setMenu] = useState(false)
  const kebabRef = useRef<HTMLButtonElement>(null)
  const pressTimer = useRef<number | null>(null)
  const longPressed = useRef(false)

  // 手機：長按對話也開選單（沒有 hover，⋮ 又小難按）
  function pressStart() {
    longPressed.current = false
    pressTimer.current = window.setTimeout(() => { longPressed.current = true; setMenu(true) }, 450)
  }
  function pressCancel() { if (pressTimer.current) { clearTimeout(pressTimer.current); pressTimer.current = null } }
  function handlePick() {
    if (longPressed.current) { longPressed.current = false; return }  // 剛長按開了選單→這次不接著聊
    onPick(c.id)
  }
  async function rename() { await pages.renameConv(c.id, title); setRenaming(false); onChange() }

  if (renaming) return (
    <div className="flex items-center gap-1 px-1 py-0.5">
      <Input value={title} onChange={(e) => setTitle(e.target.value)} className="h-7" placeholder="改名…" autoFocus />
      <Button size="sm" onClick={rename}>存</Button>
    </div>
  )
  return (
    <div className={cn("group flex items-center gap-0.5 rounded-lg px-2 py-1 hover:bg-sidebar-accent", active && "bg-sidebar-accent")}>
      <button onClick={handlePick}
              onTouchStart={pressStart} onTouchEnd={pressCancel} onTouchMove={pressCancel}
              onContextMenu={(e) => { e.preventDefault(); setMenu(true) }}
              title={`${c.title || "未命名"}｜${c.created_at.slice(0, 10)}·${c.count} 則${c.yield_count > 0 ? `·聊出了 ${c.yield_count} 條核心理解` : ""}（點＝接著聊、長按＝選單）`}
              className="min-w-0 flex-1 truncate text-left text-sm">
        {c.title || "（未命名對話）"}
      </button>
      <button ref={kebabRef} onClick={(e) => { e.stopPropagation(); setMenu((v) => !v) }}
              aria-label="更多" title="更多"
              className={cn("shrink-0 rounded px-2 py-1 text-muted-foreground hover:bg-sidebar-accent hover:text-foreground",
                menu ? "opacity-100" : "opacity-100 md:opacity-0 md:transition md:group-hover:opacity-100")}>⋮</button>
      <ConvMenu c={c} open={menu} setOpen={setMenu} anchorRef={kebabRef}
                onResume={() => onPick(c.id)} onRename={() => setRenaming(true)} onChange={onChange} onNav={onNav} />
    </div>
  )
}
