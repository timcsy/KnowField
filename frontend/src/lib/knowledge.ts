import type { KnowledgeItem, KnowledgeKind, KnowledgeRef } from "./api"

// 整理台的選取鍵（spec 050）。
// ⚠️ **必須含 kind**：文章 #5 和核心理解 #5 是兩件不同的東西，只用 ref 會撞在一起
// ——撞了不會報錯，只會讓你勾一件、搬走兩件。
// ⚠️ 來源的 ref 是 url（字串），所以一律轉成字串比對。
export const keyOf = (i: KnowledgeRef) => `${i.kind}:${i.ref}`

/** 選取集合 → 送給後端的清單（保持清冊順序）。 */
export function pickedRefs(items: KnowledgeItem[], picked: Set<string>): KnowledgeRef[] {
  return items.filter((i) => picked.has(keyOf(i))).map((i) => ({ kind: i.kind, ref: i.ref }))
}

/** 一個領域底下的知識（`null` ＝未歸屬）。 */
export function inDomain(items: KnowledgeItem[], id: number | null): KnowledgeItem[] {
  return items.filter((i) => (i.domain_id ?? null) === id)
}

export const KIND_ORDER: KnowledgeKind[] = ["source", "conversation", "why_node", "article"]
