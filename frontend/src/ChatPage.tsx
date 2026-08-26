import { useEffect, useRef, useState } from "react"
import { useNavigate, useSearchParams } from "react-router-dom"
import { api, pages, streamChat, type Candidate, type Message } from "@/lib/api"
import { Markdown } from "@/components/Markdown"
import { Sources, FoundExtra } from "@/components/Sources"
import { KINDS } from "@/components/KindBadge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { cn } from "@/lib/utils"
import { useCurrentDomain } from "@/lib/domain"
import { coveredSet, coverageSummary, type Range } from "@/lib/coverage"
import { Copy, GitBranch, Pencil, RefreshCw } from "lucide-react"
import { Rehearse } from "@/components/Rehearse"

type Chapter = { title: string; start: number; end: number }

// 通知側欄（Layout 內）重載對話歷史
const notifyConversations = () => window.dispatchEvent(new Event("kf-conversations-changed"))
// spec 047：檢視頁退場後，側欄的「目前這段」高亮沒有 URL 可依（`?resume=` 會被清掉）。
// ⚠️ 它原本**只在檢視頁亮得起來**——走聊天頁那條路一直是暗的。沿用既有事件匯流排廣播，
// 順手把它修對，而不是跟著頁面一起刪掉。
const notifyActiveConv = (id: number | null) =>
  window.dispatchEvent(new CustomEvent("kf-active-conv", { detail: id }))

// 帶入物：文章（AI 依理解生成的衍生物）或來源（使用者收進的一手素材）。
// 兩者在**畫面上同形**，但在**脈絡裡分層**——分層在後端 field_chat._messages 做。
type Carried =
  | { kind: "article"; id: number; title: string }
  | { kind: "source"; url: string; title: string }

export default function ChatPage() {
  const nav = useNavigate()
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState("")
  const [bare, setBare] = useState(false)   // 這輪暫時屏蔽知識庫：不參考理解、不撒網、不查收藏
  // 使用者**明確**帶進來的東西：一篇生成文章（spec 041）或一份收進的來源（spec 042）。
  // ⚠️ **共用同一條呈現路徑**——那是「形狀差異＝0 處」最強的保證：
  // 只有一個 render 分支，就不可能長出兩套形狀（spec 042 SC-006）。
  const [carried, setCarried] = useState<Carried | null>(null)
  // 帶進脈絡卻看不到，等於只有 AI 讀得到它——就地展開（041 FR-001a）
  const [carriedOpen, setCarriedOpen] = useState(true)   // 它是「第一則」，預設就看得到
  const [carriedBody, setCarriedBody] = useState<string | null>(null)
  // spec 048：這段對話要開在哪個領域。⚠️ 只在**建立那筆**時寫（同 044 的由來），
  // 之後 autosave 送什麼都不會改到它。
  const pendingDomain = useRef<number | null>(null)
  const { did } = useCurrentDomain()      // 你站的地方（spec 052）
  // 「⋯ 更多」改成受控選單：`<details>` 點空白處收不起來（使用者回報 2026-08-26）
  const [more, setMore] = useState(false)
  const moreRef = useRef<HTMLDivElement>(null)
  const [allDomains, setAllDomains] = useState<{ id: number; name: string; path: { id: number; name: string }[] }[]>([])
  useEffect(() => {
    if (!more) return
    pages.domains().then((r) => setAllDomains(r.domains)).catch(() => {})
    const close = (e: Event) => { if (!moreRef.current?.contains(e.target as Node)) setMore(false) }
    // ⚠️ 兩種輸入都要接：只掛 mousedown 的話手機上關不掉（同一族的第四次）
    document.addEventListener("mousedown", close)
    document.addEventListener("touchstart", close)
    return () => {
      document.removeEventListener("mousedown", close)
      document.removeEventListener("touchstart", close)
    }
  }, [more])

  async function moveThisConv(v: string) {
    const cid = tempId.current
    if (!cid) return
    setMore(false)
    const to = v === "0" ? null : Number(v)
    const t = await pages.tangles([{ kind: "conversation", ref: cid }], to)
    if (t.tangles.length && !confirm(
      `搬過去會跟這 ${t.tangles.length} 個分開：\n\n` +
      t.tangles.slice(0, 6).map((x) => "・" + x.label).join("\n") +
      "\n\n仍要搬？（它們會留在原地，成為一條糾纏）")) return
    await pages.moveKnowledge([{ kind: "conversation", ref: cid }], to, false)
    notifyConversations()
    toast("搬好了")
  }

  async function archiveThisConv() {
    const cid = tempId.current
    if (!cid) return
    setMore(false)
    if (!confirm("封存這段互動？\n\n它會離開活的知識庫，但不會消失——可以在「領域」頁復原。")) return
    const r = await pages.deleteConv(cid)
    if (!r.deleted && r.blocked_by?.length) {
      alert("這段互動是下列理解的『由來』，封存不了。\n請先封存它們：\n\n"
        + r.blocked_by.map((x) => "• " + x).join("\n"))
      return
    }
    notifyConversations()
    newChat()
    toast("已封存")
  }

  const [stage, setStage] = useState<string | null>(null)
  const [streaming, setStreaming] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [rootCount, setRootCount] = useState(0)
  const [candidates, setCandidates] = useState<Candidate[] | null>(null)
  // spec 046：候選在冊封前可以改（主張＋層次）。空＝沿用 AI 提的原樣。
  const [edits, setEdits] = useState<Record<number, { claim?: string; kind?: string }>>({})
  const [candDone, setCandDone] = useState<Record<number, string>>({})
  const [saveConvo, setSaveConvo] = useState(false)
  const [convTitle, setConvTitle] = useState("")   // 本對話落點標題（抬頭顯示）
  const tempId = useRef<number | null>(null)
  const referrers = useRef<string[]>([])   // 以本對話為由來的理解主張（編輯/重生時擋，護溯源）
  const [chapters, setChapters] = useState<Chapter[] | null>(null)   // resume 舊訊息的章節（折疊）
  const baseCount = useRef(0)                                         // resume 載入的訊息數（章節涵蓋到此）
  const [focusFrom, setFocusFrom] = useState(0)                      // 理解定位進來的出處起點則
  // spec 046：這段對話已冊封的範圍。⚠️ 用**集合**逐則判斷，不用水位線——
  // 實測覆蓋不連續（對話 44 收到第 44 則卻缺 3–8），水位線會把中間的洞藏起來。
  const [anointed, setAnointed] = useState<{ id: number; claim: string; from: number; to: number }[]>([])
  const [nudgeDismissed, setNudgeDismissed] = useState(false)        // 分章提醒關掉了
  const chapterRefs = useRef<(HTMLDetailsElement | null)[]>([])   // 各章 <details>，供大綱跳章＋預設展開
  const bottomRef = useRef<HTMLDivElement>(null)
  const [sp, setSp] = useSearchParams()

  useEffect(() => {
    api.state().then((s) => setRootCount(s.root_count)).catch(() => {})
  }, [])

  async function loadConversation(id: number, from = 0) {
    const c = await pages.conversation(id, true)
    if (!c.found) return
    setCarried(null); setCarriedBody(null)   // 接回舊對話 → 文章不殘留（FR-001c：不在對話間常駐）
    setMessages(c.messages)
    setConvTitle(c.title || "")
    baseCount.current = c.messages.length
    setFocusFrom(from); setNudgeDismissed(false)
    tempId.current = c.id; notifyActiveConv(c.id)   // 接回就綁定這筆：繼續聊就地更新同一筆，不另開（spec 040 起無分層）
    referrers.current = c.referrers || []   // 這段是不是某理解的由來（編輯/重生要擋）
    setAnointed(c.anointed || [])
    setCandidates(null); setStreaming(null); setStage(null)
    // 載章節（持久化）：多章才折疊
    pages.segment(id).then((r) =>
      setChapters(r.found && r.chapters.length > 1 ? r.chapters : null)).catch(() => setChapters(null))
  }
  function newChat() {
    notifyActiveConv(null)
    pendingDomain.current = null
    setCarried(null); setCarriedOpen(true); setCarriedBody(null); setAnointed([])   // 文章不跨對話殘留（FR-001c）
    setMessages([]); tempId.current = null; referrers.current = []; setChapters(null); baseCount.current = 0; setFocusFrom(0)
    setConvTitle(""); setNudgeDismissed(false)
    setCandidates(null); setCandDone({}); setStreaming(null); setStage(null); setInput("")
  }

  // 側欄用 URL 溝通：?new=… 開新對話、?resume=id 接回（?from&to＝理解定位）
  useEffect(() => {
    // spec 041：/?article=<id>&atitle=<標題> → **開一段新對話給這篇文章**（人明確按的，非自動）。
    // ⚠️ 不是把文章掛到當前那段對話上——文章不該在對話間常駐（FR-001c，使用者裁決 2026-08-21）：
    // 一篇文章激發的想法自成一條線，混進既有對話會讓兩條線互相污染，也讓那段對話的由來變得不純。
    const aid = Number(sp.get("article") || 0)
    if (aid) {
      newChat()                       // 先清空，這是新的一段
      setCarried({ kind: "article", id: aid, title: sp.get("atitle") || "應用" })
      setCarriedOpen(true); setCarriedBody(null)
      pages.getArticle(aid).then((a) => setCarriedBody(a?.markdown || "")).catch(() => setCarriedBody(""))
      sp.delete("article"); sp.delete("atitle"); setSp(sp, { replace: true })
      return                          // 不再往下走 resume（那會把舊對話載回來）
    }
    // spec 042：/?source=<url>&stitle=<標題> → 開一段新對話給這份來源。規則與文章逐項相同。
    const surl = (sp.get("source") || "").trim()
    if (surl) {
      newChat()
      setCarried({ kind: "source", url: surl, title: sp.get("stitle") || "來源" })
      setCarriedOpen(true); setCarriedBody(null)
      // ⚠️ 畫面顯示的是**顯示路徑**的結果（可能已繁體化），而送進模型脈絡的是**儲存層原文**
      //（spec 042 FR-004）。這是刻意的不一致：人要讀得順，模型要看得到原文才抓得出翻譯失真。
      pages.source(surl).then((r) => setCarriedBody(r?.markdown || "")).catch(() => setCarriedBody(""))
      sp.delete("source"); sp.delete("stitle"); setSp(sp, { replace: true })
      return
    }
    if (sp.get("new")) {
      newChat()
      // spec 052：當前領域住在 `?d`。舊的 `?domain=` 仍認（舊連結／書籤不打斷）。
      // ⚠️ **不要 delete("d")**——那是你站的地方，換頁不該把你掉出去。
      const d = Number(sp.get("d") || sp.get("domain") || 0)
      pendingDomain.current = d || null
      sp.delete("new"); sp.delete("domain"); setSp(sp, { replace: true })
      return
    }
    const rid = Number(sp.get("resume") || 0)
    if (rid) {
      const from = Number(sp.get("from") || 0)
      loadConversation(rid, from).finally(() => {
        sp.delete("resume"); sp.delete("from"); sp.delete("to"); setSp(sp, { replace: true })
      })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sp, setSp])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, streaming, stage])

  // 預設展開「該開的章」（出處章 or 最後章）；定位進來時還捲到它
  useEffect(() => {
    const d = chapterRefs.current[openIdx]
    if (d) {
      d.open = true
      if (focusFrom) d.scrollIntoView({ behavior: "smooth", block: "start" })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chapters, focusFrom])

  // 大綱點章：展開那章＋捲到它
  function jumpToChapter(ci: number) {
    const d = chapterRefs.current[ci]
    if (d) { d.open = true; d.scrollIntoView({ behavior: "smooth", block: "start" }) }
  }

  // 串流一輪：hist＝這句 user 之前的歷史；msg＝這句 user。送出/編輯重問/重新生成共用。
  async function runStream(hist: Message[], msg: string) {
    setBusy(true)
    setStage("思考中…")
    setStreaming("")
    setMessages([...hist, { role: "user", content: msg }])   // 樂觀顯示：送出當下就看到自己那句
    let full = ""
    await streamChat(hist, msg, bare, {
      onStage: (t) => setStage(t),
      onToken: (t) => { full += t; setStage(null); setStreaming(full) },
      onError: (t) => {
        setStreaming(null); setStage(null)
        setMessages([...hist, { role: "user", content: msg },
          { role: "assistant", content: "⚠ " + t }])
      },
      onDone: (text, sources, extra, truncated) => {
        const next: Message[] = [...hist, { role: "user", content: msg },
          { role: "assistant", content: text || full, sources, found_extra: extra, truncated }]
        setMessages(next); setStreaming(null); setStage(null)
        // spec 044：把由來一起送（只有建立那筆時後端才會寫；之後送了也不會改到）
        api.autosave(next, tempId.current, carried
          ? { kind: carried.kind, ref: carried.kind === "article" ? String(carried.id) : carried.url }
          : undefined, pendingDomain.current).then((r) => {
          tempId.current = r.temp_id
          if (r.title) setConvTitle(r.title)
          notifyConversations()
        }).catch(() => {})
      },
    }, carried?.kind === "article" ? carried.id : 0,
       carried?.kind === "source" ? carried.url : "")
    setBusy(false)
  }
  // spec 043：帶著這段對話去生成頁。⚠️ **不在這裡判斷有沒有冊封過**——
  // 那個判斷在後端（`conversation_referrers`），而後端會回一句可行動的話（FR-006）。
  // 前端自己猜會多一份會過期的真相。
  function genArticleFromConv() {
    const cid = tempId.current
    if (!cid) { toast("先聊幾句（這段還沒被存下來）"); return }
    nav(`/roots?conv=${cid}&ctitle=${encodeURIComponent(convTitle || "這段互動")}`)
  }

  async function send() {
    const msg = input.trim()
    if (!msg || busy) return
    setInput("")
    await runStream(messages, msg)
  }

  // 編輯/重生的護欄：由來→擋（先處理理解，護溯源）；會丟後面訊息→確認可取消。
  function guardMutate(discardCount: number): boolean {
    if (referrers.current.length > 0) {
      alert("這段互動是下列理解的『由來』，編輯/重新生成會改動它、斷開溯源。\n"
        + "請先到「💡 理解」把它們退回/處理，再改這段：\n\n"
        + referrers.current.map((s) => "• " + s).join("\n"))
      return false
    }
    if (discardCount > 0 && !confirm(`重新生成會丟掉後面 ${discardCount} 則訊息，確定？`)) return false
    return true
  }

  // 重新生成最後一則回覆（用最後一句 user 重跑）
  async function regenerateLast() {
    if (busy) return
    let j = messages.length - 1
    while (j >= 0 && messages[j].role !== "user") j--
    if (j < 0) return
    if (!guardMutate(messages.length - (j + 1))) return
    await runStream(messages.slice(0, j), messages[j].content)
  }

  async function distill() {
    if (!messages.length || busy) return
    setBusy(true)
    const r = await api.distill(messages)
    setBusy(false)
    if (r.error) return
    setCandidates(r.candidates || [])
    setCandDone({})
  }

  const setEdit = (i: number, patch: { claim?: string; kind?: string }) =>
    setEdits((e) => ({ ...e, [i]: { ...e[i], ...patch } }))

  async function anointOne(i: number, c: Candidate) {
    // ⚠️ 送**改過的**值——不是 c.claim。這條是 spec 046 的整個重點。
    const r = await api.anoint({
      claim: (edits[i]?.claim ?? c.claim).trim(), kind: edits[i]?.kind ?? c.kind, ladder: c.ladder.join("\n"),
      evidence_urls: c.evidence_urls.join(", "),
      save_convo: saveConvo, history: messages, temp_id: tempId.current,
      src_from: c.src_from, src_to: c.src_to,
      // ⚠️ 沒有對話由來時，這條理解落在**你站的地方**（spec 052 FR-006）。
      // 有由來的話後端會用出處——出處勝過站的地方。
      domain_id: pendingDomain.current ?? did,
    })
    setCandDone((d) => ({ ...d, [i]: r.status === "exists" ? "➖ 已收過（沒重複收）" : "✅ 已精選" }))
    if (r.status === "created") setRootCount((n) => n + 1)
    if (saveConvo) notifyConversations()   // 連同存對話→歷史更新
  }

  const [flash, setFlash] = useState<string | null>(null)
  function toast(t: string) { setFlash(t); setTimeout(() => setFlash(null), 2200) }

  async function copyChat(as: "md" | "urls") {
    const r = await fetch("/api/chat/export", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ history: messages, as }),
    })
    const text = await r.text()
    if (!text.trim()) { toast(as === "urls" ? "這段沒有被引用的來源網址" : "這段互動還是空的"); return }
    try { await navigator.clipboard.writeText(text); toast("已複製，可貼進 NotebookLM") }
    catch { toast("這個瀏覽器不允許自動複製") }
  }
  function editMessage(i: number) {
    if (!guardMutate(messages.length - (i + 1))) return   // 由來→擋；丟後面訊息→確認
    setInput(messages[i]?.content || "")
    setMessages(messages.slice(0, i))   // 從這句重問（這串會改）；改好按送出即重生
  }
  // 從某章末開分支：載入前綴當新對話（原對話不動），接著聊會自動存成新的一筆
  function branchFrom(upToMsg: number) {
    setMessages(messages.slice(0, upToMsg))
    tempId.current = null; baseCount.current = 0
    setChapters(null); setFocusFrom(0); setConvTitle("")
    setCandidates(null); setStreaming(null); setStage(null)
    toast("已從這裡開分支——接著聊會存成新互動，原互動不動")
  }
  async function copyMsg(text: string) {
    try { await navigator.clipboard.writeText(text); toast("已複製這則") }
    catch { toast("這個瀏覽器不允許自動複製") }
  }
  // spec 047：原本只在檢視頁的「重生標題」。搬過來，否則刪頁面＝弄丟能力。
  async function retitleConv() {
    const cid = tempId.current
    if (!cid) return
    const r = await pages.retitleConv(cid)
    if (r.title) { setConvTitle(r.title); notifyConversations() }
  }

  // 整理成章節（把續聊的新訊息也切進章節）——分章提醒觸發
  async function reslice() {
    if (!tempId.current) { toast("先聊一句讓它存下、才能整理章節"); return }
    setBusy(true)
    const r = await pages.segment(tempId.current, true)
    setBusy(false)
    setNudgeDismissed(true)
    if (r.found && r.chapters.length > 1) {
      setChapters(r.chapters); baseCount.current = messages.length; setFocusFrom(0)
      toast(`整理成 ${r.chapters.length} 章了`)
    }
  }

  const empty = messages.length === 0 && streaming === null && stage === null

  const freshCands = (candidates || []).filter((c) => !c.already)

  // spec 046：哪幾則已冊封。⚠️ 集合，不是水位線（見 lib/coverage.ts 的理由）。
  const covered = coveredSet(anointed as Range[], messages.length)
  const cov = coverageSummary(anointed as Range[], messages.length)
  // 沒有範圍的舊冊封（正式庫 34/75）：只能算在對話層級，**不猜是哪幾則**（猜就是造假資料）。
  const rangelessCount = anointed.filter((a) => !a.from || !a.to).length

  const renderMsg = (m: Message, i: number) =>
    m.role === "user" ? (
      <div key={i} className="group flex flex-col items-end gap-0.5">
        <div className={cn("max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-sm bg-muted px-4 py-2",
                           covered.has(i + 1) && "border-l-2 border-primary/40")}>{m.content}</div>
        <button onClick={() => editMessage(i)} title="編輯這句重問（改這串）"
                className="pr-1 text-muted-foreground opacity-100 hover:text-foreground md:opacity-0 md:transition md:group-hover:opacity-100">
          <Pencil className="size-3.5" />
        </button>
      </div>
    ) : (
      // SOTA：AI 回覆＝全寬無框文字流（不裝卡片），文字區最大化；用留白＋對齊區分你我，不用框
      <div key={i} className={cn("group", covered.has(i + 1) && "border-l-2 border-primary/40 pl-3")}>
        <Markdown text={m.content} prefix={`m${i}`} />
        {/* 不完整就明說是哪一種——靜默半句看起來像講完了，兩種斷法也得分得出來（憲章 V） */}
        {m.truncated && (
          <div className="mt-2 text-xs text-amber-600 dark:text-amber-500">
            {m.truncated === "length"
              ? "⚠ 這則回答到長度上限被截斷了（沒講完）。可以請它「接著上面繼續」。"
              : "⚠ 這則回答中途斷線，只收到一半。可以重新生成。"}
          </div>
        )}
        <Sources sources={m.sources || []} prefix={`m${i}`} />
        <FoundExtra extra={m.found_extra || []} />
        {/* 回覆下方操作列（一般 AI 聊天慣例）：複製、重生、分支 */}
        <div className="mt-2 flex gap-4 text-muted-foreground opacity-100 md:opacity-0 md:transition md:group-hover:opacity-100">
          <button onClick={() => copyMsg(m.content)} title="複製這則回覆" className="hover:text-foreground"><Copy className="size-3.5" /></button>
          {i === messages.length - 1 && !busy && (
            <button onClick={regenerateLast} title="重新生成這則回覆" className="hover:text-foreground"><RefreshCw className="size-3.5" /></button>
          )}
          <button onClick={() => branchFrom(i + 1)} title="從這裡開分支（原互動不動、另開一串接著聊）" className="hover:text-primary"><GitBranch className="size-3.5" /></button>
        </div>
      </div>
    )
  const hasChapters = !!(chapters && chapters.length > 1)
  // 該預設展開的章 index：定位進來→出處章；否則→最後章
  let openIdx = -1
  if (hasChapters && chapters) {
    openIdx = focusFrom > 0
      ? chapters.findIndex((ch) => ch.start <= focusFrom && ch.end >= focusFrom)
      : chapters.length - 1
    if (openIdx < 0) openIdx = chapters.length - 1
  }
  const lastEnd = hasChapters && chapters ? chapters[chapters.length - 1].end : 0
  const uncharted = messages.length - lastEnd   // 還沒切進章節的訊息數（續聊累積）
  const showNudge = uncharted >= 8 && !nudgeDismissed && !busy && streaming === null

  return (
    <div className="relative flex h-full px-4 py-3">
      {/* 章節大綱：釘在主內容區最左邊（靠導覽側欄）；聊天欄仍置中。大螢幕、有多章才出現 */}
      {hasChapters && chapters && (
        <aside className="absolute left-1 top-14 hidden w-48 xl:block">
          <div className="space-y-0.5">
            <div className="mb-1 px-2 text-[10px] font-medium uppercase tracking-wide text-muted-foreground/60">本互動章節</div>
            {chapters.map((ch, ci) => (
              <button key={ci} onClick={() => jumpToChapter(ci)} title={ch.title}
                      className={cn("block w-full truncate rounded px-2 py-1 text-left text-xs hover:bg-muted",
                        ci === openIdx ? "font-medium text-foreground" : "text-muted-foreground")}>
                🔖 {ch.title}
              </button>
            ))}
          </div>
        </aside>
      )}

      <div className="mx-auto flex h-full w-full max-w-3xl flex-col">
      <div className="shrink-0 pb-1">
        <h1 className="truncate text-base font-bold md:text-lg" title={convTitle || undefined}>
          {convTitle ? `💬 ${convTitle}` : "🧠 跟你的知識庫聊"}
        </h1>
        {/* spec 046：收到哪裡了。⚠️ 講的是**集合大小**不是水位線——
            覆蓋不連續時（實測對話 44 缺第 3–8 則），水位線會把洞藏起來。 */}
        {messages.length > 0 && (
          <p className="text-xs text-muted-foreground">
            {cov.covered === 0
              ? `${cov.total} 則，還沒收過任何一條`
              : `${cov.total} 則中 ${cov.covered} 則已收（左側有線），還有 ${cov.uncovered} 則沒收`}
            {rangelessCount > 0 && `　·　另有 ${rangelessCount} 條沒記出處範圍（標不到則）`}
          </p>
        )}
        {/* 副標只在還沒開始聊時顯示（聊起來就收，省上邊空間） */}
        {messages.length === 0 && (
          <p className="text-xs text-muted-foreground">
            從你存下的 {rootCount} 條理解出發，有話直說、不順著你講好聽話。
          </p>
        )}
      </div>

      <div className="min-h-0 flex-1 space-y-6 overflow-y-auto py-2">
        {/* spec 041：已帶的文章＝**這一輪的第一則**（使用者裁決 2026-08-21）。
            它讀起來像對話的開場白，隨對話自然捲動，不跟版面搶位置。
            ⚠️ **看起來是第一則，但絕不進 `messages`**——`history` 會被持久化並餵進 distill()，
            文章一旦進去就破掉 FR-003 那道閘門（冊封候選不得由文章原文生成）。
            這是刻意讓「視覺隱喻」與「資料模型」不一致的地方。 */}
        {carried && (
          // 展開收合比照章節：同一組 <details>／▸▾／樣式。人只要學一次。
          // （章節是 uncontrolled、用 ref 開；這裡用受控 open，否則每次打字重繪都會把它掰回展開）
          <details open={carriedOpen} onToggle={(e) => setCarriedOpen(e.currentTarget.open)}
                   className="group rounded-xl bg-card shadow-sm">
            <summary className="flex cursor-pointer list-none items-center px-4 py-2.5 text-sm font-medium hover:bg-muted/40">
              <span className="mr-1 text-muted-foreground group-open:hidden">▸</span>
              <span className="mr-1 hidden text-muted-foreground group-open:inline">▾</span>
              {carried.kind === "article" ? "📄" : "📚"} {carried.title}
              <span className="ml-2 truncate text-xs font-normal text-muted-foreground">
                {carried.kind === "article"
                  ? "AI 依你的理解生成，比理解軟"
                  : "你收進的來源，外部證言——比理解軟"}
              </span>
              <button onClick={(e) => { e.preventDefault(); setCarried(null) }}
                      className="ml-auto shrink-0 pl-2 text-xs font-normal text-muted-foreground hover:text-foreground hover:underline">
                移除
              </button>
            </summary>
            <div className="border-t px-4 py-3">
              {carriedBody === null ? (
                <p className="text-sm text-muted-foreground">載入中…</p>
              ) : carriedBody === "" ? (
                <p className="text-sm text-muted-foreground">找不到內容（可能已封存）。</p>
              ) : (
                <Markdown text={carriedBody} prefix="chatart" />
              )}
            </div>
          </details>
        )}
        {/* 有帶入物時不顯示——它就是這一輪的開場，再擺一個「還沒有開場」的提示是自相矛盾 */}
        {empty && !carried && (
          <div className="flex flex-col items-center gap-3 pt-16 text-center text-muted-foreground">
            <div className="text-5xl">🧠</div>
            <p className="max-w-sm text-sm">
              丟一個想法、一個「為什麼 X 要這樣」，或接著上一句往下問。
              <br />它有話直說，不順著你講好聽話。
            </p>
            {/* spec 068：一天三條複習。放這裡是因為**你正要開始想事情，脈絡剛好**。 */}
            <Rehearse />
          </div>
        )}
        {hasChapters && chapters ? (
          chapters.map((ch, ci) => {
            const isLast = ci === chapters.length - 1
            const isFocus = focusFrom > 0 && ch.start <= focusFrom && ch.end >= focusFrom
            // 最後一章的範圍含本次續聊的新訊息（都在這章的折疊區內）
            const msgs = isLast ? messages.slice(ch.start - 1) : messages.slice(ch.start - 1, ch.end)
            const endLabel = isLast ? messages.length : ch.end
            return (
              <details key={`ch${ci}`} ref={(el) => { chapterRefs.current[ci] = el }}
                       className={cn("group rounded-xl bg-card shadow-sm", isFocus && "ring-2 ring-primary/50")}>
                <summary className="cursor-pointer list-none px-4 py-2.5 text-sm font-medium hover:bg-muted/40">
                  <span className="mr-1 text-muted-foreground group-open:hidden">▸</span>
                  <span className="mr-1 hidden text-muted-foreground group-open:inline">▾</span>
                  {ch.title}
                  <span className="ml-2 text-xs font-normal text-muted-foreground">第 {ch.start}–{endLabel} 則</span>
                  {isFocus && <span className="ml-2 text-xs font-normal text-primary">← 出處</span>}
                  {isLast && <span className="ml-2 text-xs font-normal text-muted-foreground">（最新，接著聊）</span>}
                </summary>
                <div className="space-y-3 border-t px-4 py-3">
                  {msgs.map((m, j) => renderMsg(m, ch.start - 1 + j))}
                </div>
              </details>
            )
          })
        ) : (
          messages.map(renderMsg)
        )}


        {streaming !== null && (
          // 串流中也全寬無框（與完成的 AI 回覆一致）；走 Markdown → 數學/格式當下就渲染
          <div>
            {streaming ? <Markdown text={streaming} prefix="stream" /> : <div className="text-[15px] text-muted-foreground">…</div>}
          </div>
        )}
        {stage && <div className="animate-pulse text-sm text-muted-foreground">{stage}</div>}

        {candidates && (
          <div className="space-y-3 rounded-xl border bg-card p-4">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold">整理出這幾條——挑要精選的（你決定）</h2>
              <button onClick={() => setCandidates(null)}
                      className="text-xs text-muted-foreground hover:underline">收起</button>
            </div>
            {freshCands.length > 0 && (
              <label className="flex items-center gap-2 text-xs text-muted-foreground">
                <input type="checkbox" checked={saveConvo}
                       onChange={(e) => setSaveConvo(e.target.checked)} />
                連同這段互動存成「由來」
              </label>
            )}
            {freshCands.length === 0 && (
              <p className="text-sm text-muted-foreground">這段沒整理出值得長期留的重點。</p>
            )}
            {candidates.map((c, i) =>
              c.already ? (
                <div key={i} className="text-xs text-muted-foreground">✓ 已在理解：{c.claim}</div>
              ) : candDone[i] ? (
                <div key={i} className="rounded-lg border p-3 text-sm text-primary">{candDone[i]}</div>
              ) : (
                // spec 046：⚠️ 冊封前可以改。沿用來源頁 SourceCandidateCard 的形狀
                //（主張可改、層次可改）——同一件事不要有兩套介面。
                // 後端本來就收改過的 claim/kind（`_do_anoint`），所以這是純前端。
                <div key={i} className="space-y-2 rounded-lg border p-3">
                  <Input value={edits[i]?.claim ?? c.claim}
                         onChange={(e: React.ChangeEvent<HTMLInputElement>) => setEdit(i, { claim: e.target.value })}
                         className="font-medium" />
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className="text-xs text-muted-foreground">層次：</span>
                    {KINDS.map((k) => {
                      const cur = edits[i]?.kind ?? c.kind ?? ""
                      return (
                        <button key={k} onClick={() => setEdit(i, { kind: cur === k ? "" : k })}
                                className={cn("rounded px-2 py-0.5 text-xs transition",
                                  cur === k ? "bg-primary text-primary-foreground"
                                            : "bg-muted text-muted-foreground hover:text-foreground")}>
                          {k}
                        </button>
                      )
                    })}
                  </div>
                  <Button size="sm" onClick={() => anointOne(i, c)}>精選這條</Button>
                </div>
              ),
            )}
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {showNudge && (
        <div className="mb-2 flex shrink-0 items-center gap-2 rounded-lg border bg-muted px-3 py-2 text-xs text-muted-foreground">
          <span>聊了一大段（{uncharted} 則還沒整理）——整理成章節、方便回頭找？</span>
          <button onClick={reslice} disabled={busy} className="ml-auto font-medium text-primary hover:underline">🔖 整理成章節</button>
          <button onClick={() => setNudgeDismissed(true)} title="先不要" className="hover:text-foreground">✕</button>
        </div>
      )}

      <div className="shrink-0 pt-2">
        <div className="flex items-end gap-2 rounded-2xl bg-muted px-3 py-2 focus-within:ring-1 focus-within:ring-ring">
          <Textarea
            rows={1}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              // 輸入法組字中的 Enter＝選字確認，不是送出（isComposing / keyCode 229）
              if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing && e.keyCode !== 229) { e.preventDefault(); send() }
            }}
            placeholder="丟個想法，或接著往下問…"
            className="max-h-40 min-h-0 resize-none border-0 bg-transparent p-1 shadow-none focus-visible:ring-0"
          />
          <Button size="icon" className="shrink-0 rounded-full" disabled={busy} onClick={send}
                  aria-label="送出">↑</Button>
        </div>
        <div className="flex items-center gap-x-4 pt-1">
          <label className="flex items-center gap-1 text-xs text-muted-foreground"
                 title="這輪暫時不參考你的理解與收藏、也不撒網，就當一般 AI 聊（隨時可取消）">
            <input type="checkbox" checked={bare}
                   onChange={(e) => setBare(e.target.checked)} />
            🔌 不接知識庫
          </label>
          {/* 其餘動作收進「⋯ 更多」，預設收起（省底部空間，尤其手機） */}
          {messages.length > 0 && (
            <div ref={moreRef} className="relative">
              <button onClick={() => setMore((v) => !v)}
                      className="cursor-pointer text-xs text-muted-foreground hover:text-foreground">⋯ 更多</button>
              {more && (
              <div className="absolute bottom-full left-0 z-30 mb-1 w-44 overflow-hidden rounded-md border bg-popover py-1 shadow-md">
                <button onClick={distill} disabled={busy} className="block w-full px-3 py-1.5 text-left text-sm hover:bg-accent">🧵 整理成重點</button>
                {/* spec 043：用這段對話冊封出的理解當骨幹生一篇文章。
                    ⚠️ 需要這段已經被存下來（tempId）——autosave 每輪都會做，所以正常情況一定有。 */}
                <button onClick={genArticleFromConv} disabled={busy}
                        className="block w-full px-3 py-1.5 text-left text-sm hover:bg-accent">🧩 用這段生一份應用</button>
                {/* spec 047：檢視頁退場，它獨有的動作搬過來——刪頁面最容易的錯
                    就是順手弄丟一個只有那頁有的動作（SC-003：能力集合的差＝0）。 */}
                <button onClick={retitleConv} disabled={busy || !tempId.current}
                        className="block w-full px-3 py-1.5 text-left text-sm hover:bg-accent">🏷 重生標題</button>
                <button onClick={reslice} disabled={busy || !tempId.current}
                        className="block w-full px-3 py-1.5 text-left text-sm hover:bg-accent">🔖 重新分章</button>
                <button onClick={() => copyChat("md")} className="block w-full px-3 py-1.5 text-left text-sm hover:bg-accent">📋 複製 Markdown</button>
                <button onClick={() => copyChat("urls")} className="block w-full px-3 py-1.5 text-left text-sm hover:bg-accent">🔗 複製來源</button>
                {/* 整理與離場也該在這裡——不然要離開對話、繞去領域頁才做得到 */}
                <div className="my-1 border-t" />
                <div className="px-3 py-1">
                  <select value="" aria-label="搬到領域" disabled={busy || !tempId.current}
                          className="w-full rounded border bg-background px-1 py-0.5 text-sm"
                          onChange={(e) => { if (e.target.value !== "") moveThisConv(e.target.value) }}>
                    <option value="">🗂 搬到領域…</option>
                    <option value="0">🗂 知識庫</option>
                    {allDomains.map((d) => (
                      <option key={d.id} value={d.id}>{d.path.map((x) => x.name).join(" / ")}</option>
                    ))}
                  </select>
                </div>
                <button onClick={archiveThisConv} disabled={busy || !tempId.current}
                        className="block w-full px-3 py-1.5 text-left text-sm text-destructive hover:bg-accent">📦 封存這段</button>
              </div>
              )}
            </div>
          )}
        </div>
      </div>

      {flash && (
        <div className="fixed bottom-6 left-1/2 z-50 -translate-x-1/2 rounded-lg bg-foreground px-4 py-2 text-sm text-background shadow-lg">
          {flash}
        </div>
      )}
      </div>
    </div>
  )
}
