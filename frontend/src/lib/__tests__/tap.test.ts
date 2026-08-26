import { describe, it, expect } from "vitest"
import { isTap, TAP_SLOP } from "../tap"

describe("點選 vs 滑動（spec 059）", () => {
  it("原地按放＝點選", () => {
    expect(isTap({ x: 100, y: 200 }, { x: 100, y: 200 })).toBe(true)
  })

  it("⚠️ 捲動的距離 MUST NOT 被當成點選", () => {
    expect(isTap({ x: 100, y: 200 }, { x: 100, y: 260 })).toBe(false)
  })

  it("手指小幅抖動仍算點選——按著本來就會抖", () => {
    expect(isTap({ x: 100, y: 200 }, { x: 100 + TAP_SLOP - 1, y: 200 })).toBe(true)
  })

  it("剛好在門檻上算點選（邊界）", () => {
    expect(isTap({ x: 0, y: 0 }, { x: TAP_SLOP, y: 0 })).toBe(true)
  })

  it("⚠️ 沒有起點時 MUST 當成點選——寧可放行，不要吃掉鍵盤/程式觸發的點擊", () => {
    expect(isTap(null, { x: 999, y: 999 })).toBe(true)
  })

  it("斜著滑也算滑動（用歐氏距離，不是只看 y）", () => {
    expect(isTap({ x: 0, y: 0 }, { x: 8, y: 8 })).toBe(false)
  })
})
