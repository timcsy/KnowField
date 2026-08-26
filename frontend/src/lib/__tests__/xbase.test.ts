import { describe, expect, it } from "vitest"
import { BORROWED, borrowedBases } from "../api"

// spec 071：`origin` 的前綴是前後端**唯一**的共識面。
// ⚠️ 它一旦跟後端的 `Repository.BORROWED` 不同步，收件匣就會安靜地空掉
//    ——沒有錯誤、沒有紅字，只是那些借來的判準從此看不見。
describe("borrowedBases", () => {
  it("跟後端同一個前綴", () => expect(BORROWED).toBe("from:"))

  it("拆得出跨過哪幾個知識庫", () =>
    expect(borrowedBases("from:KnowField,VizGPT,semorphe"))
      .toEqual(["KnowField", "VizGPT", "semorphe"]))

  it("單一來源也算借來的", () =>
    expect(borrowedBases("from:VizGPT")).toEqual(["VizGPT"]))

  it("自己寫的、AI 蒸餾的都不是借來的", () => {
    for (const o of ["", "self", "self:judgment"]) expect(borrowedBases(o)).toEqual([])
  })

  // ⚠️ `origin` 可能是 undefined（舊資料、或後端沒回這個欄位）——不能整頁炸掉
  it("壞值不炸", () =>
    expect(borrowedBases(undefined as unknown as string)).toEqual([]))

  it("空的 base 名字不算一個", () =>
    expect(borrowedBases("from:")).toEqual([]))
})
