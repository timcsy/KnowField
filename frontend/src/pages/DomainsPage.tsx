import { useEffect, useMemo, useRef, useState } from "react"
import { useNavigate } from "react-router-dom"
import { pages, type KnowledgeItem, type KnowledgeKind, type KnowledgeRef } from "@/lib/api"
import { keyOf, pickedRefs as pickRefs, inDomain as inDom, KIND_ORDER } from "@/lib/knowledge"
import { useCurrentDomain, withDomain } from "@/lib/domain"
import { armLongPress } from "@/lib/longpress"
import { isTap } from "@/lib/tap"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { SuggestOrganize } from "@/components/SuggestOrganize"
import { cn } from "@/lib/utils"
import { DomainContextPanel } from "@/components/DomainContext"

// 整理台（spec 050，階段 45）＝領域樹 ＋ 待整理清冊。
// ⚠️ **領域＝節點、主題 Topic＝從根到節點的路徑**——路徑由後端從 parent_id 導出，這裡只顯示。
// ⚠️ **`domain_id = null` 就是「根領域」**——它是樹的**頂**，不是樹外面的一個桶子。
//    原本叫它「未歸屬」並另外列一格，整理起來就不像檔案系統：東西在樹外面，
//    你沒辦法「在它現在的位置底下開一個子領域再拖進去」。名字錯了，位置也錯了。
// ⓘ 資料模型一個字都沒改（仍是 null）——改的是它在樹上的**位置**與**名字**。
// ⚠️ 階段 44 只做了「已歸屬的對話能搬」，而正式庫那樣的東西是 0 件
//    ——整理的**起點動作**（把未歸屬的搬進去）當時在介面上不存在。這一頁就是補那個。
type Domain = { id: number; name: string; parent_id: number | null; path: { id: number; name: string }[] }

// 根領域的顯示名。⚠️ 它**不是**資料庫裡的一列——`domain_id = null` 就是它。
const ROOT_NAME = "知識庫"

const KIND_LABEL: Record<KnowledgeKind, string> = {
  source: "📚 來源", conversation: "💬 互動", why_node: "💡 理解", article: "🧩 應用",
}

export default function DomainsPage() {
  const nav = useNavigate()
  const [domains, setDomains] = useState<Domain[] | null>(null)
  const [items, setItems] = useState<KnowledgeItem[]>([])
  // ⚠️ 從側欄點「領域」進來時，**接上你站的地方**——不然管理頁每次都從根開始，
  //    你得再找一次自己剛剛在哪。
  const { did, go } = useCurrentDomain()
  // ⚠️ **不要**另外存一份 `sel`：當前位置只有一個真相，就是 URL 裡的 `did`。
  //    兩份真相的下場就是側欄進去了、清單沒進去（2026-08-26 實跑撞到）。
  const sel = did
  const [name, setName] = useState("")
  const [msg, setMsg] = useState<string | null>(null)
  const [picked, setPicked] = useState<Set<string>>(new Set())
  const [filter, setFilter] = useState<KnowledgeKind | "all">("all")
  const [q, setQ] = useState("")
  // 遺骸：封存過的東西。⚠️ 「刪除又要不能不見」的那個**見**就在這裡
  //    ——沒有這一格，封存跟刪除在使用者眼裡沒有差別。
  const [attic, setAttic] = useState<Awaited<ReturnType<typeof pages.archived>> | null>(null)
  const [showAttic, setShowAttic] = useState(false)
  const [dropOn, setDropOn] = useState<number | null | "none">("none")
  // 檔案總管的三件事（spec 057）
  const [sort, setSort] = useState<{ by: "name" | "kind" | "at"; asc: boolean }>({ by: "at", asc: false })
  const [menu, setMenu] = useState<{ x: number; y: number; kind: "domain"; d: Domain }
                                  | { x: number; y: number; kind: "item"; i: KnowledgeItem } | null>(null)
  const anchor = useRef<string | null>(null)   // shift 連選的起點
  // ⚠️ 觸控上捲動與點選開頭一模一樣 ⇒ 記下按下的位置，放開時才判斷得出來
  const pressAt = useRef<{ x: number; y: number } | null>(null)
  // ⚠️ 長按觸發之後瀏覽器**還會送一個 click**，不擋掉的話它會立刻把剛選的取消。
  //    沿用側欄既有的一次性旗標作法（`ConversationSidebar` 的 `longPressed`）。
  const longPressed = useRef(false)
  // ⚠️ **瀏覽器在觸控長按時會自己送 `contextmenu`**（Android Chrome / iOS Safari 都會）。
  //    我只想到自己那條 450ms 的路徑，沒想到原生還有一條 ⇒ 批次模式進去了、選單同時跳出來。
  //    `contextmenu` 事件本身不帶 `pointerType`，所以要自己記住上一次是什麼裝置。
  const lastPointer = useRef<string>("mouse")
  // 手機沒有 hover 也沒有右鍵（spec 058）⇒ 明確的「選取模式」＋ 樹抽屜
  const [selecting, setSelecting] = useState(false)
  const [tree, setTree] = useState(false)
  // 搬東西時若有糾纏，先問。⚠️ 糾纏不是我們建的，是**既有連結被樹拆散**。
  const [ask, setAsk] = useState<{ items: KnowledgeRef[]; to: number | null
                                   tangles: { label: string }[] } | null>(null)

  const load = () => Promise.all([pages.domains(), pages.inventory(), pages.archived()])
    .then(([d, inv, a]) => { setDomains(d.domains); setItems(inv.items); setAttic(a) })
    .catch(() => setDomains([]))
  useEffect(() => { load() }, [])

  async function create() {
    if (!name.trim()) return
    const r = await pages.createDomain(name.trim(), sel)
    if (!r.ok) { setMsg(r.err || "建不起來"); return }
    setName(""); setMsg(null); load()
  }
  async function rename(d: Domain) {
    const name = prompt("改名為：", d.name)
    if (name === null || !name.trim() || name.trim() === d.name) return
    const r = await pages.renameDomain(d.id, name.trim())
    setMsg(r.ok ? null : (r.err || "改不了名"))
    load()
  }

  // 封存＝**離開活的場，留下遺骸**（spec 055）。先說出會帶走什麼再問（FR-007）。
  // ⚠️ 它會**連帶封存整棵子樹**——不上移，之後可以一起復原。
  async function archiveDomain(d: Domain) {
    const p = await pages.archiveDomainPreview(d.id)
    const what = [p.items && `${p.items} 件知識`, p.children && `${p.children} 個子領域`]
      .filter(Boolean).join("、")
    const line = what
      ? `封存「${d.name}」？\n\n它底下的 ${what} 會一起封存——離開活的知識庫，但不會消失，之後可以一起復原。`
      : `封存「${d.name}」？（它是空的）`
    if (!confirm(line)) return
    await pages.archiveDomain(d.id)
    // ⚠️ 站在被封存的領域上就要移走——不能站在一個不在活樹上的地方（FR-008）
    if (did === d.id) go(p.to, { replace: true })
    setMsg(what ? `封存了「${d.name}」——連同 ${what}` : `封存了「${d.name}」`)
    load()
  }

  async function moveDomain(id: number, parent: number | null) {
    const r = await pages.moveDomain(id, parent)
    setMsg(r.ok ? null : (r.err || "搬不動"))   // 成環會被後端擋下並回原因（不靜默照做）
    load()
  }

  // ── 搬動：一律走批次（單件＝一個元素的清單，不留第二條路）─────────────
  async function startMove(refs: KnowledgeRef[], to: number | null) {
    if (refs.length === 0) return
    const r = await pages.tangles(refs, to)
    if (r.tangles.length === 0) { await doMove(refs, to, false); return }   // 沒糾纏就直接搬
    setAsk({ items: refs, to, tangles: r.tangles })
  }
  // 第二次的死。⚠️ 只出現在**遺骸區**——活的東西沒有捷徑通往這裡。
  async function erase(refs: KnowledgeRef[], label: string) {
    const p = await pages.pointersTo(refs)
    const who = p.pointers.length
      ? `\n\n⚠️ 這些東西指著它，抹掉之後它們會指向一塊空白：\n` +
        p.pointers.slice(0, 8).map((x) => `・${x.label}`).join("\n") +
        (p.pointers.length > 8 ? `\n・…共 ${p.pointers.length} 個` : "")
      : "\n\n（沒有東西指著它）"
    if (!confirm(`抹除${label}？\n\n這是第二次的死——內容會直接消失，救不回來。\n` +
                 `只會留下一塊疤：「這裡曾經有東西，在今天被抹掉了」。${who}`)) return
    const r = await pages.eraseKnowledge(refs)
    if (!r.ok) { setMsg(r.err || "抹不掉"); return }
    setMsg(`抹除了${label}`); load()
  }

  async function archivePicked() {
    const refs = pickedRefs()
    if (!refs.length) return
    if (!confirm(`封存這 ${refs.length} 件？\n\n它們會離開活的知識庫，但不會消失——之後可以復原。`)) return
    await pages.archiveKnowledge(refs)
    setPicked(new Set()); setMsg(`封存了 ${refs.length} 件`)
    load()
  }

  async function doMove(refs: KnowledgeRef[], to: number | null, bring: boolean) {
    const r = await pages.moveKnowledge(refs, to, bring)
    setAsk(null); setPicked(new Set())
    setMsg(r.tangles && !bring
      ? `搬好 ${r.moved} 件——留下 ${r.tangles} 條糾纏`
      : `搬好 ${r.moved} 件`)
    load()
  }

  // 鍵盤導覽（桌機習慣）。⚠️ 只在沒有輸入框聚焦時才吃鍵，否則打字會被吃掉。
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement
      if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.isContentEditable)) return
      if (e.key === "Escape") { exitBatch(); setMenu(null); return }
      if (e.key !== "ArrowDown" && e.key !== "ArrowUp" && e.key !== "Enter") return
      const list = shown(inDomain(sel))
      if (!list.length) return
      e.preventDefault()
      const cur = anchor.current ? list.findIndex((x) => keyOf(x) === anchor.current) : -1
      if (e.key === "Enter") { if (cur >= 0) open(list[cur]); return }
      const nxt = e.key === "ArrowDown"
        ? Math.min(cur + 1, list.length - 1)
        : Math.max(cur - 1, 0)
      anchor.current = keyOf(list[nxt])
      setPicked(new Set([anchor.current]))
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  })

  // ⚠️ **批次模式有兩個來源**（長按設 `selecting`、直接勾選只動 `picked`），
  //    而按鈕原本只看 `selecting` ⇒ 用勾選進入時它顯示「選取」，按下去反而**推得更深**，
  //    使用者就退不出來了（2026-08-26 回報）。⇒ 收斂成一個推導值。
  const inBatch = selecting || picked.size > 0
  const exitBatch = () => { setSelecting(false); setPicked(new Set()) }

  const kids = (p: number | null) => (domains || []).filter((d) => d.parent_id === p)
  const inDomain = (id: number | null) => inDom(items, id)
  const unfiled = useMemo(() => inDomain(null), [items])

  const pickedRefs = (): KnowledgeRef[] => pickRefs(items, picked)

  // ⚠️ 檔案總管的選取模型：**點一下＝開啟**，不是選取。
  //    勾選框只在「已經有選取」或滑鼠移過去時出現——常駐的勾選框是整理模式的家具，
  //    而你多數時候只是想看看（spec 057）。
  function toggle(i: KnowledgeItem) {
    const k = keyOf(i)
    anchor.current = k
    setPicked((p) => { const n = new Set(p); n.has(k) ? n.delete(k) : n.add(k); return n })
  }

  /** shift 連選：在**目前看到的順序**上取區間——不是在原始清冊上。 */
  function rangeTo(i: KnowledgeItem, rows: KnowledgeItem[]) {
    const k = keyOf(i)
    const a = anchor.current
    if (!a) { toggle(i); return }
    const ks = rows.map(keyOf)
    const s0 = ks.indexOf(a), s1 = ks.indexOf(k)
    if (s0 < 0 || s1 < 0) { toggle(i); return }
    const [lo, hi] = s0 < s1 ? [s0, s1] : [s1, s0]
    setPicked(new Set([...picked, ...ks.slice(lo, hi + 1)]))
  }

  /** 點一下：對話 → 開啟；其餘 → 到它的頁。 */
  function open(i: KnowledgeItem) {
    if (i.kind === "conversation") nav(`/?resume=${i.ref}`)
    else if (i.kind === "article") nav(`/articles/${i.ref}`)
    else if (i.kind === "source") nav(`/source?u=${encodeURIComponent(String(i.ref))}`)
    else nav(withDomain("/roots", sel))
  }

  // ── 拖放（Pointer Events，不是 HTML5 DnD）────────────────────────────
  // ⚠️ **HTML5 drag-and-drop 在觸控裝置上根本不會觸發**，而這是個 PWA
  //    ——用 draggable/onDrop 的話手機上會安靜地不能拖，什麼錯都不報。
  //    Pointer Events 滑鼠與觸控同一條路，而且合成事件驅得動 ⇒ 驗得到。
  // 拖的是**目前選取的那批**；拖一個沒被選取的，就當成只拖它自己。
  function beginDrag(e: React.PointerEvent, i: KnowledgeItem) {
    // ⚠️ **觸控不啟用拖曳。** 捲動與拖曳共用 pointerdown：捲一下 `armed` 就變 true，
    //    手指放開時若剛好停在某個資料夾列上，會**真的把知識搬過去**——而資料夾就排在
    //    清單最上面。滑一下就悄悄搬走東西，且畫面上只閃過一句「搬好 1 件」。
    //    手機要搬東西走長按選單的「搬到…」（spec 058 已把手機拖放列為 out of scope）。
    if (e.pointerType !== "mouse") return
    if (e.button !== 0) return
    // ⚠️ 別碰勾選框：它自己有 onChange，pointerdown 攔下來兩邊會互相抵消
    if ((e.target as HTMLElement).tagName === "INPUT") return
    const key = keyOf(i)
    const batch = picked.has(key) ? picked : new Set([key])
    // ⚠️ **選取只在真的拖起來時才動**——在 pointerdown 就 setPicked 的話，
    //    它會跟同一個元素上的點擊／勾選打架（2026-08-26 實跑：勾選框完全沒反應）。
    const start = { x: e.clientX, y: e.clientY }
    let armed = false

    const targetAt = (x: number, y: number): { to: number | null } | null => {
      const el = document.elementFromPoint(x, y)?.closest("[data-drop]") as HTMLElement | null
      if (!el) return null
      const v = el.dataset.drop!
      return { to: v === "unfiled" ? null : Number(v) }
    }
    const onMove = (ev: PointerEvent) => {
      if (!armed && Math.hypot(ev.clientX - start.x, ev.clientY - start.y) < 6) return
      if (!armed) { armed = true; if (batch !== picked) setPicked(batch) }   // 真的拖了才選取
      const t = targetAt(ev.clientX, ev.clientY)
      const next = t ? t.to : "none"
      // ⚠️ 只在**真的變了**才 setState——pointermove 一秒幾十次，
      // 每次都 setState 等於把整份清冊重畫幾十次。
      setDropOn((d) => (d === next ? d : next))
    }
    const onUp = (ev: PointerEvent) => {
      window.removeEventListener("pointermove", onMove)
      window.removeEventListener("pointerup", onUp)
      setDropOn("none")
      if (!armed) return                 // 只是點一下，不是拖
      const t = targetAt(ev.clientX, ev.clientY)
      if (!t) return
      const refs = items.filter((x) => batch.has(keyOf(x))).map((x) => ({ kind: x.kind, ref: x.ref }))
      if (refs.length) startMove(refs, t.to)
    }
    window.addEventListener("pointermove", onMove)
    window.addEventListener("pointerup", onUp)
  }
  const dropProps = (to: number | null) => ({ "data-drop": to === null ? "unfiled" : String(to) })

  // ⚠️ 這兩個是**函式**不是元件：定義在元件內部的 JSX 元件每次 render 都是新型別，
  // React 會把整棵子樹卸載重掛——拖曳時一秒幾十次 render，105 列就這樣卡死頁面。
  /** 抽屜裡的樹：只導覽。⚠️ 管理動作走長按選單，不在這裡塞四個小圖示（手指按不到）。 */
  const renderMobileNode = (d: Domain, depth: number) => (
    <div key={`m${d.id}`}>
      <button onClick={() => { go(d.id); setTree(false) }}
              style={{ paddingLeft: 8 + depth * 16 }}
              className={cn("flex w-full items-center gap-2 rounded py-1.5 pr-2 text-left text-sm hover:bg-muted",
                            sel === d.id && "bg-muted font-medium")}>
        <span className="min-w-0 flex-1 truncate">📁 {d.name}</span>
        <span className="text-xs text-muted-foreground">{inDomain(d.id).length || ""}</span>
      </button>
      {kids(d.id).map((k) => renderMobileNode(k, depth + 1))}
    </div>
  )

  const renderNode = (d: Domain, depth: number) => (
    <div key={d.id}>
      <div className={cn("group flex items-center gap-2 rounded px-2 py-1 hover:bg-muted",
                         sel === d.id && "bg-muted",
                         dropOn === d.id && "outline outline-2 outline-primary")}
           style={{ paddingLeft: 8 + depth * 16 }} {...dropProps(d.id)}>
        <button onClick={() => go(sel === d.id ? null : d.id)} className="min-w-0 flex-1 truncate text-left text-sm">
          📁 {d.name}
          <span className="ml-2 text-xs text-muted-foreground">{inDomain(d.id).length || ""}</span>
        </button>
        {/* ⚠️ 用圖示不用文字：`opacity-0` 只是**視覺隱藏，仍然佔寬度**
            ——四個文字按鈕會把 280px 面板裡深層節點的名字擠到零寬（truncate 讓它靜靜消失）。 */}
        <div className="ml-auto flex shrink-0 items-center gap-0.5 text-xs text-muted-foreground">
          <button onClick={() => go(d.id)} title="站到這裡"
                  className="rounded px-1 py-0.5 hover:bg-background hover:text-foreground">📍</button>
          <button onClick={() => rename(d)} title="改名"
                  className="rounded px-1 py-0.5 hover:bg-background hover:text-foreground">✏️</button>
          {d.parent_id !== null && (
            <button onClick={() => moveDomain(d.id, null)} title="移到最上層"
                    className="rounded px-1 py-0.5 hover:bg-background hover:text-foreground">⤴</button>
          )}
          <button onClick={() => archiveDomain(d)} title="封存（連同底下的知識一起離開活的知識庫；不會消失，可復原）"
                  className="rounded px-1 py-0.5 hover:bg-background hover:text-destructive">📦</button>
        </div>
      </div>
      {kids(d.id).map((k) => renderNode(k, depth + 1))}
    </div>
  )

  const selected = (domains || []).find((d) => d.id === sel)
  const needle = q.trim().toLowerCase()
  const KIND_RANK: Record<KnowledgeKind, number> = { source: 0, conversation: 1, why_node: 2, article: 3 }
  const shown = (list: KnowledgeItem[]) => {
    const out = list
      .filter((i) => filter === "all" || i.kind === filter)
      .filter((i) => !needle || i.label.toLowerCase().includes(needle))
    const dir = sort.asc ? 1 : -1
    return [...out].sort((a, b) =>
      sort.by === "name" ? dir * a.label.localeCompare(b.label, "zh-Hant")
      : sort.by === "at" ? dir * ((a.at || "") < (b.at || "") ? -1 : (a.at || "") > (b.at || "") ? 1 : 0)
      : dir * (KIND_RANK[a.kind] - KIND_RANK[b.kind] || a.label.localeCompare(b.label, "zh-Hant")))
  }
  /** 目前這一層看到的子資料夾（檔案總管：資料夾排在檔案前面）。 */
  const folders = kids(sel).filter((d) => !needle || d.name.toLowerCase().includes(needle))
  const rows = shown(inDomain(sel))
  const path = selected ? selected.path : []

  /** 觸控長按。⚠️ 與捲動互斥：移動超過門檻就取消（見 `lib/longpress`）。 */
  function pressHold(e: React.PointerEvent, fire: () => void) {
    if (e.pointerType === "mouse") return
    const h = armLongPress(e.clientX, e.clientY, fire)
    const mv = (ev: PointerEvent) => h.movedFar(ev.clientX, ev.clientY)
    const up = () => { h.cancel(); window.removeEventListener("pointermove", mv); window.removeEventListener("pointerup", up) }
    window.addEventListener("pointermove", mv)
    window.addEventListener("pointerup", up)
  }

  const folderRow = (d: Domain) => (
    <div key={`d${d.id}`} {...dropProps(d.id)}
         onClick={(e) => {
           if (longPressed.current) { longPressed.current = false; return }
           if (isTap(pressAt.current, { x: e.clientX, y: e.clientY })) go(d.id)
         }}
         onPointerDown={(e) => {
           lastPointer.current = e.pointerType
           pressAt.current = { x: e.clientX, y: e.clientY }
           longPressed.current = false
           // ⓘ 資料夾**不進批次**（批次的對象是知識，不是領域），
           //    而手機也**不出長按選單**（使用者要求）⇒ 它的動作走列尾那顆 ⋯
         }}
         onContextMenu={(e) => {
           e.preventDefault()                       // 觸控也要擋，否則跳出系統的複製／選取泡泡
           if (lastPointer.current !== "mouse") return
           setMenu({ x: e.clientX, y: e.clientY, kind: "domain", d })
         }}
         title="點一下進去；⋯ 有更多"
         className={cn("group relative grid cursor-pointer grid-cols-[1.5rem_minmax(0,1fr)] md:grid-cols-[1.5rem_minmax(0,1fr)_5rem_7rem] items-center gap-2 rounded px-2 py-1.5 text-sm hover:bg-muted",
                       dropOn === d.id && "outline outline-2 outline-primary")}>
      <span />
      <span className="min-w-0 truncate font-medium">📁 {d.name}</span>
      <span className="hidden text-xs text-muted-foreground md:block">資料夾</span>
      <span className="hidden text-xs text-muted-foreground md:block">
        {inDomain(d.id).length ? `${inDomain(d.id).length} 件` : "空的"}
      </span>
      {/* ⚠️ 手機沒有右鍵、也不再有長按選單 ⇒ 這顆必須**常駐**，否則資料夾的
          改名／搬動／封存在手機上到不了（同一族的第三次） */}
      <button onClick={(e) => { e.stopPropagation()
                                setMenu({ x: e.clientX, y: e.clientY, kind: "domain", d }) }}
              aria-label="更多"
              className="absolute right-2 rounded px-2 py-0.5 text-muted-foreground hover:bg-background hover:text-foreground md:opacity-0 md:group-hover:opacity-100">⋯</button>
    </div>
  )

  const itemRow = (i: KnowledgeItem) => {
    const k = keyOf(i)
    const on = picked.has(k)
    return (
      <div key={k} onPointerDown={(e) => {
             lastPointer.current = e.pointerType
             pressAt.current = { x: e.clientX, y: e.clientY }
             longPressed.current = false
             beginDrag(e, i)
             // 觸控長按＝**進批次模式並選取這一件**（Android／Drive／Gmail 慣例）。
             // ⓘ 不出選單：選單裡那四項在批次模式的底部列全都有，而長按→選單→選取是兩下。
             pressHold(e, () => { longPressed.current = true; setSelecting(true); toggle(i) })
           }}
           onClick={(e) => {
             if (longPressed.current) { longPressed.current = false; return }  // 剛長按選了→別再 toggle 掉
             // ⚠️ 滑動不是點選——捲清單時瀏覽器不保證會抑制 click
             if (!isTap(pressAt.current, { x: e.clientX, y: e.clientY })) return
             if (e.metaKey || e.ctrlKey) toggle(i)
             else if (e.shiftKey) rangeTo(i, rows)
             else if (inBatch) toggle(i)                    // 批次模式 → 點一下＝加選
             else open(i)
           }}
           onDoubleClick={() => open(i)}
           onContextMenu={(e) => {
             e.preventDefault()
             if (lastPointer.current !== "mouse") return
             setMenu({ x: e.clientX, y: e.clientY, kind: "item", i })
           }}
           className={cn("group grid cursor-pointer select-none grid-cols-[1.5rem_minmax(0,1fr)] md:grid-cols-[1.5rem_minmax(0,1fr)_5rem_7rem] items-center gap-2 rounded px-2 py-1.5 text-sm hover:bg-muted",
                         on && "bg-muted")}>
        {/* ⚠️ 勾選框不常駐：沒選任何東西時它只在 hover 出現——常駐＝整理模式的家具 */}
        <input type="checkbox" checked={on} onClick={(e) => e.stopPropagation()} onChange={() => toggle(i)}
               className={cn("h-4 w-4",
                             // ⚠️ 觸控沒有 hover ⇒ 只靠 group-hover 的話手機上選不到任何東西
                             !on && !inBatch && "opacity-0 group-hover:opacity-100")} />
        <span className="min-w-0 truncate">{KIND_LABEL[i.kind].slice(0, 2)} {i.label}</span>
        <span className="hidden text-xs text-muted-foreground md:block">{KIND_LABEL[i.kind].slice(2).trim()}</span>
        <span className="hidden text-xs text-muted-foreground md:block">{(i.at || "").slice(0, 10)}</span>
      </div>
    )
  }

  const SortHead = ({ by, children, cls }: { by: "name" | "kind" | "at"; children: React.ReactNode; cls?: string }) => (
    <button onClick={() => setSort((s0) => ({ by, asc: s0.by === by ? !s0.asc : true }))}
            className={cn("text-left text-xs text-muted-foreground hover:text-foreground", cls)}>
      {children}{sort.by === by && (sort.asc ? " ▲" : " ▼")}
    </button>
  )

  return (
    <div className="flex h-full min-h-0 flex-col" onClick={() => menu && setMenu(null)}>
      {/* ── 工具列：上一層 · 麵包屑 · 新資料夾 · 搜尋 ───────────────── */}
      <div className="flex shrink-0 items-center gap-2 border-b px-3 py-2">
        {/* ⚠️ 手機沒有左欄 ⇒ 樹要有一個入口，否則整棵樹在手機上不存在 */}
        <button onClick={() => setTree(true)} title="領域樹"
                className="rounded px-2 py-1 text-sm hover:bg-muted md:hidden">📁</button>
        <button onClick={() => go(path.length > 1 ? path[path.length - 2].id : null)}
                disabled={sel === null} title="上一層"
                className="rounded px-2 py-1 text-sm hover:bg-muted disabled:opacity-30">⬆</button>
        {/* 窄螢幕只留「目前在哪」；寬螢幕才展開整條麵包屑 */}
        <span className="min-w-0 flex-1 truncate text-sm font-medium md:hidden">
          {path.length ? path[path.length - 1].name : `🗂 ${ROOT_NAME}`}
        </span>
        <div className="hidden min-w-0 flex-wrap items-center gap-0.5 text-sm md:flex">
          <button onClick={() => go(null)}
                  className={cn("rounded px-1.5 py-0.5 hover:bg-muted", sel === null && "font-semibold")}>
            🗂 {ROOT_NAME}
          </button>
          {path.map((seg) => (
            <span key={seg.id} className="flex items-center gap-0.5">
              <span className="text-muted-foreground/50">/</span>
              <button onClick={() => go(seg.id)}
                      className={cn("max-w-[10rem] truncate rounded px-1.5 py-0.5 hover:bg-muted",
                                    seg.id === sel && "font-semibold")}>{seg.name}</button>
            </span>
          ))}
        </div>
        <div className="ml-auto hidden items-center gap-2 md:flex">
          <Input value={name} onChange={(e) => setName(e.target.value)}
                 onKeyDown={(e) => { if (e.key === "Enter" && !e.nativeEvent.isComposing) create() }}
                 placeholder="新資料夾名稱…" className="h-8 w-40 text-sm" />
          <Button size="sm" variant="secondary" onClick={create}>＋ 新資料夾</Button>
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="在這個領域裡找…"
                 className="h-8 w-44 text-sm" />
        </div>
        {/* 手機：對齊 iOS Files／Drive 的「選取／完成」 */}
        <button onClick={() => (inBatch ? exitBatch() : setSelecting(true))}
                className="shrink-0 rounded px-2 py-1 text-sm text-primary md:hidden">
          {inBatch ? "完成" : "選取"}
        </button>
      </div>

      {/* 手機：搜尋與新資料夾另起一行，不擠在工具列 */}
      <div className="flex shrink-0 items-center gap-2 border-b px-3 py-1.5 md:hidden">
        <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="在這個領域裡找…"
               className="h-8 flex-1 text-sm" />
        <Input value={name} onChange={(e) => setName(e.target.value)}
               onKeyDown={(e) => { if (e.key === "Enter" && !e.nativeEvent.isComposing) create() }}
               placeholder="新資料夾…" className="h-8 w-28 text-sm" />
        <button onClick={create} className="shrink-0 rounded px-2 py-1 text-sm hover:bg-muted">＋</button>
      </div>

      {msg && <div className="shrink-0 bg-muted px-3 py-1.5 text-sm">{msg}</div>}

      {ask && (
        <div className="shrink-0 space-y-2 border-b border-amber-300 bg-amber-50/60 px-3 py-2 dark:bg-amber-950/30">
          <p className="text-sm">搬這 <b>{ask.items.length}</b> 件過去，會跟這 {ask.tangles.length} 個分開：</p>
          <ul className="ml-4 max-h-24 list-disc overflow-y-auto text-sm text-muted-foreground">
            {ask.tangles.map((t, n) => <li key={n}>{t.label}</li>)}
          </ul>
          <div className="flex flex-wrap items-center gap-2">
            <Button size="sm" onClick={() => doMove(ask.items, ask.to, true)}>連帶一起搬</Button>
            <Button size="sm" variant="secondary" onClick={() => doMove(ask.items, ask.to, false)}>留一條糾纏</Button>
            <button onClick={() => setAsk(null)} className="text-sm text-muted-foreground hover:underline">取消</button>
            <span className="text-xs text-muted-foreground">
              ⚠️「連帶」只走<b className="text-foreground">一層</b>——它們自己連著的東西不會跟著搬。
            </span>
          </div>
        </div>
      )}

      {/* ── 兩欄：左樹、右內容（都吃滿高度）───────────────────────── */}
      <div className="flex min-h-0 flex-1">
        <aside className="hidden w-64 shrink-0 overflow-y-auto border-r p-2 md:block">
          <div {...dropProps(null)}
               onClick={() => go(null)}
               className={cn("flex cursor-pointer items-center gap-2 rounded px-2 py-1 text-sm hover:bg-muted",
                             sel === null && "bg-muted font-medium",
                             dropOn === null && "outline outline-2 outline-primary")}>
            <span className="min-w-0 flex-1 truncate">🗂 {ROOT_NAME}</span>
            <span className="text-xs text-muted-foreground">{items.length}</span>
          </div>
          {kids(null).map((d) => renderNode(d, 1))}
        </aside>

        <section className="flex min-h-0 flex-1 flex-col">
          <div className="flex shrink-0 flex-wrap items-center gap-1 border-b px-3 py-1.5">
            {(["all", ...KIND_ORDER] as const).map((k) => (
              <button key={k} onClick={() => setFilter(k as KnowledgeKind | "all")}
                      className={cn("rounded px-2 py-0.5 text-xs",
                                    filter === k ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted")}>
                {k === "all" ? "全部" : KIND_LABEL[k as KnowledgeKind]}
              </button>
            ))}
            <Button size="sm" variant="secondary" className="ml-auto h-7"
                    onClick={() => nav(withDomain("/?new=" + Date.now(), sel))}>＋ 在這裡開新互動</Button>
          </div>

          {/* spec 070：⚠️ 這一塊**不折疊、不放頁尾**——它是這一頁存在的理由。
              清單（下面那個）是搜尋結果的形狀，搜尋做得比它好；
              「你沒在找的東西」才是搜尋給不了的。 */}
          <DomainContextPanel did={sel} onGo={(d) => go(d)} />

          {/* 欄位標題（可排序） */}
          <div className="grid shrink-0 grid-cols-[1.5rem_minmax(0,1fr)] md:grid-cols-[1.5rem_minmax(0,1fr)_5rem_7rem] items-center gap-2 border-b px-2 py-1">
            <span />
            <SortHead by="name">名稱</SortHead>
            <SortHead by="kind" cls="hidden md:block">種類</SortHead>
            <SortHead by="at" cls="hidden md:block">更新</SortHead>
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto p-1">
            {folders.length === 0 && rows.length === 0 && (
              <div className="p-6 text-center text-sm text-muted-foreground">
                {needle ? (
                  <p>找不到「{needle}」。<button onClick={() => setQ("")} className="underline hover:text-foreground">清除搜尋</button></p>
                ) : (
                  <div className="space-y-1">
                    <p>這個領域是空的。</p>
                    <p className="text-xs">
                      到<button onClick={() => go(null)} className="underline hover:text-foreground">🗂 {ROOT_NAME}</button>
                      把知識拖進來，或
                      <button onClick={() => nav(withDomain("/?new=" + Date.now(), sel))}
                              className="underline hover:text-foreground">在這裡開一段新互動</button>。
                    </p>
                  </div>
                )}
              </div>
            )}
            {folders.map(folderRow)}
            {rows.map(itemRow)}
          </div>

          {picked.size > 0 && (
            <div className="flex shrink-0 flex-wrap items-center gap-2 border-t px-3 py-2">
              <span className="text-sm">已選 <b>{picked.size}</b> 件</span>
              <button onClick={exitBatch} className="text-xs text-muted-foreground hover:underline">完成</button>
              <button onClick={() => setPicked(new Set(rows.map(keyOf)))}
                      className="text-xs text-muted-foreground hover:underline">全選這 {rows.length} 件</button>
              <button onClick={archivePicked}
                      className="text-xs text-muted-foreground hover:underline hover:text-destructive">📦 封存</button>
              <select value="" className="ml-auto h-8 rounded border bg-background px-2 text-sm"
                      onChange={(e) => { if (e.target.value !== "")
                        startMove(pickedRefs(), e.target.value === "0" ? null : Number(e.target.value)) }}>
                <option value="">搬到…</option>
                <option value="0">🗂 {ROOT_NAME}</option>
                {(domains || []).filter((d) => d.id !== sel).map((d) => (
                  <option key={d.id} value={d.id}>{d.path.map((x) => x.name).join(" / ")}</option>
                ))}
              </select>
            </div>
          )}
        </section>
      </div>

      {/* 手機：領域樹抽屜。⚠️ 沒有它，整棵樹在手機上不存在 */}
      {tree && (
        <div className="fixed inset-0 z-40 flex md:hidden">
          <div className="absolute inset-0 bg-black/30" onClick={() => setTree(false)} />
          <aside className="relative z-10 w-72 max-w-[80%] overflow-y-auto bg-background p-2 shadow-xl">
            <div className="flex items-center justify-between px-2 pb-2">
              <span className="text-sm font-semibold">📁 領域</span>
              <button onClick={() => setTree(false)} className="px-1 text-muted-foreground">✕</button>
            </div>
            <button onClick={() => { go(null); setTree(false) }}
                    className={cn("flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-sm hover:bg-muted",
                                  sel === null && "bg-muted font-medium")}>
              <span className="min-w-0 flex-1 truncate">🗂 {ROOT_NAME}</span>
              <span className="text-xs text-muted-foreground">{items.length}</span>
            </button>
            {(domains || []).filter((d) => d.parent_id === null).map((d) => renderMobileNode(d, 1))}
          </aside>
        </div>
      )}

      {/* 右鍵選單 */}
      {menu && (
        <div style={{ left: menu.x, top: menu.y }}
             className="fixed z-50 w-44 rounded-lg border bg-popover p-1 shadow-lg">
          {menu.kind === "domain" ? (
            <>
              <button onClick={() => { go(menu.d.id); setMenu(null) }} className="block w-full rounded px-2 py-1 text-left text-sm hover:bg-accent">開啟</button>
              <button onClick={() => { rename(menu.d); setMenu(null) }} className="block w-full rounded px-2 py-1 text-left text-sm hover:bg-accent">✏️ 改名</button>
              {menu.d.parent_id !== null && (
                <button onClick={() => { moveDomain(menu.d.id, null); setMenu(null) }} className="block w-full rounded px-2 py-1 text-left text-sm hover:bg-accent">⤴ 移到最上層</button>
              )}
              <button onClick={() => { archiveDomain(menu.d); setMenu(null) }} className="block w-full rounded px-2 py-1 text-left text-sm text-destructive hover:bg-accent">📦 封存</button>
            </>
          ) : (
            <>
              <button onClick={() => { open(menu.i); setMenu(null) }} className="block w-full rounded px-2 py-1 text-left text-sm hover:bg-accent">開啟</button>
              <button onClick={() => { toggle(menu.i); setSelecting(true); setMenu(null) }} className="block w-full rounded px-2 py-1 text-left text-sm hover:bg-accent">選取</button>
              {/* ⚠️ 手機沒有拖放（捲動會誤觸），所以「搬到…」必須在這裡，否則手機上搬不動東西 */}
              <div className="px-2 py-1">
                <select value="" aria-label="搬到" className="w-full rounded border bg-background px-1 py-0.5 text-sm"
                        onChange={(e) => {
                          if (e.target.value === "") return
                          const to = e.target.value === "0" ? null : Number(e.target.value)
                          const it = menu.i; setMenu(null)
                          startMove([{ kind: it.kind, ref: it.ref }], to)
                        }}>
                  <option value="">搬到…</option>
                  <option value="0">🗂 {ROOT_NAME}</option>
                  {(domains || []).filter((d) => d.id !== sel).map((d) => (
                    <option key={d.id} value={d.id}>{d.path.map((x) => x.name).join(" / ")}</option>
                  ))}
                </select>
              </div>
              <button onClick={async () => { setMenu(null); await pages.archiveKnowledge([{ kind: menu.i.kind, ref: menu.i.ref }]); setMsg("封存了 1 件"); load() }}
                      className="block w-full rounded px-2 py-1 text-left text-sm text-destructive hover:bg-accent">📦 封存</button>
            </>
          )}
        </div>
      )}

      <div className="shrink-0 border-t px-3 py-2">
      {/* 遺骸——封存過的東西。⚠️ 沒有這一格，「封存」在使用者眼裡就等於「刪除」 */}
      {((attic?.items.length ?? 0) + (attic?.domains.length ?? 0)) > 0 && (
        <section className="space-y-1 rounded-xl border border-dashed p-3">
          <button onClick={() => setShowAttic((v) => !v)}
                  className="flex w-full items-center gap-2 text-left text-sm font-semibold">
            <span>📦 已封存</span>
            <span className="text-xs font-normal text-muted-foreground">
              {attic!.domains.length} 個領域、{attic!.items.length} 件知識
            </span>
            <span className="ml-auto text-xs text-muted-foreground">{showAttic ? "▴" : "▾"}</span>
          </button>
          {showAttic && (
            <div className="space-y-0.5 pt-1">
              <p className="pb-1 text-xs text-muted-foreground">
                離開了活的知識庫，但沒有消失——也不再進入聊天與檢索。
                <br />
                <b>抹除</b>是第二次的死：內容直接消失、救不回來，只留下一塊疤。
              </p>
              {attic!.domains.map((d) => (
                <div key={`d${d.id}`} className="flex items-center gap-2 rounded px-2 py-1 text-sm hover:bg-muted">
                  <span className="min-w-0 flex-1 truncate">📁 {d.name}</span>
                  <span className="shrink-0 text-xs text-muted-foreground">{d.archived_at.slice(0, 10)}</span>
                  <button onClick={async () => { await pages.restoreDomain(d.id); setMsg(`復原了「${d.name}」`); load() }}
                          className="shrink-0 text-xs text-muted-foreground hover:underline hover:text-foreground">復原</button>
                  <button title="第二次的死——救不回來（底下已封存的知識不會被連帶抹除）"
                          onClick={async () => {
                            if (!confirm(`抹除領域「${d.name}」？\n\n這是第二次的死，救不回來。\n` +
                                         `⚠️ 它底下「已封存的知識」不會被一起抹掉——那些仍可單獨復原。`)) return
                            const r = await pages.eraseDomain(d.id)
                            setMsg(r.ok ? `抹除了「${d.name}」` : (r.err || "抹不掉")); load()
                          }}
                          className="shrink-0 text-xs text-muted-foreground hover:underline hover:text-destructive">抹除</button>
                </div>
              ))}
              {attic!.items.map((i) => (
                <div key={keyOf(i)} className="flex items-center gap-2 rounded px-2 py-1 text-sm hover:bg-muted">
                  <span className="shrink-0 text-xs text-muted-foreground">{KIND_LABEL[i.kind].slice(0, 2)}</span>
                  <span className="min-w-0 flex-1 truncate">{i.label}</span>
                  <span className="shrink-0 text-xs text-muted-foreground">{i.archived_at.slice(0, 10)}</span>
                  <button onClick={async () => { await pages.restoreKnowledge([{ kind: i.kind, ref: i.ref }]); setMsg("復原了"); load() }}
                          className="shrink-0 text-xs text-muted-foreground hover:underline hover:text-foreground">復原</button>
                  <button title="第二次的死——救不回來"
                          onClick={() => erase([{ kind: i.kind, ref: i.ref }], `「${i.label.slice(0, 20)}」`)}
                          className="shrink-0 text-xs text-muted-foreground hover:underline hover:text-destructive">抹除</button>
                </div>
              ))}
            </div>
          )}
        </section>
      )}

        {sel === null && unfiled.length > 0 && (
          <div className="mt-2 space-y-2">
            <p className="text-xs text-muted-foreground">
              既有的知識都在根領域——⚠️ <b className="text-foreground">刻意不自動分類</b>：猜出來的歸屬會看起來跟真的一樣。
            </p>
            {/* spec 065：所以這裡給的是**建議**，不是分類。逐夾接受，沒有「全部套用」。 */}
            <SuggestOrganize onApplied={load} />
          </div>
        )}
      </div>
    </div>
  )
}
