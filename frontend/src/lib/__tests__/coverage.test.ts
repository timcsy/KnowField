import { describe, it, expect } from "vitest"
import { coveredSet, coverageSummary } from "../coverage"

describe("冊封覆蓋（集合，不是水位線）", () => {
  it("⚠️ 中間的洞要看得見——這條是本檔存在的理由", () => {
    // 對話 44 的真實形狀：收到第 44 則，但第 27–30 從沒被收過
    const covered = coveredSet([{ from: 9, to: 26 }, { from: 31, to: 44 }], 46)
    expect(covered.has(26)).toBe(true)
    expect(covered.has(31)).toBe(true)
    for (const i of [27, 28, 29, 30]) {
      expect(covered.has(i)).toBe(false)   // ⚠️ 水位線實作會讓這四條全 true
    }
    expect(covered.has(45)).toBe(false)    // 尾巴也沒收
  })

  it("開頭的洞也要看得見", () => {
    const covered = coveredSet([{ from: 9, to: 26 }], 26)
    expect([...Array(8)].every((_, i) => !covered.has(i + 1))).toBe(true)
  })

  it("沒有範圍的舊冊封（0/0）忽略，不算成已收", () => {
    expect(coveredSet([{ from: 0, to: 0 }], 10).size).toBe(0)
  })

  it("髒資料：from > to、超出訊息數", () => {
    expect(coveredSet([{ from: 5, to: 2 }], 10).size).toBe(0)
    expect(coveredSet([{ from: 8, to: 99 }], 10).size).toBe(3)   // 取交集 8,9,10
  })

  it("摘要不講水位線，講的是集合大小", () => {
    const s = coverageSummary([{ from: 9, to: 26 }, { from: 31, to: 44 }], 46)
    expect(s).toEqual({ total: 46, covered: 32, uncovered: 14 })
  })

  it("空的", () => {
    expect(coverageSummary([], 10)).toEqual({ total: 10, covered: 0, uncovered: 10 })
  })
})
