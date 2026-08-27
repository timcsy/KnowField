import { describe, expect, it } from "vitest"
import { layersOf } from "../DevSidebar"

const P = (...paths: string[]) => paths.map((path) => ({ path }))

describe("layersOf", () => {
  it("資料夾歸成一層，根目錄的檔各自成一層", () => {
    const l = layersOf(P("knowledge/experience.md", "knowledge/history/1.md",
                         "knowledge/history/2.md", "knowledge/vision.md"))
    expect(l.map((x) => [x.key, x.n])).toEqual([
      ["vision.md", 1], ["experience.md", 1], ["history", 2],
    ])
  })

  // ⚠️ 順序是**膜的流向**（原則→路線圖→經驗→概念→歷史→…），不是字母序：
  //    位置固定，你才記得住它在哪一行。
  it("認得的層照固定順序，其餘排在後面照字母", () => {
    const l = layersOf(P("knowledge/zzz/a.md", "knowledge/history/1.md",
                         "knowledge/principles.md", "knowledge/aaa/b.md"))
    expect(l.map((x) => x.key)).toEqual(["principles.md", "history", "aaa", "zzz"])
  })

  // 只有一份的層點下去要**直接開那一份**（`experience.md`），所以要說得出它是誰
  it("只有一份時給得出那一份的完整路徑", () => {
    const l = layersOf(P("knowledge/experience.md", "knowledge/history/1.md",
                         "knowledge/history/2.md"))
    expect(l.find((x) => x.key === "experience.md")!.only).toBe("knowledge/experience.md")
    expect(l.find((x) => x.key === "history")!.only).toBe("")
  })

  it("空的就是空的", () => expect(layersOf([])).toEqual([]))
})
