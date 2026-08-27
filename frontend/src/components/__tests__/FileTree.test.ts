import { describe, expect, it } from "vitest"
import { buildTree, type Node } from "../FileTree"

const P = (...paths: string[]) => paths.map((path, i) => ({ id: i + 1, path }))
const names = (ns: Node[]): string[] => ns.map((n) => (n.children ? `${n.name}/` : n.name))
const find = (ns: Node[], name: string): Node | undefined =>
  ns.find((n) => n.name === name)

describe("buildTree", () => {
  it("剝掉 knowledge/ 前綴", () => {
    expect(names(buildTree(P("knowledge/experience.md")))).toEqual(["experience.md"])
  })

  it("資料夾在檔案前面，各自照字母排", () => {
    const t = buildTree(P("knowledge/vision.md", "knowledge/draft/b.md",
                          "knowledge/experience.md", "knowledge/concepts/a.md"))
    expect(names(t)).toEqual(["concepts/", "draft/", "experience.md", "vision.md"])
  })

  // ⚠️ skills/ 是巢狀的（`skills/knowie-pull/SKILL.md`）——之前那個「層 ＋ 平面清單」
  //    的形狀**說不出巢狀**，而 knowledge/ 本來就是巢狀的。
  it("深度不限", () => {
    const t = buildTree(P("knowledge/skills/knowie-pull/SKILL.md"))
    const skills = find(t, "skills")!
    const pull = find(skills.children!, "knowie-pull")!
    expect(names(pull.children!)).toEqual(["SKILL.md"])
    expect(pull.children![0].id).toBe(1)
  })

  it("資料夾帶「含子孫」的計數", () => {
    const t = buildTree(P("knowledge/skills/a/X.md", "knowledge/skills/b/Y.md",
                          "knowledge/skills/README.md"))
    expect(find(t, "skills")!.count).toBe(3)
  })

  it("只有檔案節點有 id——資料夾點下去是展開，不是開檔", () => {
    const t = buildTree(P("knowledge/draft/a.md"))
    expect(find(t, "draft")!.id).toBeUndefined()
    expect(find(find(t, "draft")!.children!, "a.md")!.id).toBe(1)
  })

  it("同名的資料夾與檔案不會互相吃掉", () => {
    const t = buildTree(P("knowledge/skills/x.md", "knowledge/skills.md"))
    expect(names(t)).toEqual(["skills/", "skills.md"])
  })

  it("檔案節點保留完整原始路徑（預覽要靠它顯示出處）", () => {
    const t = buildTree(P("knowledge/history/140-x.md"))
    expect(find(find(t, "history")!.children!, "140-x.md")!.path)
      .toBe("knowledge/history/140-x.md")
  })

  it("空的就是空的", () => expect(buildTree([])).toEqual([]))
})
