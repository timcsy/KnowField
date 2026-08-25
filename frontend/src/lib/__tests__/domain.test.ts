import { describe, it, expect } from "vitest"
import { withDomain } from "../domain"

describe("當前領域跟著換頁走（spec 052）", () => {
  it("根領域不加參數", () => {
    expect(withDomain("/roots", null)).toBe("/roots")
  })
  it("⚠️ 換頁 MUST NOT 讓你掉出你站的地方", () => {
    expect(withDomain("/roots", 7)).toBe("/roots?d=7")
  })
  it("路徑已有 query 時用 &", () => {
    expect(withDomain("/?new=1", 7)).toBe("/?new=1&d=7")
  })
  it("⚠️ 領域 0 是根，不是領域 0", () => {
    // 後端的 0 ＝ 根；前端一律用 null 表示，避免 0 被 falsy 吃掉
    expect(withDomain("/x", null)).toBe("/x")
  })
})
