import { useEffect, useRef } from "react"

// 把各種數學分隔符正規化成 Markdown 習慣（供複製）：\(..\)→$..$、\[..\]→$$..$$、$/$$ 保留。
function toMarkdownMath(tex: string): string {
  const t = tex.trim()
  if (t.startsWith("$$") && t.endsWith("$$")) return t
  if (t.startsWith("\\[") && t.endsWith("\\]")) return "$$" + t.slice(2, -2).trim() + "$$"
  if (t.startsWith("\\(") && t.endsWith("\\)")) return "$" + t.slice(2, -2).trim() + "$"
  if (t.startsWith("$") && t.endsWith("$")) return t
  return t
}

const escHtml = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")

// 內容變化後 debounce typeset 整頁（比逐元件 typesetPromise([el]) 可靠——
// 後者在 resume/re-render 的時序下會錯過；整頁 typeset 就是手動觸發也 work 的那招）。
let _typesetTimer: ReturnType<typeof setTimeout> | null = null
let _firstRequestAt = 0          // 這一串連續請求的起點——用來上限住 debounce
const DEBOUNCE_MS = 80
const MAX_WAIT_MS = 500          // ⚠️ 串流每個 token 都會來一次，純 debounce 會被無限延後

/** 這個節點是不是**真的**被 MathJax 排版過。
 *
 * ⚠️ 用 DOM 證據（MathJax 會塞 `mjx-container`），不用我們自己標的旗標。
 * 舊版是 `mark()` 把當下所有 `.mathcopy` 一律標成 `data-typeset` ——那標的是
 * 「我呼叫過 typeset」而不是「這個節點真的被排版了」：在 typeset 開始**之後**才進 DOM 的
 * 節點會被誤標，於是漏網偵測永遠找不到它們，**永久卡成原始碼**。
 * 這正是 history/091 自己寫下的結論（驗 DOM 實際渲染狀態，而非「我觸發過」）被它自己的 mark() 違反。
 */
function isTypeset(el: Element): boolean {
  return !!el.querySelector("mjx-container") || el.getAttribute("data-mj-skip") === "1"
}

function rawMathNodes(): Element[] {
  return Array.from(document.querySelectorAll(".mathcopy")).filter((el) => !isTypeset(el))
}

export function scheduleTypeset() {
  const w = window as unknown as {
    MathJax?: { typesetPromise?(): Promise<void>; startup?: { promise?: Promise<unknown> } }
  }
  const now = Date.now()
  if (!_typesetTimer) _firstRequestAt = now
  // 上限：距離這一串請求的起點超過 MAX_WAIT_MS 就別再延後了，立刻排。
  const waited = now - _firstRequestAt
  const delay = waited >= MAX_WAIT_MS ? 0 : Math.min(DEBOUNCE_MS, MAX_WAIT_MS - waited)
  if (_typesetTimer) clearTimeout(_typesetTimer)
  _typesetTimer = setTimeout(() => {
    _typesetTimer = null
    _firstRequestAt = 0
    // 兜底重跑抓漏網：MathJax 還在載／圖片 reflow／串流剛換節點的內容會晚到。
    // 判準用 DOM 證據（見 isTypeset），所以誤標不可能發生；冪等⇒重跑無害。
    let attempts = 0
    const MAX_ATTEMPTS = 4          // history/091 寫的就是 4，但當時的實作其實只重試 1 次
    const run = (): void => {
      attempts++
      w.MathJax?.typesetPromise?.().then(() => {
        if (rawMathNodes().length > 0 && attempts < MAX_ATTEMPTS) setTimeout(run, 400)
      }).catch(() => {})
    }
    if (w.MathJax?.typesetPromise) run()                              // 已 ready
    else if (w.MathJax?.startup?.promise) w.MathJax.startup.promise.then(run)  // 載入中
    else {                                                           // script 還沒執行→輪詢等（10s）
      let n = 0
      const iv = setInterval(() => {
        if (w.MathJax?.typesetPromise) { clearInterval(iv); run() }
        else if (++n > 50) clearInterval(iv)
      }, 200)
    }
  }, delay)
}

// 答案/原文 → HTML：math 抽出佔位 → marked 渲染 → 還原成 .mathcopy(帶 data-tex) → [n] 變引用錨點。
export function renderHtml(text: string, prefix = "src"): string {
  const marked = (window as unknown as { marked?: { parse(s: string): string } }).marked
  const math: string[] = []
  // 行內 $..$ 容許單一換行（但不跨空行/段落）——否則含換行的行內數學漏抓、留下落單 $ 造成後續配對連鎖崩壞
  let t = text.replace(
    /\$\$[\s\S]+?\$\$|\$(?:[^\n$]|\n(?!\n))+?\$|\\\([\s\S]+?\\\)|\\\[[\s\S]+?\\\]/g,
    (m) => { math.push(m); return `@@M${math.length - 1}@@` },
  )
  // CJK 粗體：marked 的 CommonMark flanking 規則對全形標點失效（如「完整。**真正」的 ** 無法閉合、露出星號）
  // → 先手動抽 **…** 成佔位、繞過 marked，最後還原成 <strong>（inner 可能含 @@M，於數學步統一還原）。
  const bold: string[] = []
  t = t.replace(/\*\*(?!\s)([^\n]+?)\*\*/g, (_m, inner) => { bold.push(inner); return `@@B${bold.length - 1}@@` })
  let html = marked ? marked.parse(t) : t.replace(/\n/g, "<br>")
  html = html.replace(/@@B(\d+)@@/g, (_m, i) => `<strong>${escHtml(bold[+i])}</strong>`)
  html = html.replace(/@@M(\d+)@@/g, (_m, i) => {
    const tex = math[+i]
    const isBlock = /^\$\$|^\\\[/.test(tex)
    const tag = isBlock ? "div" : "span"
    // span 內文＝原始分隔符（MathJax 渲染用）；data-tex＝正規化 Markdown（複製用）
    const dataTex = escHtml(toMarkdownMath(tex)).replace(/"/g, "&quot;")
    return `<${tag} class="mathcopy${isBlock ? " mathcopy-block" : ""}" title="雙擊選取、Ctrl/⌘+C 複製 LaTeX" data-tex="${dataTex}">${escHtml(tex)}</${tag}>`
  })
  return html.replace(/\[(\d+)\]/g, (_m, n) => `<a href="#${prefix}-${n}" class="cite">[${n}]</a>`)
}

export function Markdown({ text, prefix = "src" }: { text: string; prefix?: string }) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    scheduleTypeset()   // MathJax：內容變化後 debounce typeset 整頁
    // 圖 hotlink 失效→替代連結（不留破圖）
    el.querySelectorAll("img").forEach((im) => {
      im.addEventListener("error", () => {
        const a = document.createElement("a")
        a.href = im.src; a.target = "_blank"; a.rel = "noopener"
        a.className = "text-xs text-muted-foreground underline"
        a.textContent = "🖼 圖片（原站，點開）"
        im.replaceWith(a)
      }, { once: true })
    })
  }, [text])
  return (
    <div
      ref={ref}
      className="answer-md text-[15px] leading-relaxed"
      dangerouslySetInnerHTML={{ __html: renderHtml(text, prefix) }}
    />
  )
}

// 選取數學 → Ctrl/⌘+C 複製 LaTeX 原始碼（含 $）。刻意不做「點公式就複製」（使用者要求）。掛一次即全站生效。
export function installMathCopy(): () => void {
  const mathOf = (n: Node | null): Element | null => {
    if (!n) return null
    const el = n.nodeType === 1 ? (n as Element) : n.parentElement
    return el ? el.closest(".mathcopy") : null
  }
  // MathJax 渲染後公式無可拖曳選取的文字→單獨反白很難；雙擊即整塊反白（仍由使用者自己按 Ctrl/⌘+C，非自動複製）。
  function onDblClick(e: MouseEvent) {
    const mc = mathOf(e.target as Node)
    if (!mc) return
    const sel = window.getSelection()
    if (!sel) return
    sel.removeAllRanges()
    const r = document.createRange()
    r.selectNode(mc)
    sel.addRange(r)
    // 公式無文字節點→瀏覽器 ::selection 高亮畫不出來，改自己上底色當視覺回饋
    document.querySelectorAll(".mathcopy.is-selected").forEach((el) => el.classList.remove("is-selected"))
    mc.classList.add("is-selected")
    const clear = (ev: Event) => {
      if (ev.type === "mousedown" && mathOf(ev.target as Node) === mc) return  // 再點同一條→不清
      mc.classList.remove("is-selected")
      document.removeEventListener("mousedown", clear, true)
    }
    document.addEventListener("mousedown", clear, true)
  }
  function onCopy(e: ClipboardEvent) {
    const sel = window.getSelection()
    if (!sel || sel.rangeCount === 0 || sel.isCollapsed || !e.clipboardData) return
    const frag = sel.getRangeAt(0).cloneContents()
    const maths = frag.querySelectorAll(".mathcopy")
    if (maths.length === 0) {
      const a = mathOf(sel.anchorNode)
      if (a && a === mathOf(sel.focusNode)) {
        e.clipboardData.setData("text/plain", a.getAttribute("data-tex") || "")
        e.preventDefault()
      }
      return
    }
    maths.forEach((m) => {
      const tex = m.getAttribute("data-tex") || ""
      const block = m.classList.contains("mathcopy-block")
      m.replaceWith(document.createTextNode(block ? `\n${tex}\n` : tex))
    })
    e.clipboardData.setData("text/plain", frag.textContent || "")
    e.preventDefault()
  }
  document.addEventListener("copy", onCopy)
  document.addEventListener("dblclick", onDblClick)
  return () => {
    document.removeEventListener("copy", onCopy)
    document.removeEventListener("dblclick", onDblClick)
  }
}
