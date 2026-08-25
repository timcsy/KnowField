import { describe, it, expect } from "vitest"
import { keyOf, pickedRefs, inDomain } from "../knowledge"
import type { KnowledgeItem } from "../api"

const it_ = (kind: KnowledgeItem["kind"], ref: number | string, domain_id: number | null = null):
  KnowledgeItem => ({ kind, ref, label: `${kind}#${ref}`, domain_id })

describe("整理台的選取鍵（spec 050）", () => {
  it("⚠️ 不同種類的同一個 id 不可以撞在一起", () => {
    expect(keyOf({ kind: "article", ref: 5 })).not.toBe(keyOf({ kind: "why_node", ref: 5 }))
  })

  it("來源的 ref 是 url，也產得出鍵", () => {
    expect(keyOf({ kind: "source", ref: "https://a.b/c" })).toBe("source:https://a.b/c")
  })

  it("⚠️ 勾一件 MUST NOT 搬走兩件", () => {
    const items = [it_("article", 5), it_("why_node", 5)]
    const picked = new Set([keyOf({ kind: "article", ref: 5 })])
    expect(pickedRefs(items, picked)).toEqual([{ kind: "article", ref: 5 }])
  })

  it("送出的清單保持清冊順序", () => {
    const items = [it_("source", "u"), it_("conversation", 1), it_("article", 2)]
    const picked = new Set(items.map(keyOf))
    expect(pickedRefs(items, picked).map((r) => r.kind))
      .toEqual(["source", "conversation", "article"])
  })
})

describe("領域底下的知識", () => {
  it("未歸屬用 null，而 undefined 也算未歸屬", () => {
    const items = [it_("conversation", 1, null), it_("conversation", 2, 7),
                   { ...it_("article", 3), domain_id: undefined } as unknown as KnowledgeItem]
    expect(inDomain(items, null).map((i) => i.ref)).toEqual([1, 3])
    expect(inDomain(items, 7).map((i) => i.ref)).toEqual([2])
  })

  it("⚠️ 領域 0 不可以被當成未歸屬", () => {
    // 0 是 falsy——用 `||` 而不是 `??` 就會把領域 0 的東西全歸到未歸屬。
    const items = [it_("conversation", 1, 0), it_("conversation", 2, null)]
    expect(inDomain(items, 0).map((i) => i.ref)).toEqual([1])
    expect(inDomain(items, null).map((i) => i.ref)).toEqual([2])
  })
})
