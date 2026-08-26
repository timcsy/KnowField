import { describe, it, expect, beforeEach } from "vitest"
import { readRecent, touchRecent, liveRecent } from "../recent"

beforeEach(() => { try { localStorage.clear() } catch { /* ignore */ } })

describe("最近存取的領域（spec 053）", () => {
  it("新的在前", () => {
    touchRecent(1); touchRecent(2)
    expect(readRecent().map((r) => r.id)).toEqual([2, 1])
  })

  it("⚠️ 同一個領域造訪兩次只留一筆", () => {
    touchRecent(1); touchRecent(2); touchRecent(1)
    expect(readRecent().map((r) => r.id)).toEqual([1, 2])
  })

  it("根領域不記——它一直都在側欄頂端", () => {
    touchRecent(null)
    expect(readRecent()).toEqual([])
  })

  it("上限 8 筆", () => {
    for (let i = 1; i <= 12; i++) touchRecent(i)
    expect(readRecent().length).toBe(8)
    expect(readRecent()[0].id).toBe(12)
  })

  it("⚠️ 已刪掉的領域不可以出現——列一個點了會壞的東西比不列更糟", () => {
    touchRecent(1); touchRecent(2); touchRecent(3)
    expect(liveRecent(readRecent(), new Set([1, 3])).map((r) => r.id)).toEqual([3, 1])
  })

  it("壞掉的 localStorage 內容不會炸掉頁面", () => {
    try { localStorage.setItem("kf.recentDomains", "{不是陣列}") } catch { /* ignore */ }
    expect(readRecent()).toEqual([])
  })
})
