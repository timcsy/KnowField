/**
 * Markdown.tsx 的測試（spec：無——這是補的，見 history/091 與本輪）。
 *
 * ⚠️ 這個元件被 6 個介面共用、已經出過三次線上 bug（全形粗體、typeset 競態、
 * 串流時退回原始碼），而在此之前**一行測試都沒有**。每一次都是使用者在線上撞到的。
 */
import { beforeEach, describe, expect, it, vi } from "vitest"

import { renderHtml, scheduleTypeset } from "../Markdown"

describe("renderHtml：數學抽取", () => {
  it("行內 $..$ 變成 mathcopy span", () => {
    const h = renderHtml("當 $x_t$ 時")
    expect(h).toContain('class="mathcopy"')
    expect(h).not.toContain('class="mathcopy mathcopy-block"')
  })

  it("區塊 $$..$$ 變成 block div", () => {
    expect(renderHtml("$$ p(x) = 1 $$")).toContain("mathcopy-block")
  })

  it("\\(..\\) 與 \\[..\\] 也算數學", () => {
    expect(renderHtml("見 \\(a+b\\) 這裡")).toContain("mathcopy")
    expect(renderHtml("見 \\[a+b\\] 這裡")).toContain("mathcopy-block")
  })

  it("data-tex 正規化成 markdown 形式（供複製）", () => {
    expect(renderHtml("見 \\(a\\) 這")).toContain('data-tex="$a$"')
    expect(renderHtml("見 \\[a\\] 這")).toContain('data-tex="$$a$$"')
  })

  it("行內數學可含單一換行，但不跨空行", () => {
    expect(renderHtml("$a\nb$")).toContain("mathcopy")
    // 跨空行不該被當成一條數學（否則落單的 $ 會造成後續配對連鎖崩壞）
    expect(renderHtml("$a\n\nb$")).not.toContain("mathcopy")
  })

  it("數學內容被 escape，不會變成 HTML", () => {
    const h = renderHtml("$a < b$")
    expect(h).toContain("&lt;")
    expect(h).not.toMatch(/<(?!\/?(span|div|p|a|strong)\b)/)
  })
})

describe("renderHtml：CJK 粗體（history/091 坑一的迴歸測試）", () => {
  it("全形句號後的 ** 仍能閉合", () => {
    const h = renderHtml("完整。**真正**的重點")
    expect(h).toContain("<strong>真正</strong>")
    expect(h).not.toContain("**")
  })

  it("粗體內含數學不壞", () => {
    const h = renderHtml("**當 $x$ 時**")
    expect(h).toContain("<strong>")
    expect(h).toContain("mathcopy")
  })
})

describe("renderHtml：引用錨點", () => {
  it("[n] 變成錨點且帶 prefix", () => {
    expect(renderHtml("見 [3]", "m7")).toContain('href="#m7-3"')
  })
})

/** 假的 MathJax：記錄呼叫次數，並模擬「只處理呼叫當下已在 DOM 的節點」。 */
function fakeMathJax() {
  const calls: number[] = []
  return {
    calls,
    typesetPromise: vi.fn(async () => {
      const n = document.querySelectorAll(".mathcopy").length
      calls.push(n)
      // 真 MathJax 會在節點內產生 mjx-container；用它當「真的排版過」的證據
      document.querySelectorAll(".mathcopy").forEach((el) => {
        if (!el.querySelector("mjx-container")) el.appendChild(document.createElement("mjx-container"))
      })
    }),
  }
}

describe("scheduleTypeset：串流期間", () => {
  beforeEach(() => {
    vi.useFakeTimers()
    document.body.innerHTML = ""
    ;(window as any).MathJax = fakeMathJax()
  })

  it("⚠️ 高頻呼叫時仍必須排版——不能被 debounce 無限延後", () => {
    document.body.innerHTML = '<span class="mathcopy">$x$</span>'
    const mj = (window as any).MathJax
    // 模擬串流：每 20ms 一個 token，共 2 秒（LLM token 間隔遠小於 debounce 的 80ms）
    for (let i = 0; i < 100; i++) {
      scheduleTypeset()
      vi.advanceTimersByTime(20)
    }
    expect(mj.typesetPromise).toHaveBeenCalled()
  })
})

describe("scheduleTypeset：漏網偵測（D2／D3）", () => {
  beforeEach(() => {
    vi.useFakeTimers()
    document.body.innerHTML = ""
    ;(window as any).MathJax = fakeMathJax()
  })

  it("⚠️ 在 typeset 開始之後才進 DOM 的節點必須被抓到重跑", async () => {
    // 舊實作的致命處：typeset 後把**當下所有** .mathcopy 一律標成 data-typeset，
    // 包含這種晚到的——於是漏網偵測永遠找不到它，永久卡成原始碼。
    document.body.innerHTML = '<span class="mathcopy" id="a">$x$</span>'
    const mj = (window as any).MathJax
    mj.typesetPromise.mockImplementationOnce(async () => {
      // 這一輪只處理已在 DOM 的 #a；處理途中 #b 才進來（模擬串流換節點）
      document.querySelector("#a")!.appendChild(document.createElement("mjx-container"))
      document.body.insertAdjacentHTML("beforeend", '<span class="mathcopy" id="b">$y$</span>')
    })
    scheduleTypeset()
    await vi.advanceTimersByTimeAsync(100)
    await vi.advanceTimersByTimeAsync(500)   // 讓兜底重跑有機會發生
    expect(document.querySelector("#b")!.querySelector("mjx-container"),
      "晚到的節點沒有被重跑抓到——它會永久停在原始碼").not.toBeNull()
  })

  it("重試次數上限為 4（文件說 4，舊實作只做 1）", async () => {
    document.body.innerHTML = '<span class="mathcopy">$x$</span>'
    const mj = (window as any).MathJax
    mj.typesetPromise.mockImplementation(async () => { /* 永遠不排版→模擬持續漏網 */ })
    scheduleTypeset()
    await vi.advanceTimersByTimeAsync(100)
    for (let i = 0; i < 8; i++) await vi.advanceTimersByTimeAsync(400)
    expect(mj.typesetPromise.mock.calls.length).toBe(4)
  })

  it("已排版的節點不會被誤判為漏網（冪等）", async () => {
    document.body.innerHTML = '<span class="mathcopy"><mjx-container></mjx-container></span>'
    const mj = (window as any).MathJax
    scheduleTypeset()
    await vi.advanceTimersByTimeAsync(100)
    await vi.advanceTimersByTimeAsync(500)
    expect(mj.typesetPromise.mock.calls.length).toBe(1)
  })
})
