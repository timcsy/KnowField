# 041：根因萃取品質補強——挖到 bedrock ＋ why 階梯

> 日期：2026-07-25　｜　承接 history/040（階段 10 完成）

## 緣起（使用者回饋）
使用者抽了幾則根因後回饋：「**本質層面的 why 太少，都是表面的 why**；我想要底層邏輯、
有 **aha** 的點」。＝萃取**停在第一個 why 就收手**，沒過試金石第 6 條（追問不撞牆）。

## 為何是 concept 早預言的失敗
- 試金石 6（concept :73）：淺解釋很快 bottom out 在霧詞；深解釋落到**原始層**（數學必然／
  資源限制／資訊理論極限）。
- 試金石 4/5＝aha（:70-71）：一個原理讓表面事實同時 click、能重新推導。
- 舊萃取提示只叫 AI 給「機制層根因」、**把試金石當檢查表列著**，沒把「遞迴追到 bedrock」
  設成任務本身 → AI 給過得去的表面 why 就交卷。

## 修正（不動架構，強化萃取＋可視化深度）
- **提示改寫**（`OpenAIExtractor._SYSTEM`）：目標改成「**挖到 bedrock、逼出 aha**」；方法＝
  **遞迴追問**「那這個又為什麼？」直到撞原始層，**不到原始層不准停**；看到霧詞＝還沒到底、
  **再挖一層**（不是只標旗標）；`claim`＝最底層 aha；挖不到就 `no_material=true`（誠實勝過假深洞見）。
- **新增 why 階梯 `ladder`**（表面→bedrock，每層一句）：`Candidate`/`WhyNode` 加欄、`why_nodes`
  加 `ladder` 欄（SCHEMA＋_migrate ALTER 冪等）、`/roots` 候選卡顯示階梯（末層標「bedrock」）
  ——**看得到它挖了幾層**，一眼分辨深淺。
- **階梯進檢索**：已冊封 why-node 的 corpus body 併入階梯，問底層邏輯也撈得到。

## 誠實的天花板（未做，留後續）
單一種子若本身留一手（concept :53），bedrock 可能不在材料裡——真要每次到底得靠**跨來源
三角測量＋解說文**（concept 早列，仍 out-of-scope）。單篇萃取有天花板；本次先把單篇能挖的
深度拉滿。

## 產物
- `rootcause/extract.py`（提示改寫＋`ladder` 欄＋stub 階梯＋解析）、`store/schema.py`（ladder 欄＋
  migrate）、`store/repository.py`（存讀 ladder＋corpus body 併階梯）、`web/app.py`（傳 ladder）、
  `templates/roots.html`（階梯顯示）。
- 測試：`test_rootcause`（stub/openai ladder）＋`test_why_nodes_repo`（round-trip＋corpus）；234 綠。
- commit：見本次。
