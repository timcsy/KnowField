# Research：場驅動來源推薦

無 NEEDS CLARIFICATION——全複用既有零件。記關鍵抉擇。

## D1：候選「訂閱」如何不重抓 feed
- **決策**：候選訂閱表單 POST 既有 `/sources/add`，`url=feed_url`。
- **理由**：`discover_feed` 對已是 feed 的 url 會 `_looks_like_feed` 短路直接回它——不重抓 HTML；
  `subscribe()` 再驗一次確保落庫前有料（教訓 7）。**零新訂閱路由、與手動加來源同一守門。**
- **否決**：新開 `/sources/subscribe-candidate` 直接塞 Source——繞過既有驗證，重複邏輯，棄。

## D2：死/幻覺 feed vs 無 feed 的候選怎麼處理
- **決策**：**探到 feed 但驗證失敗/空＝死/幻覺→丟棄**（FR-002）；**完全探不到 feed＝保留、標
  「無 RSS」、不可訂**（FR-010，誠實天花板）。
- **理由**：兩者語意不同——死 feed 是雜訊（該擋），無 feed 的好站是「訂不了但值得知道」（該誠實
  標示、靠 web 活水/收進補）。單一 `has_feed` 旗標區分，UI 據此決定有無「訂閱」鈕。
- **否決**：一律只留有 feed 的——會靜默吞掉「沒 RSS 的好站」，違 FR-010 誠實天花板。

## D3：場驅動分數怎麼算（複用，不新建）
- **決策**：`field_score`＝候選文字（name＋snippet）嵌入對 `list_field_attractors()`（種子＋冊封根因）
  的 **cosine 最大值**——與 `FieldRelate` 找最近吸引子同一手法（spec 018）。
- **理由**：直接複用 `make_embedder`＋`ensure_embeddings`＋`cosine`；「你冊封的材料出自它」用語意
  相近近似（候選來源描述 vs 你的場）。無 attractor → 全 0，排序退回「有活 feed ＞ 跨清單重複」。
- **否決**：精確比對候選網域 vs 種子 url 的網域——太脆（同站不同子網域/轉貼）、覆蓋低；嵌入相近更穩。

## D4：排序訊號合成
- **決策**：排序 key＝`(field_score, has_feed, list_hits)` 由大到小（tuple 比較，場驅動最重）。
- **理由**：使用者定案「你冊封材料出自它 ＞ 有活 feed ＞ 跨清單重複」直接映射 tuple 優先序。
- **否決**：加權線性合成單一分數——需調權重、不透明；tuple 詞典序簡單且符合定案的嚴格優先。

## D5：opt-in / 按需
- **決策**：只有 `POST /sources/recommend`（人按鈕）觸發；**不**接進 digest 管線、不背景輪詢。
- **理由**：搜尋額度成本＋原則 5＋北極星「深淺分明」。與增量 b「按需」一致。
