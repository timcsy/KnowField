import { useEffect, useState } from "react"
import { Link, useLocation, useNavigate } from "react-router-dom"
import { pages, type ConvRow } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"

const NAV = [
  { label: "💬 對話", to: "/" },
  { label: "💡 核心理解", to: "/roots" },
  { label: "📚 來源", to: "/sources" },
]

// 單一側欄（各大 AI 手順）：Logo＋新對話＋導覽＋對話歷史，全在一欄。
// 與聊天頁靠 URL（?new/?resume）＋事件（kf-conversations-changed）解耦溝通。
export function ConversationSidebar({ onNavigate }: { onNavigate?: () => void }) {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const [perm, setPerm] = useState<ConvRow[]>([])
  const [temp, setTemp] = useState<ConvRow[]>([])
  const [msg, setMsg] = useState<string | null>(null)
  const [active, setActive] = useState<{ id: number | null; chapters: { title: string; start: number; end: number }[] | null }>({ id: null, chapters: null })

  const load = () => pages.conversations().then((r) => { setPerm(r.permanent); setTemp(r.temporary) }).catch(() => {})
  useEffect(() => {
    load()
    const h = () => load()
    window.addEventListener("kf-conversations-changed", h)
    return () => window.removeEventListener("kf-conversations-changed", h)
  }, [])
  // 聽 ChatPage 廣播的「本對話章節目錄」
  useEffect(() => {
    const h = (e: Event) => setActive((e as CustomEvent).detail)
    window.addEventListener("kf-active-chapters", h)
    return () => window.removeEventListener("kf-active-chapters", h)
  }, [])

  const isActive = (to: string) =>
    to === "/" ? pathname === "/" || pathname.startsWith("/conversations")
      : to === "/sources" ? pathname.startsWith("/source")
      : pathname.startsWith(to)

  const goNew = () => { navigate("/?new=" + Date.now()); onNavigate?.() }
  const goResume = (id: number) => { navigate("/?resume=" + id); onNavigate?.() }
  const goChapter = (start: number, end: number) => {
    if (active.id) { navigate(`/?resume=${active.id}&from=${start}&to=${end}`); onNavigate?.() }
  }

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

      {/* 本對話章節目錄（只在對話頁、有多章時）：點章節跳到聊天頁那章 */}
      {pathname === "/" && active.chapters && active.chapters.length > 1 && (
        <div className="border-t px-1 pt-2">
          <div className="mb-0.5 px-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground/60">本對話章節</div>
          <div className="space-y-0.5">
            {active.chapters.map((ch, i) => (
              <button key={i} onClick={() => goChapter(ch.start, ch.end)}
                      className="block w-full truncate rounded px-1.5 py-1 text-left text-xs text-muted-foreground hover:bg-sidebar-accent hover:text-foreground">
                🔖 {ch.title}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="mt-1 flex items-center justify-between border-t px-2 pt-2">
        <span className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground/60">對話紀錄</span>
        {(perm.length > 0 || temp.length > 0) && (
          <button onClick={dedupe} className="text-[11px] text-muted-foreground hover:underline">🧹 清理重複</button>
        )}
      </div>
      {msg && <div className="rounded-md bg-muted px-2 py-1 text-xs">{msg}</div>}

      <div className="min-h-0 flex-1 space-y-2 overflow-y-auto">
        {perm.length === 0 && temp.length === 0 && (
          <p className="px-2 text-xs text-muted-foreground">還沒有對話。聊一段會自動暫存到這裡。</p>
        )}
        {perm.length > 0 && (
          <Group title="對話">
            {perm.map((c) => <Row key={c.id} c={c} active={pathname === `/conversations/${c.id}`} onPick={goResume} onChange={load} onNav={onNavigate} />)}
          </Group>
        )}
        {temp.length > 0 && (
          <Group title="暫存" hint="自動存、7 天沒碰會清；想留就 📌 轉永久">
            {temp.map((c) => <Row key={c.id} c={c} active={false} onPick={goResume} onChange={load} onNav={onNavigate} temp />)}
          </Group>
        )}
      </div>
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

function Row({ c, active, onPick, onChange, onNav, temp }: {
  c: ConvRow; active: boolean; onPick: (id: number) => void; onChange: () => void; onNav?: () => void; temp?: boolean
}) {
  const [renaming, setRenaming] = useState(false)
  const [title, setTitle] = useState(c.title)
  async function rename() { await pages.renameConv(c.id, title); setRenaming(false); onChange() }
  async function promote() { await pages.promoteConv(c.id); onChange() }

  if (renaming) return (
    <div className="flex items-center gap-1 px-1 py-0.5">
      <Input value={title} onChange={(e) => setTitle(e.target.value)} className="h-7" placeholder="改名…" autoFocus />
      <Button size="sm" onClick={rename}>存</Button>
    </div>
  )
  return (
    <div className={cn("group flex items-center gap-0.5 rounded-lg px-2 py-1 hover:bg-sidebar-accent", active && "bg-sidebar-accent")}>
      <button onClick={() => onPick(c.id)}
              title={`${c.title || "未命名"}｜${c.created_at.slice(0, 10)}·${c.count} 則${c.why_node_id ? "·某條核心理解的由來" : ""}（點＝接著聊）`}
              className="min-w-0 flex-1 truncate text-left text-sm">
        {c.title || "（未命名對話）"}
      </button>
      <div className="flex shrink-0 items-center gap-1.5 text-xs text-muted-foreground opacity-0 transition group-hover:opacity-100">
        <Link to={`/conversations/${c.id}`} onClick={onNav} className="hover:text-foreground" title="唯讀檢視">檢視</Link>
        {temp && <button onClick={promote} className="hover:text-foreground" title="轉為永久保存">📌</button>}
        <button onClick={() => setRenaming(true)} className="hover:text-foreground" title="改名">✎</button>
      </div>
    </div>
  )
}
