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

// 答案/原文 → HTML：math 抽出佔位 → marked 渲染 → 還原成 .mathcopy(帶 data-tex) → [n] 變引用錨點。
export function renderHtml(text: string, prefix = "src"): string {
  const marked = (window as unknown as { marked?: { parse(s: string): string } }).marked
  const math: string[] = []
  const t = text.replace(
    /\$\$[\s\S]+?\$\$|\$[^\n$]+?\$|\\\([\s\S]+?\\\)|\\\[[\s\S]+?\\\]/g,
    (m) => { math.push(m); return `@@M${math.length - 1}@@` },
  )
  let html = marked ? marked.parse(t) : t.replace(/\n/g, "<br>")
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
    const mj = (window as unknown as {
      MathJax?: { typesetPromise?(els: Element[]): Promise<void> }
    }).MathJax
    if (mj?.typesetPromise) mj.typesetPromise([el]).catch(() => {})
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
