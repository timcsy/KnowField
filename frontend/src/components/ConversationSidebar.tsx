import { useEffect, useRef, useState } from "react"
import { Link, useLocation, useNavigate } from "react-router-dom"
import { pages, type ConvRow, type KnowledgeKind } from "@/lib/api"
import { DomainNav } from "@/components/DomainNav"
import { ROOT_NAME, useCurrentDomain, withDomain } from "@/lib/domain"
import { ConvMenu } from "@/components/ConvMenu"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"

// 側欄的四種葉節點（spec 052）。順序＝膜的流向：
// 來源（原料）→ 對話（消化）→ 核心理解（沉澱地基）→ 文章（輸出）。
// ⚠️ 這裡列的是**當前領域底下**的東西，不是全知識庫
// ——「全部的核心理解」＝站到根領域再看這一格（使用者裁決：當前領域含子領域）。
const KINDS: { kind: KnowledgeKind; label: string; to: string }[] = [
  { kind: "source", label: "📚 來源", to: "/sources" },
  { kind: "conversation", label: "💬 對話", to: "/conversations" },
  { kind: "why_node", label: "💡 核心理解", to: "/roots" },
  { kind: "article", label: "📝 文章", to: "/articles" },
]

// 單一側欄（各大 AI 手順）：Logo＋新對話＋導覽＋對話歷史，全在一欄。
// 與聊天頁靠 URL（?new/?resume）＋事件（kf-conversations-changed）解耦溝通。
export function ConversationSidebar({ onNavigate }: { onNavigate?: () => void }) {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  // spec 040：不再分暫存/永久——對話就是對話。
  const [convs, setConvs] = useState<ConvRow[]>([])
  // spec 047：目前打開的是哪一段。⚠️ 原本靠 `pathname === /conversations/:id` 判斷，
  // 那條路（檢視頁）已退場，而聊天頁的 `?resume=` 會被清掉 ⇒ 改由 ChatPage 廣播。
  const [activeId, setActiveId] = useState<number | null>(null)
  const [msg, setMsg] = useState<string | null>(null)
  const [me, setMe] = useState<{ user: string | null; auth_enabled: boolean }>({ user: null, auth_enabled: false })
  const { did, go } = useCurrentDomain()
  const [view, setView] = useState<Awaited<ReturnType<typeof pages.domainView>> | null>(null)
  const load = () => Promise.all([pages.conversations(), pages.domainView(did)])
    .then(([c, v]) => { setConvs(c.conversations); setView(v) })
    .catch(() => {})
  useEffect(() => {
    load()
    pages.me().then(setMe).catch(() => {})
    const h = () => load()
    const ha = (e: Event) => setActiveId((e as CustomEvent).detail as number | null)
    window.addEventListener("kf-active-conv", ha)
    window.addEventListener("kf-conversations-changed", h)
    return () => {
      window.removeEventListener("kf-active-conv", ha)
      window.removeEventListener("kf-conversations-changed", h)
    }
  }, [])
  // 換領域＝換視野。⚠️ did 進相依陣列，不然站到別的領域側欄不會變。
  useEffect(() => { load() }, [did])

  const isActive = (to: string) =>
    to === "/conversations" ? pathname === "/" || pathname.startsWith("/conversations")
      : to === "/sources" ? pathname.startsWith("/source")
      : pathname.startsWith(to)

  // ⚠️ ＋新對話帶著當前領域 ⇒ 新東西生在你站的地方（spec 051 FR-006 那條等著的線）
  const goNew = () => { navigate(withDomain("/?new=" + Date.now(), did)); onNavigate?.() }
  const goResume = (id: number) => { navigate(withDomain("/?resume=" + id, did)); onNavigate?.() }

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
      <Button size="sm" onClick={goNew}>＋ 新對話{did !== null && "（在這裡）"}</Button>

      {/* 麵包屑＝換地方 ＋「我現在會影響誰」 */}
      <DomainNav onNavigate={onNavigate} />

      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto">
        {/* 子領域：往下走 */}
        {(view?.children.length ?? 0) > 0 && (
          <nav className="flex flex-col gap-0.5">
            {view!.children.map((c) => (
              <button key={c.id} onClick={() => { go(c.id); onNavigate?.() }}
                      className="flex items-center gap-2 rounded-lg px-3 py-1.5 text-left text-sm hover:bg-sidebar-accent">
                <span className="min-w-0 flex-1 truncate">📁 {c.name}</span>
                <span className="shrink-0 text-xs text-muted-foreground">{c.count || ""}</span>
              </button>
            ))}
          </nav>
        )}

        {/* 這個領域裡有什麼——四種葉節點 */}
        <nav className="flex flex-col gap-0.5 border-t pt-2">
          {KINDS.map((k) => {
            const n = (view?.items || []).filter((i) => i.kind === k.kind).length
            return (
              <Link key={k.kind} to={withDomain(k.to, did)} onClick={onNavigate}
                className={cn("flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm text-sidebar-foreground hover:bg-sidebar-accent",
                  isActive(k.to) && "bg-sidebar-accent font-medium")}>
                <span className="min-w-0 flex-1 truncate">{k.label}</span>
                <span className="shrink-0 text-xs text-muted-foreground">{n || ""}</span>
              </Link>
            )
          })}
        </nav>

        {/* 通往外面＝場的邊界。⚠️ 寫「通往外面」不寫「糾纏」——後者看起來像有待辦要清，
            而這只是「從我站的地方看，這幾條通到別的領域」。 */}
        {(view?.outward.length ?? 0) > 0 && (
          <section className="border-t pt-2">
            <h3 className="mb-0.5 px-2 text-[10px] font-medium uppercase tracking-wide text-muted-foreground/60"
                title="從這個領域看出去，連到外面的東西（站到上一層，其中一些會變成內部連結）">
              ⛓ 通往外面 {view!.outward.length}
            </h3>
            {view!.outward.slice(0, 6).map((o) => (
              <button key={`${o.kind}:${o.ref}`} onClick={() => { go(o.domain_id); onNavigate?.() }}
                      title={`跳到它所在的領域`}
                      className="block w-full truncate rounded-lg px-3 py-1 text-left text-xs text-muted-foreground hover:bg-sidebar-accent hover:text-foreground">
                {o.label}
              </button>
            ))}
          </section>
        )}

        {/* 🕘 最近＝**時間軸**。⚠️ 位置和時間是兩個軸，側欄不能只給一個
            ——不然「我昨天在聊什麼」就不見了。這一格刻意**不**依領域過濾。 */}
        <section className="border-t pt-2">
          <div className="mb-0.5 flex items-center justify-between px-2">
            <h3 className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground/60">🕘 最近</h3>
            {convs.length > 0 && (
              <button onClick={dedupe} className="text-[11px] text-muted-foreground hover:underline">🧹 清理重複</button>
            )}
          </div>
          {msg && <div className="mx-2 rounded-md bg-muted px-2 py-1 text-xs">{msg}</div>}
          {convs.length === 0 && (
            <p className="px-2 text-xs text-muted-foreground">還沒有對話。聊一段會自動存到這裡。</p>
          )}
          {convs.slice(0, 8).map((c) => (
            <Row key={c.id} c={c} active={activeId === c.id} onPick={goResume} onChange={load} />
          ))}
        </section>
      </div>

      {/* ⚠️ FR-007：視野被領域縮過就要**說出來**——「找不到」和「這裡沒有」長得一模一樣 */}
      {did !== null && (
        <div className="border-t px-2 pt-2 text-[11px] text-muted-foreground">
          只顯示這個領域底下的。
          <button onClick={() => { go(null); onNavigate?.() }} className="ml-1 underline hover:text-foreground">
            看整個{ROOT_NAME}
          </button>
        </div>
      )}
      <Link to={withDomain("/domains", did)} onClick={onNavigate}
            className="rounded-lg px-3 py-1 text-xs text-muted-foreground hover:bg-sidebar-accent hover:text-foreground">
        ⚙ 整理台
      </Link>

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

function Row({ c, active, onPick, onChange }: {
  c: ConvRow; active: boolean; onPick: (id: number) => void; onChange: () => void }) {
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
                onResume={() => onPick(c.id)} onRename={() => setRenaming(true)} onChange={onChange} />
    </div>
  )
}
