// spec 046：一段對話裡「哪幾則已經冊封過」。
//
// ⚠️ **用集合，不是水位線。** 實測正式庫的覆蓋是**不連續**的：
//   對話 44：9 條冊封、共 46 則、已覆蓋 40，缺 [3,4,5,6,7,8]
//   對話 31：5 條冊封、共 24 則、已覆蓋 18，缺 [1,2,9,10,11,12]
// 水位線（`1..max(to)`）會說「收到第 46 則」，**而中間的洞就此看不見**
// ——那正是使用者要找的東西（「哪些還沒收」）。
export type Range = { from: number; to: number }

/** 回「已冊封的則數」集合（1-based）。範圍非法（<=0 或 from>to）一律忽略，不報錯。 */
export function coveredSet(ranges: Range[], total: number): Set<number> {
  const s = new Set<number>()
  for (const r of ranges) {
    if (!r || r.from <= 0 || r.to <= 0 || r.from > r.to) continue   // 舊資料 0/0、或髒資料
    for (let i = r.from; i <= Math.min(r.to, total); i++) s.add(i)  // 超出訊息數→取交集
  }
  return s
}

/** 摘要：共幾則、已收幾則、還沒收幾則。⚠️ 不講水位線（見上）。 */
export function coverageSummary(ranges: Range[], total: number) {
  const covered = coveredSet(ranges, total)
  return { total, covered: covered.size, uncovered: total - covered.size }
}
