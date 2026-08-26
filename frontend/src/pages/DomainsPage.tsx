import { useEffect, useMemo, useState } from "react"
import { useNavigate } from "react-router-dom"
import { pages, type KnowledgeItem, type KnowledgeKind, type KnowledgeRef } from "@/lib/api"
import { keyOf, pickedRefs as pickRefs, inDomain as inDom, KIND_ORDER } from "@/lib/knowledge"
import { useCurrentDomain } from "@/lib/domain"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"

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
  source: "📚 來源", conversation: "💬 對話", why_node: "💡 理解", article: "🧩 應用",
}

export default function DomainsPage() {
  const nav = useNavigate()
  const [domains, setDomains] = useState<Domain[] | null>(null)
  const [items, setItems] = useState<KnowledgeItem[]>([])
  // ⚠️ 從側欄點「領域」進來時，**接上你站的地方**——不然管理頁每次都從根開始，
  //    你得再找一次自己剛剛在哪。
  const { did, go } = useCurrentDomain()
  const [sel, setSel] = useState<number | null>(did)
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
    if (sel === d.id) setSel(p.to)
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

  const kids = (p: number | null) => (domains || []).filter((d) => d.parent_id === p)
  const inDomain = (id: number | null) => inDom(items, id)
  const unfiled = useMemo(() => inDomain(null), [items])

  const pickedRefs = (): KnowledgeRef[] => pickRefs(items, picked)

  function toggle(i: KnowledgeItem) {
    const k = keyOf(i)
    setPicked((p) => { const n = new Set(p); n.has(k) ? n.delete(k) : n.add(k); return n })
  }

  // ── 拖放（Pointer Events，不是 HTML5 DnD）────────────────────────────
  // ⚠️ **HTML5 drag-and-drop 在觸控裝置上根本不會觸發**，而這是個 PWA
  //    ——用 draggable/onDrop 的話手機上會安靜地不能拖，什麼錯都不報。
  //    Pointer Events 滑鼠與觸控同一條路，而且合成事件驅得動 ⇒ 驗得到。
  // 拖的是**目前選取的那批**；拖一個沒被選取的，就當成只拖它自己。
  function beginDrag(e: React.PointerEvent, i: KnowledgeItem) {
    if (e.button !== 0 && e.pointerType === "mouse") return
    const key = keyOf(i)
    const batch = picked.has(key) ? picked : new Set([key])
    if (batch !== picked) setPicked(batch)
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
      armed = true                       // 門檻：小於 6px 當成點擊，不當拖曳
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
  const renderRow = (i: KnowledgeItem) => (
    <label key={keyOf(i)} onPointerDown={(e) => beginDrag(e, i)}
           className="flex cursor-grab select-none items-center gap-2 rounded px-2 py-1 text-sm hover:bg-muted">
      <input type="checkbox" checked={picked.has(keyOf(i))} onChange={() => toggle(i)} />
      <span className="shrink-0 text-xs text-muted-foreground">{KIND_LABEL[i.kind].slice(0, 2)}</span>
      <span className="min-w-0 flex-1 truncate">{i.label}</span>
      {i.kind === "conversation" && (
        <button onClick={(e) => { e.preventDefault(); nav(`/?resume=${i.ref}`) }}
                className="shrink-0 text-xs text-muted-foreground hover:underline">開啟</button>
      )}
    </label>
  )

  const renderNode = (d: Domain, depth: number) => (
    <div key={d.id}>
      <div className={cn("group flex items-center gap-2 rounded px-2 py-1 hover:bg-muted",
                         sel === d.id && "bg-muted",
                         dropOn === d.id && "outline outline-2 outline-primary")}
           style={{ paddingLeft: 8 + depth * 16 }} {...dropProps(d.id)}>
        <button onClick={() => setSel(sel === d.id ? null : d.id)} className="min-w-0 flex-1 truncate text-left text-sm">
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
  const shown = (list: KnowledgeItem[]) => list
    .filter((i) => filter === "all" || i.kind === filter)
    .filter((i) => !needle || i.label.toLowerCase().includes(needle))
  const byKind = (list: KnowledgeItem[], k: KnowledgeKind) => list.filter((i) => i.kind === k)

  return (
    <div className="space-y-5 pb-8">
      <div>
        <h1 className="text-2xl font-bold">🗂 領域</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          管理知識庫的樹——新增、改名、搬動、封存；勾選右邊的知識，拖到左邊的領域上放開。
          <br />
          ⚠️ <b>封存不是刪除</b>：它連同底下的知識一起離開活的知識庫，<b>不會消失</b>，之後可以一起復原。
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Input value={name} onChange={(e) => setName(e.target.value)}
               onKeyDown={(e) => { if (e.key === "Enter" && !e.nativeEvent.isComposing) create() }}
               placeholder={sel ? "在選取的領域底下新增子領域…" : `在${ROOT_NAME}底下新增領域…`}
               className="w-64 max-w-full" />
        <Button size="sm" onClick={create}>＋ 新增</Button>
        {sel && <button onClick={() => setSel(null)} className="text-xs text-muted-foreground hover:underline">回根領域</button>}
      </div>

      {msg && <div className="rounded-md bg-muted px-3 py-2 text-sm">{msg}</div>}

      {ask && (
        <div className="space-y-3 rounded-xl border border-amber-300 bg-amber-50/40 p-4 dark:bg-amber-950/20">
          <p className="text-sm">
            搬這 <b>{ask.items.length}</b> 件過去，會跟這 {ask.tangles.length} 個分開：
          </p>
          <ul className="ml-4 max-h-40 list-disc overflow-y-auto text-sm text-muted-foreground">
            {ask.tangles.map((t, i) => <li key={i}>{t.label}</li>)}
          </ul>
          <div className="flex flex-wrap gap-2">
            <Button size="sm" onClick={() => doMove(ask.items, ask.to, true)}>連帶一起搬</Button>
            <Button size="sm" variant="secondary" onClick={() => doMove(ask.items, ask.to, false)}>
              留一條糾纏
            </Button>
            <button onClick={() => setAsk(null)} className="text-sm text-muted-foreground hover:underline">
              取消
            </button>
          </div>
          <p className="text-xs text-muted-foreground">
            ⚠️ 「連帶」只走<b className="text-foreground">一層</b>——它們自己連著的東西不會跟著搬（知識的連結是網不是樹）。
          </p>
        </div>
      )}

      <div className="grid items-start gap-4 md:grid-cols-[minmax(0,280px)_minmax(0,1fr)]">
        {/* ── 左：領域樹（每個節點都是放置目標）──────────────────── */}
        {/* 置頂不捲走：清冊有上百列，樹捲掉了就沒地方可以放。 */}
        <div className="space-y-2 md:sticky md:top-4">
          {domains === null ? (
            <p className="text-sm text-muted-foreground">載入中…</p>
          ) : (
            <div className="rounded-xl border bg-card p-2">
              {/* ⚠️ 根領域是樹的**頂**，不是樹外面的桶子 */}
              <div className={cn("flex items-center gap-2 rounded px-2 py-1 hover:bg-muted",
                                 sel === null && "bg-muted",
                                 dropOn === null && "outline outline-2 outline-primary")}
                   style={{ paddingLeft: 8 }} {...dropProps(null)}>
                <button onClick={() => setSel(null)} className="text-left text-sm font-medium">
                  🗂 {ROOT_NAME}
                </button>
                <span className="text-xs text-muted-foreground">{inDomain(null).length}</span>
              </div>
              {kids(null).map((d) => renderNode(d, 1))}
            </div>
          )}
          {domains !== null && domains.length === 0 && (
            <p className="text-xs text-muted-foreground">
              還沒有子領域。上面打一個名字就能在根領域底下建第一個。
            </p>
          )}
        </div>

        {/* ── 右：待整理清冊 ──────────────────────────────────── */}
        <div className="space-y-2 rounded-xl border bg-card p-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-semibold">
              {selected ? [ROOT_NAME, ...selected.path.map((p) => p.name)].join(" / ") : ROOT_NAME}
            </span>
            <div className="ml-auto flex flex-wrap items-center gap-1">
              {(["all", ...KIND_ORDER] as const).map((k) => (
                <button key={k} onClick={() => setFilter(k as KnowledgeKind | "all")}
                        className={cn("rounded px-2 py-0.5 text-xs",
                                      filter === k ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted")}>
                  {k === "all" ? "全部" : KIND_LABEL[k as KnowledgeKind]}
                </button>
              ))}
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2 border-b pb-2">
            <Button size="sm" variant="secondary"
                    onClick={() => nav(selected ? `/?new=1&domain=${selected.id}` : "/?new=1")}>
              ＋ 在這裡開新對話
            </Button>
            <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="在這個領域裡找…"
                   className="h-8 w-44 max-w-full text-sm" />
            {/* 搜尋縮到一批之後，逐件勾就是「互動次數＝可行性」那條判準在打自己 */}
            {shown(inDomain(sel)).length > 0 && (
              <button onClick={() => setPicked(new Set(shown(inDomain(sel)).map(keyOf)))}
                      className="text-xs text-muted-foreground hover:underline">
                全選這 {shown(inDomain(sel)).length} 件
              </button>
            )}
            {kids(sel).length > 0 && (
              <span className="text-xs text-muted-foreground">
                子領域：{kids(sel).map((k) => k.name).join("、")}
              </span>
            )}
          </div>

          {(() => {
            const list = shown(inDomain(sel))
            if (list.length === 0) {
              return <p className="py-4 text-sm text-muted-foreground">
                {needle ? "找不到符合的。" : "這個領域底下還沒有這類知識。"}
              </p>
            }
            // 每個領域都有自己的「子領域、來源、對話、理解、文章」——分段列
            return KIND_ORDER.filter((k) => byKind(list, k).length > 0).map((k) => (
              <section key={k} className="space-y-0.5">
                <h3 className="px-2 pt-2 text-xs font-semibold text-muted-foreground">
                  {KIND_LABEL[k]}（{byKind(list, k).length}）
                </h3>
                {byKind(list, k).map(renderRow)}
              </section>
            ))
          })()}

          {picked.size > 0 && (
            <div className="sticky bottom-0 flex flex-wrap items-center gap-2 border-t bg-card pt-2">
              <span className="text-sm">已選 <b>{picked.size}</b> 件</span>
              <button onClick={() => setPicked(new Set())}
                      className="text-xs text-muted-foreground hover:underline">清除</button>
              <button onClick={archivePicked}
                      className="text-xs text-muted-foreground hover:underline hover:text-destructive">📦 封存</button>
              <select value="" className="ml-auto rounded border bg-background px-2 py-1 text-sm"
                      onChange={(e) => { if (e.target.value !== "")
                        startMove(pickedRefs(), e.target.value === "0" ? null : Number(e.target.value)) }}>
                <option value="">搬到…</option>
                <option value="0">🗂 {ROOT_NAME}</option>
                {(domains || []).filter((d) => d.id !== sel).map((d) => (
                  <option key={d.id} value={d.id}>{d.path.map((p) => p.name).join(" / ")}</option>
                ))}
              </select>
            </div>
          )}
        </div>
      </div>

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
                                         `⚠️ 它底下**已封存的知識不會**被一起抹掉——那些仍可單獨復原。`)) return
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
        <p className="text-xs text-muted-foreground">
          既有的知識都在根領域——⚠️ <b className="text-foreground">刻意不自動分類</b>：猜出來的歸屬會看起來跟真的一樣。
        </p>
      )}
    </div>
  )
}
