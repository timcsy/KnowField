import { useEffect, useRef, useState } from "react"
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom"
import { pages, type ExtBase, type ExtTreeItem, type KnowledgeKind } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { readRecentDocs, type RecentDoc } from "@/lib/recentDocs"
import { cn } from "@/lib/utils"

// spec 074／080：開發模式的側欄。
// ⚠️ 使用者：「開發模式的側邊欄要幾乎跟互動模式一樣」——所以它照抄**同一個骨架**：
//    身分 → 你站在哪（導航列）→ ＋主要動作 → 這底下有什麼（帶計數）→ 最近（時間軸）→ 範圍說明。
//    ⓘ 這推翻了 spec 074 FR-006「persona 不進開發模式」：那時專案是**第二個場**、天然隔離；
//    spec 080 之後專案就是**來源**，跟你的東西同一個庫 ⇒ 身分當然也管得到它。
// ⚠️ 檔案樹仍**不在這裡**——它在主區的左半（IDE：最左是專案，接著才是檔案樹、預覽）。

//: ⚠️ 使用者：「在開發模式，仍然是領域、來源、互動、理解、應用」。
//: ⇒ **同一組五格**，只是換成**這個專案的**（它就是一個領域，所以 `domainView` 直接給得出來）。
//: 而互動那五格**完全看不到專案的東西**（`project_domain_ids`）——一條線，兩邊各自完整。
const KINDS: { kind: KnowledgeKind; label: string; view: string }[] = [
  { kind: "source", label: "📚 來源", view: "sources" },
  { kind: "conversation", label: "💬 互動", view: "conversations" },
  { kind: "why_node", label: "💡 理解", view: "roots" },
  { kind: "article", label: "🧩 應用", view: "articles" },
]

//: 檔案樹裡的「層」。⚠️ 順序是**膜的流向**（原則→路線圖→經驗→…）：
//: 位置固定，你才記得住它在哪一行。
const LAYERS: { key: string; label: string }[] = [
  { key: "principles.md", label: "📐 原則" },
  { key: "vision.md", label: "🗺 路線圖" },
  { key: "experience.md", label: "💡 經驗" },
  { key: "concepts", label: "🧩 概念" },
  { key: "history", label: "📜 歷史" },
  { key: "episodes", label: "🎬 場景" },
  { key: "draft", label: "✏️ 草稿" },
  { key: "skills", label: "🛠 技能" },
]

/** 把路徑歸成「層」：`knowledge/history/1.md` → `history`；`knowledge/vision.md` → `vision.md`。 */
export function layersOf(items: { path: string }[]): { key: string; n: number; only: string }[] {
  const bag = new Map<string, string[]>()
  for (const it of items) {
    const rel = it.path.replace(/^knowledge\//, "")
    const key = rel.includes("/") ? rel.split("/")[0] : rel
    bag.set(key, [...(bag.get(key) ?? []), it.path])
  }
  const known = LAYERS.map((l) => l.key)
  return [...bag.entries()]
    .sort((a, b) => {
      const ia = known.indexOf(a[0]), ib = known.indexOf(b[0])
      // 認得的照固定順序排前面；其餘照字母（⚠️ -1 會排到最前面，要先擋掉）
      if (ia !== ib) return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib)
      return a[0].localeCompare(b[0], "zh-Hant")
    })
    .map(([key, paths]) => ({ key, n: paths.length, only: paths.length === 1 ? paths[0] : "" }))
}

export function DevSidebar({ onNavigate }: { onNavigate?: () => void }) {
  const [sp, setSp] = useSearchParams()
  const { pathname } = useLocation()
  const nav = useNavigate()
  const [bases, setBases] = useState<ExtBase[] | null>(null)
  const [items, setItems] = useState<ExtTreeItem[]>([])
  const [snap, setSnap] = useState(0)
  const [did, setDid] = useState(0)
  // 這個專案底下有什麼——⚠️ 跟互動側欄**同一支 API**（它就是一個領域）
  const [view, setView] = useState<Awaited<ReturnType<typeof pages.domainView>> | null>(null)
  const [pickerOpen, setPickerOpen] = useState(false)
  const [recent, setRecent] = useState<RecentDoc[]>(() => readRecentDocs())
  const box = useRef<HTMLDivElement>(null)
  const bid = Number(sp.get("base") || 0)
  const doc = sp.get("doc") || ""

  useEffect(() => {
    pages.bases().then((d) => setBases(d.bases.filter((b) => b.status === "ok")))
      .catch(() => setBases([]))
  }, [])
  useEffect(() => {
    if (bases?.length && !bid) {
      const s = new URLSearchParams(sp); s.set("base", String(bases[0].id))
      setSp(s, { replace: true })
    }
  }, [bases, bid, sp, setSp])
  // 換專案／開檔都會動到這裡：層的計數要跟著那個專案走
  useEffect(() => {
    if (!bid) { setItems([]); setSnap(0); setDid(0); setView(null); return }
    pages.baseTree(bid)
      .then((d) => {
        setItems(d.items || []); setSnap(d.n_snapshot || 0); setDid(d.domain_id || 0)
        return d.domain_id ? pages.domainView(d.domain_id).then(setView) : setView(null)
      })
      .catch(() => { setItems([]); setSnap(0); setDid(0); setView(null) })
  }, [bid])
  useEffect(() => { setRecent(readRecentDocs()) }, [bid, doc])
  useEffect(() => {
    const h = (e: MouseEvent) => { if (!box.current?.contains(e.target as Node)) setPickerOpen(false) }
    window.addEventListener("mousedown", h)
    return () => window.removeEventListener("mousedown", h)
  }, [])

  /** 動網址；在「管理專案」頁時順便回到閱讀那一頁（你選它就是為了看它）。 */
  const go = (patch: Record<string, string>) => {
    const s = new URLSearchParams(sp)
    for (const [k, v] of Object.entries(patch)) v ? s.set(k, v) : s.delete(k)
    if (pathname === "/dev/bases") nav(`/dev?${s.toString()}`)
    else setSp(s)
    onNavigate?.()
  }
  // 換專案就放掉檔與展開——那是**另一個專案**的位置，留著只會指到空的
  const pickBase = (id: number) => {
    setPickerOpen(false); go({ base: String(id), doc: "", open: "", view: "" })
  }
  // 只有一份的層（`experience.md`）直接開；一整個資料夾就展開它
  const pickLayer = (l: { key: string; only: string }) =>
    l.only ? go({ view: "sources", doc: l.only, open: "" })
           : go({ view: "sources", open: l.key, doc: "" })

  const base = bases?.find((b) => b.id === bid)
  const layers = layersOf(items)
  const open = sp.get("open") || ""
  const cur = sp.get("view") || "sources"
  const nOf = (k: KnowledgeKind) => (view?.items || []).filter((i) => i.kind === k).length

  if (bases !== null && bases.length === 0) {
    return (
      <div className="flex min-h-0 flex-1 flex-col gap-2">
        <p className="px-2 pt-1 text-sm text-muted-foreground">
          還沒有專案。到{" "}
          <Link to="/dev/bases" onClick={onNavigate} className="text-primary hover:underline">⚙ 管理專案</Link>
          {" "}加一個進來。
        </p>
      </div>
    )
  }
  return (
    <div className="flex min-h-0 flex-1 flex-col gap-2" ref={box}>
      {/* ── 你站在哪：專案導航列（對應互動的 DomainNav）。⚠️ 在「＋」之上——
          按下之前要先看得到你在哪個專案 ── */}
      <div className="relative px-1">
        <button onClick={() => setPickerOpen((v) => !v)}
                className="flex w-full items-center gap-1 rounded-lg px-2 py-1.5 text-sm font-medium hover:bg-sidebar-accent">
          <span className="min-w-0 flex-1 truncate text-left">
            📁 {base ? (base.name || base.repo) : "選一個專案"}
          </span>
          <span className="shrink-0 text-xs text-muted-foreground">▾</span>
        </button>
        {pickerOpen && (
          <ul className="absolute left-1 right-1 z-20 mt-0.5 max-h-64 overflow-y-auto rounded-lg border bg-popover p-1 shadow-md">
            {(bases ?? []).map((b) => (
              <li key={b.id}>
                <button onClick={() => pickBase(b.id)} title={`${b.repo} · ${b.branch}`}
                  className={cn("flex w-full items-center gap-2 rounded px-2 py-1.5 text-sm hover:bg-sidebar-accent",
                    bid === b.id && "font-medium")}>
                  <span className="min-w-0 flex-1 truncate text-left">📁 {b.name || b.repo}</span>
                  <span className="shrink-0 text-xs text-muted-foreground">{b.n_items}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <Button size="sm" onClick={() => { nav("/dev/bases"); onNavigate?.() }}>＋ 新增專案</Button>

      {/* ── 這個專案底下有什麼（對應互動的五格）。⚠️ 帶計數：說不出有幾份，
          「找不到」就會被讀成「它沒有」 ── */}
      {/* ── 五格（領域／來源／互動／理解／應用）——⚠️ 跟互動**同一組**，
          只是換成這個專案的。而思考那邊完全看不到專案的東西。 ── */}
      <nav className="flex flex-col gap-0.5">
        <button onClick={() => go({ view: "domains", doc: "", open: "" })}
          className={cn("flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm hover:bg-sidebar-accent",
            cur === "domains" && "bg-sidebar-accent font-medium")}>
          <span className="min-w-0 flex-1 truncate text-left">🗂 領域</span>
          <span className="shrink-0 text-xs text-muted-foreground">{view?.children.length || ""}</span>
        </button>
        {KINDS.map((k) => (
          <button key={k.kind} onClick={() => go({ view: k.view, doc: "", open: "" })}
            className={cn("flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm hover:bg-sidebar-accent",
              cur === k.view && "bg-sidebar-accent font-medium")}>
            <span className="min-w-0 flex-1 truncate text-left">{k.label}</span>
            <span className="shrink-0 text-xs text-muted-foreground">{nOf(k.kind) || ""}</span>
          </button>
        ))}
      </nav>

      {/* ── 站在「來源」時，底下才展開那個專案的層（檔案樹的目錄仍在主區）── */}
      {cur === "sources" && (
        <nav className="flex flex-col gap-0.5 border-t pt-1">
          {layers.map((l) => {
            const label = LAYERS.find((x) => x.key === l.key)?.label
                          ?? `📄 ${l.key.replace(/\.md$/, "")}`
            const active = l.only ? doc === l.only : open === l.key
            return (
              <button key={l.key} onClick={() => pickLayer(l)}
                className={cn("flex items-center gap-2 rounded-lg py-1 pl-6 pr-3 text-xs hover:bg-sidebar-accent",
                  active ? "text-foreground" : "text-muted-foreground hover:text-foreground",
                  active && "bg-sidebar-accent font-medium")}>
                <span className="min-w-0 flex-1 truncate text-left">{label}</span>
                <span className="shrink-0 text-[11px]">{l.n}</span>
              </button>
            )
          })}
          {/* ⚠️ 有快照、樹是空的 ＝ 還沒落成來源；說「沒有東西」是假話 */}
          {layers.length === 0 && snap > 0 && (
            <p className="px-3 py-1.5 text-xs text-muted-foreground">
              抓下來了（{snap} 份），但還沒落成來源——到主區按「重新抓取」。
            </p>
          )}
        </nav>
      )}

      {/* ── 底部＝**時間軸**（對應互動的「最近的互動」）。⚠️ 刻意不依專案過濾：
          「我昨天在看什麼」跟你現在站哪個專案無關 ── */}
      <div className="min-h-0 flex-1 overflow-y-auto">
        {recent.length > 0 && (
          <section className="border-t pt-2">
            <h3 className="mb-0.5 px-2 text-[10px] font-medium uppercase tracking-wide text-muted-foreground/60">
              🕘 最近開的檔
            </h3>
            {recent.map((r) => {
              const b = bases?.find((x) => x.id === r.base)
              return (
                <button key={`${r.base}:${r.path}`}
                        onClick={() => go({ base: String(r.base), doc: r.path, open: "" })}
                        title={`${b?.name || b?.repo || r.base} / ${r.path}`}
                        className={cn("block w-full truncate rounded-lg px-3 py-1 text-left text-xs hover:bg-sidebar-accent",
                          r.base === bid && r.path === doc
                            ? "text-foreground" : "text-muted-foreground hover:text-foreground")}>
                  📄 {r.path.replace(/^knowledge\//, "")}
                </button>
              )
            })}
          </section>
        )}
      </div>

      <Link to="/dev/bases" onClick={onNavigate}
        className={cn("rounded-lg px-3 py-1.5 text-sm hover:bg-sidebar-accent",
          pathname === "/dev/bases"
            ? "bg-sidebar-accent font-medium text-foreground"
            : "text-muted-foreground hover:text-foreground")}>
        ⚙ 管理專案
      </Link>

      {/* ⚠️ 對應互動那條「只顯示這個領域底下的」——範圍被縮過就要說出來。
          而這裡要多說一句**這是誰的東西**：看不出是別人的，就等於冒充你自己的知識。 */}
      <div className="border-t px-2 pt-2 text-[11px] text-muted-foreground">
        這裡讀的是<span className="font-medium text-foreground">別人專案</span>寫下的東西
        ——思考那邊看不到它們{did ? "" : "（⚠ 這個專案還沒歸到領域）"}。
      </div>
    </div>
  )
}
