import { useEffect, useRef } from "react"

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
    const esc = tex.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    const isBlock = /^\$\$|^\\\[/.test(tex)
    const tag = isBlock ? "div" : "span"
    return `<${tag} class="mathcopy${isBlock ? " mathcopy-block" : ""}" data-tex="${esc.replace(/"/g, "&quot;")}">${esc}</${tag}>`
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
  return () => document.removeEventListener("copy", onCopy)
}
