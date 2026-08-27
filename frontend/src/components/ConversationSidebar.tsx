import { useEffect, useRef, useState } from "react"
import { Link, useLocation, useNavigate } from "react-router-dom"
import { pages, type ConvRow, type KnowledgeKind } from "@/lib/api"
import { DomainNav } from "@/components/DomainNav"
import { ROOT_NAME, useCurrentDomain, withDomain } from "@/lib/domain"
import { liveRecent, readRecent, touchRecent, type RecentDomain } from "@/lib/recent"
import { ConvMenu } from "@/components/ConvMenu"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"
import { PersonaSwitcher, usePersonaColor } from "@/components/PersonaSwitcher"

// 側欄的四種葉節點（spec 052/053）。順序＝**膜的流向**：
// 來源（原料）→ 對話（消化）→ 理解（地基）→ **應用**（輸出）。
// ⚠️ spec 053 把「文章」改名為「應用」：**「文章」是一種形式，「應用」是一種用途**
// ——換成用途，出海口才容得下決策、計畫、清單，而不只是散文。
//    ⓘ 本刀只換名字讓位置空出來，**沒有**真的多做幾種（YAGNI）。
// ⚠️ 這裡列的是**當前領域底下**（含子孫）的東西，不是全知識庫
// ——「全部的理解」＝站到根領域再看這一格。
const KINDS: { kind: KnowledgeKind; label: string; to: string }[] = [
  { kind: "source", label: "📚 來源", to: "/sources" },
  { kind: "conversation", label: "💬 互動", to: "/conversations" },
  { kind: "why_node", label: "💡 理解", to: "/roots" },
  { kind: "article", label: "🧩 應用", to: "/articles" },
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
  const [allDomains, setAllDomains] = useState<{ id: number; name: string; path: { id: number; name: string }[] }[]>([])
  const [recent, setRecent] = useState<RecentDomain[]>(() => readRecent())
  const personaColor = usePersonaColor()
  const load = () => Promise.all([pages.conversations(), pages.domainView(did), pages.domains()])
    .then(([c, v, d]) => { setConvs(c.conversations); setView(v); setAllDomains(d.domains) })
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
  useEffect(() => { load(); setRecent(touchRecent(did)) }, [did])

  // 最近的領域：⚠️ 過濾掉**已經不存在**的——列一個點了會壞的東西比不列更糟。
  const liveDomains = liveRecent(recent, new Set(allDomains.map((d) => d.id)))
    .map((r) => {
      const d = allDomains.find((x) => x.id === r.id)!
      return { id: r.id, label: d.path.map((p) => p.name).join(" / ") }
    })

  const isActive = (to: string) =>
    to === "/conversations" ? pathname === "/" || pathname.startsWith("/conversations")
      : to === "/sources" ? pathname.startsWith("/source")
      : pathname.startsWith(to)

  // ⚠️ ＋新對話帶著當前領域 ⇒ 新東西生在你站的地方（spec 051 FR-006 那條等著的線）
  const goNew = () => { navigate(withDomain("/?new=" + Date.now(), did)); onNavigate?.() }
  const goResume = (id: number) => { navigate(withDomain("/?resume=" + id, did)); onNavigate?.() }

  async function dedupe() {
    const p = await pages.dedupePreview()
    if (p.n_extra === 0) { setMsg("沒有重複的互動。"); return }
    if (!confirm(`發現 ${p.n_extra} 份重複（${p.n_groups} 組）。併掉多餘、重指 ${p.n_roots} 條理解的由來？`)) return
    const r = await pages.dedupeApply()
    setMsg(`✅ 併掉 ${r.removed} 份、重指 ${r.repointed} 條由來。`); load()
  }

  return (
    // ⚠️ spec 067：整條側欄跟著身分換色。文字標籤太弱——**切錯身分而不自知不會報錯**，
    //    而顏色是唯一你不看也會注意到的訊號。
    <div className="flex h-full flex-col gap-2 border-l-4 p-2"
         style={{ borderLeftColor: personaColor || "transparent" }}>
      <div className="flex items-center justify-between px-1">
        <Link to="/" onClick={onNavigate} className="py-1 text-lg font-bold">🧠 KnowField</Link>
        {onNavigate && <button onClick={onNavigate} aria-label="關閉" className="px-1 text-muted-foreground">✕</button>}
      </div>
      {/* spec 067：身分在**最上面**，導航列之上。同一條理由的更硬版本——
          領域放錯還能搬回來；身分放錯是**私人的東西寫進了工作的場**，而且不會報錯。 */}
      <PersonaSwitcher />
      {/* ⚠️ 導航列在「＋新互動」**之上**：你按下它之前，要先看得到它會生在哪（FR-001）。 */}
      <DomainNav onNavigate={onNavigate} />

      <Button size="sm" onClick={goNew}>＋ 新互動{did !== null && "（在這裡）"}</Button>

      {/* ── 五個入口（spec 053）：領域 · 來源 · 對話 · 理解 · 應用 ──────────
          ⚠️ spec 054：「領域」**連到管理頁**，不在側欄就地展開
          ——導覽（每天）與管理（偶爾）是兩件事，塞進同一個入口是我上一刀的錯。 */}
      <nav className="flex flex-col gap-0.5">
        <Link to={withDomain("/domains", did)} onClick={onNavigate}
          className={cn("flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm text-sidebar-foreground hover:bg-sidebar-accent",
            pathname.startsWith("/domains") && "bg-sidebar-accent font-medium")}>
          <span className="min-w-0 flex-1 truncate">🗂 領域</span>
          <span className="shrink-0 text-xs text-muted-foreground">{view?.children.length || ""}</span>
        </Link>
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
        {/* spec 072：別人的知識庫——⚠️ 刻意**不放進上面那組**：
            那一組是「當前領域底下的**你的**知識」，而這是外來的、還沒收進場的。 */}
        <Link to="/bases" onClick={onNavigate}
          className={cn("flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm text-sidebar-foreground hover:bg-sidebar-accent",
            isActive("/bases") && "bg-sidebar-accent font-medium")}>
          <span className="min-w-0 flex-1 truncate">🌍 別的知識庫</span>
        </Link>
      </nav>

      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto">
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
                      title="跳到它所在的領域"
                      className="block w-full truncate rounded-lg px-3 py-1 text-left text-xs text-muted-foreground hover:bg-sidebar-accent hover:text-foreground">
                {o.label}
              </button>
            ))}
          </section>
        )}

        {/* ── 底部＝**時間軸**：最近的領域 ＋ 最近的對話 ───────────────────
            ⚠️ 位置和時間是兩個軸，側欄不能只給一個——上面全是位置，這裡是時間。
            這兩格刻意**不**依領域過濾（「我昨天在哪／在聊什麼」跟你現在站哪無關）。 */}
        {liveDomains.length > 0 && (
          <section className="border-t pt-2">
            <h3 className="mb-0.5 px-2 text-[10px] font-medium uppercase tracking-wide text-muted-foreground/60">🕘 最近的領域</h3>
            {liveDomains.map((d) => (
              <button key={d.id} onClick={() => { go(d.id); onNavigate?.() }}
                      className={cn("block w-full truncate rounded-lg px-3 py-1 text-left text-xs hover:bg-sidebar-accent",
                                    d.id === did ? "text-foreground" : "text-muted-foreground hover:text-foreground")}>
                📁 {d.label}
              </button>
            ))}
          </section>
        )}

        <section className="border-t pt-2">
          <div className="mb-0.5 flex items-center justify-between px-2">
            <h3 className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground/60">🕘 最近的互動</h3>
            {convs.length > 0 && (
              <button onClick={dedupe} className="text-[11px] text-muted-foreground hover:underline">🧹 清理重複</button>
            )}
          </div>
          {msg && <div className="mx-2 rounded-md bg-muted px-2 py-1 text-xs">{msg}</div>}
          {convs.length === 0 && (
            <p className="px-2 text-xs text-muted-foreground">還沒有互動。聊一段會自動存到這裡。</p>
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
              title={`${c.title || "未命名"}｜${c.created_at.slice(0, 10)}·${c.count} 則${c.yield_count > 0 ? `·聊出了 ${c.yield_count} 條理解` : ""}（點＝接著聊、長按＝選單）`}
              className="min-w-0 flex-1 truncate text-left text-sm">
        {c.title || "（未命名互動）"}
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
