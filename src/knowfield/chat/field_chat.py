"""跟你的場聊天（spec 022）：多輪對話，AI 從你冊封的根因往下推、維持反逢迎的膜。

核心價值＝`build_field_system_prompt`（讀場＋膜＋分層＋grounding＋提候選）——這是第一風險
（自動版能否複刻手動品質）。串既有零件、核心零新相依：chat 走 `_post`（多輪 messages）。
對話短暫、不落庫；唯有人按「冊封」才寫既有 why_nodes（原則 5）。這是 principle 6 的體感版。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Protocol

from ..backends.openai_api import OpenAIChatBackend  # noqa: F401 - 供 web/測試自本模組匯入
from .capture import norm_claim

# --- 反逢迎的膜：system prompt（保留行為，輸出用自然口語、不用內部術語）---
_MEMBRANE = """你是使用者的思考夥伴——幫他把新東西接到他既有的理解上，而且「不順著他說好聽話」。
用繁體中文、自然口語。**不要用內部術語**（別說「冊封、場、根因、grounded、derived、場-增量」這類字），
也**不要在每段開頭貼「**grounded**」這種標籤**——用一般人看得懂的話。務必：
1. 先從下面「使用者已經想清楚、存下來的理解」往下接，連到他既有的想法，不要給對誰都一樣的通用答案。
2. 誠實區分把握程度，但用自然的話講：有紮實依據就直說；只是推測就講「這比較像我的推測」；沒把握或
   可能有誤就明講。別硬套標籤。
3. 分辨三種強度、別讓弱的冒充強的：**能證明/被邏輯逼出來的** vs **觀察到的規律（不一定必然）** vs
   **只是類比/比喻（別當定論）**——講清楚，尤其別讓比喻假裝成證明。
4. 華麗但沒有實際用處、也沒有預測或解釋力的說法，直說「這目前比較像漂亮的講法，還沒真的站住」，別當知識。
5. 遇到過頭的宣稱（如「唯一解、完全自洽、絕對」），點出並說明為什麼站不住，不要附和。
6. 有建設性、給實際幫助，不為反對而反對；使用者講得有道理就大方認同、修正自己。
7. 可以自然地點出：這接到他之前哪個想法、還缺什麼——用一兩句白話，別做成僵硬的段落。
8. 若有一條想法夠紮實、值得長期留著，可以**建議**他存起來，但只是建議；要不要存是他決定，你不能自己存。
分清資料的**三層份量**：**他精選的理解＝地基**（從這往下推）；**他收藏的文章/論文＝外部證言**
（可引用，但比理解軟、可能是他人觀點或有誤，別當成他的地基、別自動當成他的想法）；**web＝最外圈的外部資料**。
可用 Markdown（粗體、清單、$數學$）讓回答好讀。
**長度紀律**：預設精簡。先用 3–5 句給出核心答案，只有在使用者要求或問題真的需要時才展開細節。
不要為了展示上面每一條原則而把它們逐條演出來——那些是你的判準，不是要寫給使用者看的段落。"""

_SEARCH_Q = """使用者在對話中問了下面的內容。請給出**一個**最適合拿去 web 搜尋、能找到相關優質資料的
查詢字串：精簡、含關鍵術語，**必要時用英文或補上領域脈絡以消除歧義**（例如只寫「flow matching」會搜到
無關的「flow」，應補成「flow matching generative model」）。只輸出那一行查詢，不要引號、不要別的字。"""

_DISTILL = """把以下對話裡**值得長期留著的重點**整理出來——可能只有一條，也可能有好幾條，而且可能是
**不同認識論層次**。**看對話裡的證據強度**、誠實判每條的可信度，標成四類之一：
- 已證實：有推導或證據站得住
- 推論：從已知合理推出來的
- 類比：借別處的結構，對應還沒證
- 猜想：有方向、還沒驗證
分開列，每條用此格式（每條之間空一行）：
主張：<一句話的重點>
類型：<已證實 ｜ 推論 ｜ 類比 ｜ 猜想>
階梯：
- <為什麼，第一層>
- <再往下一層>
佐證：<相關網址，逗號分隔；沒有就留空>
出處：<這條主要來自對話的第幾則（看每則開頭的 [n]），如 3-6；只有一則就寫 5；不確定就留空>
只輸出這些區塊，不要別的話。"""



class ChatBackend(Protocol):
    def reply(self, messages: list[dict]) -> str: ...


class StubChatBackend:
    """離線確定性：回一段膜式回應，零外部呼叫。"""

    def reply(self, messages: list[dict]) -> str:
        last = next((m["content"] for m in reversed(messages)
                     if m.get("role") == "user"), "")
        return (
            f"（離線示意）就「{last[:40]}」——設定 LLM 金鑰後啟用真實的反逢迎對話。\n"
            "有依據的地方會直說、只是推測會講明；能證明／觀察到的規律／類比會分清楚。")

    def stream(self, messages: list[dict]):
        text = self.reply(messages)
        for i in range(0, len(text), 24):     # 分段模擬串流
            yield text[i:i + 24]


@dataclass
class CandidateDraft:
    claim: str = ""
    ladder: list[str] = field(default_factory=list)
    evidence_urls: list[str] = field(default_factory=list)
    kind: str = ""          # 認識論層次：已證實/推論/類比/猜想（vision 階段 28）
    already: bool = False    # 這條的主張已在理解裡（精選時標「已收過」、不重複收）
    src_from: int = 0        # 出處：對話第幾則（階段29第2階段，1-indexed；0=未知）
    src_to: int = 0


# bare 模式（暫時屏蔽知識庫）的場脈絡：明說這輪不接他的知識庫，人格照舊。
_BARE_NOTE = (
    "（這輪使用者暫時屏蔽了知識庫：**不參考他存的理解、不撒網、不查他收進的資料**，"
    "就當一般 AI 對話。但人格不變：不說好聽話、不把猜測講成事實、不確定就說不確定。這輪不附佐證 [n]。）")


def build_field_system_prompt(roots) -> str:
    """膜指令 ＋ 場脈絡注入（每條已冊封根因的 claim＋ladder）。roots 空 → 註明未接場。"""
    if not roots:
        ctx = ("（使用者的知識庫還空——還沒存任何理解。仍可一般聊，但要說明還沒接到他存的東西，"
               "並鼓勵他存幾條。）")
    else:
        lines = []
        for r in roots:
            k = getattr(r, "kind", "") or ""
            tag = f"［{k}］" if k else ""
            lines.append(f"◆ {tag}{r.claim}")
            for step in (r.ladder or []):
                lines.append(f"   ↳ {step}")
        ctx = ("使用者已經想清楚、存下來的理解（從這裡往下接；方括號是它的確定性層次——"
               "**類比／猜想別當定論用、要講明還沒站穩；已證實／推論才據以斷言**）：\n"
               + "\n".join(lines))
    return f"{_MEMBRANE}\n\n{ctx}"


def _parse_candidates(text: str) -> list[CandidateDraft]:
    """把蒸餾輸出解析成一到多條候選（每條「主張：」起一條，帶類型/階梯/佐證）。"""
    cands: list[CandidateDraft] = []
    cur: CandidateDraft | None = None
    in_ladder = False
    for raw in (text or "").splitlines():
        line = raw.strip()
        if line.startswith("主張："):
            claim = line[len("主張："):].strip()
            cur = CandidateDraft(claim=claim)
            # 同一次整理內去重：同正規化主張只留先出現的一條（避免收進同一條兩則）
            if any(norm_claim(c.claim) == norm_claim(claim) for c in cands):
                cur = CandidateDraft(claim=claim)   # 仍設 cur 吸收後續行，但不入清單
            else:
                cands.append(cur)
            in_ladder = False
        elif cur is None:
            continue
        elif line.startswith("類型："):
            cur.kind = line[len("類型："):].strip()
            in_ladder = False
        elif line.startswith("階梯："):
            in_ladder = True
        elif line.startswith("佐證："):
            in_ladder = False
            for u in line[len("佐證："):].replace("，", ",").split(","):
                u = u.strip()
                if u.startswith("http"):
                    cur.evidence_urls.append(u)
        elif line.startswith("出處："):
            in_ladder = False
            nums = re.findall(r"\d+", line[len("出處："):])   # 階段29第2階段：出處則數範圍
            if nums:
                cur.src_from = int(nums[0])
                cur.src_to = int(nums[-1])
        elif in_ladder and line.startswith("-"):
            item = line.lstrip("-").strip()
            if item:
                cur.ladder.append(item)
    if not cands:   # 離線/未依格式 → 退回首行非空當一條（不崩）
        first = next((l.strip() for l in (text or "").splitlines() if l.strip()), "")
        if first:
            cands.append(CandidateDraft(claim=first))
    return cands


_SEGMENT = (
    "把這段對話切成幾個章節（依主題轉折，通常 2–6 章）。每章一行，格式：\n"
    "章：<小標>｜<起始訊息序號，從 1 起>｜<一句摘要>\n"
    "起始序號＝該章第一則訊息在整段對話中的序（第 1 則為 1）。只輸出這些行，不要別的字。")


def _parse_chapters(text: str) -> list[dict]:
    """把切分輸出解析成 [{title, start, summary}]（每行『章：小標｜起｜摘要』）。"""
    out: list[dict] = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line.startswith("章："):
            continue
        body = line[len("章："):]
        parts = [p.strip() for p in body.split("｜")]
        if len(parts) < 2:
            continue
        try:
            start = int(parts[1])
        except (TypeError, ValueError):
            continue
        out.append({"title": parts[0], "start": start,
                    "summary": parts[2] if len(parts) > 2 else ""})
    return out


class FieldChat:
    """編排：組 messages（system 場脈絡＋歷史＋user）→ chat_backend；蒸餾冊封候選。"""

    def __init__(self, chat_backend: ChatBackend) -> None:
        self.backend = chat_backend

    _ARTICLE_CAP = 6000        # 長文不得吃掉整個脈絡預算（同 sources 的 cap 精神）

    def _messages(self, history, user_msg, roots, sources, bare, max_history,
                  url_contents=None, article=None, source=None):
        hist = list(history)
        if max_history > 0:
            hist = hist[-max_history:]
        # bare＝這輪暫時屏蔽知識庫：不注入理解、也不會有 sources；但保留反逢迎人格（膜）。
        sys_prompt = f"{_MEMBRANE}\n\n{_BARE_NOTE}" if bare else build_field_system_prompt(roots)
        messages = [{"role": "system", "content": sys_prompt}]
        messages += hist
        # spec 041：使用者明確帶進來的一篇**生成文章**。它自成一層，而且是**最軟**的一層——
        # roots＝他冊封的地基、sources＝外部證言、文章＝**從地基長出來的自家衍生物**。
        # ⚠️ 混層的話，AI 會拿自己的產物回敬使用者、冒充成他的想法（反逢迎要擋的）。
        # ⚠️ 結構保證（FR-003）：文章只出現在**這裡組裝的臨時訊息**裡，**絕不寫回 history**
        # ——而 distill()（蒸餾冊封候選）的輸入只由 history 串成，所以它結構上看不到文章。
        # 這條保證的邊界：助理若在回覆裡引用文章，那段會進 history（見 spec 041 FR-003 的說明）。
        if article and not bare:
            body = (article.get("markdown") or "")[:self._ARTICLE_CAP]
            messages.append({"role": "system", "content": (
                "使用者帶了一份**他自己知識庫生成的應用**進來，因為他讀完之後想接著想。\n"
                "**這是 AI 依他冊封的理解生成的衍生物**——比理解軟、也比他收藏的外部來源軟：\n"
                "・它**不是**新證據，只是把既有理解重新排過；引用它時要說「你那份裡…」。\n"
                "・**與理解衝突時以理解為準**，不要用它來蓋過他的地基。\n"
                "・他要的多半是**接著想**，不是要你改這一份——除非他明講。\n"
                f"【{article.get('title') or '（無標題）'}】\n{body}")})

        # spec 042：使用者明確帶進來的**一份收進的來源**。它與文章是不同層——
        # 來源是**他挑進來的一手素材**（可能是他人觀點、也可能有誤，但不是 AI 產物），
        # 文章則是自家衍生物。⚠️ 這一層**比理解軟、比文章硬**。
        # ⚠️ FR-010：spec 041 對文章那道「冊封候選不得由它生成」的閘門**不套用在這裡**
        # ——那道閘門擋的是 model collapse，前提是文章為 AI 產物；來源不是，
        # 而且從來源冊封（/api/source/distill）本來就是既有的合法功能。
        # 這裡不寫回 history 純粹是脈絡衛生（同 article 的形狀），不是閘門。
        if source and not bare:
            note = ""
            if source.get("excerpted"):
                note = (f"（本份共 {source.get('total_units')} 段，此處是開頭 ＋ 與問題最相關的"
                        f" {source.get('shown_units')} 段；沒給你的段落**不代表它沒寫**，"
                        f"不確定時請說「這份我只看到部分」。）\n")
            messages.append({"role": "system", "content": (
                "使用者帶了**一份他收進的來源**進來，因為他想針對這一份談。\n"
                "・這是**外部證言**，不是他的地基：引用時說「你收的這份說…」，"
                "**與理解衝突時以理解為準**。\n"
                "・⚠️ 他在頁面上看到的可能是**繁體化或翻譯後**的版本，"
                "以下給你的是**原文**——他引用某句時，必要時替他做原文↔他看到的版本的對應，"
                "也可以指出翻譯失真的地方。\n"
                f"{note}"
                f"【{source.get('title') or '（無標題）'}】（{source.get('url') or ''}）\n"
                f"{source.get('body') or ''}")})

        if url_contents:   # 使用者貼的網址，已抓到的內容（教訓 3：抓不到就給 note，不假裝讀過）
            blocks = []
            for c in url_contents:
                if c.get("body"):
                    blocks.append(f"【{c.get('title') or c.get('url')}】（{c.get('url')}）\n"
                                  f"{c['body'][:3000]}")
                else:
                    blocks.append(f"（{c.get('url')}：抓不到內容，可能被擋或需登入——請據實說你讀不到、"
                                  f"請使用者貼標題/摘要，不要假裝讀過。）")
            messages.append({"role": "system", "content": (
                "使用者在訊息裡貼了網址。以下是伺服器端抓到的內容（只依這些，不要杜撰網頁沒有的細節）：\n"
                + "\n\n".join(blocks))})
        if sources:
            lines = []
            for i, s in enumerate(sources, 1):
                kind = getattr(s, "kind", "web")
                title = (getattr(s, "title", "") or "").strip()
                text = (getattr(s, "snippet", "") or "")
                cap = 400 if kind == "corpus" else 160
                label = "你收藏的" if kind == "corpus" else "web"
                lines.append(f"[{i}]（{label}）{title}：{text[:cap]}（{getattr(s, 'url', '')}）")
            messages.append({"role": "system", "content": (
                "以下是為這個問題找到的參考資料，分兩類——**分層看待**：\n"
                "・**你收藏的**＝使用者以前收進的文章/論文，是**外部證言**：可以引用，但**比他精選的理解軟**"
                "（可能是他人觀點、也可能有誤）；**別當成他的地基、別替他把它說成就是他的想法**，"
                "要說「你收的資料說…」。\n"
                "・**web**＝剛撒網找到的外部資料。\n"
                "**若你某句話正好被某條支持，就在那句句尾標 [n]**（可多個如 [1][2]）；沒被支持的不要標，"
                f"也**不要杜撰**來源或內容。用不到的忽略。\n" + "\n".join(lines))})
        messages.append({"role": "user", "content": user_msg})
        return messages

    def reply(self, history: list[dict], user_msg: str, roots, sources=None,
              bare: bool = False, max_history: int = 0, url_contents=None,
              article=None, source=None) -> str:
        """一輪對話。sources 非空時句尾標 [n]；url_contents＝使用者貼的網址抓到的內容。
        bare=True＝這輪暫時屏蔽知識庫（不注入理解、不撒網）。"""
        return self.backend.reply(
            self._messages(history, user_msg, roots, sources, bare, max_history,
                           url_contents, article, source))

    def reply_stream(self, history: list[dict], user_msg: str, roots, sources=None,
                     bare: bool = False, max_history: int = 0, url_contents=None,
                     article=None, source=None):
        """串流版 reply：yield 逐段 token，**return finish_reason**（`"length"`＝被上限切）。

        bare=True＝這輪暫時屏蔽知識庫。截斷原因原樣穿過去，讓路由層標給使用者看（憲章 V）。
        """
        return (yield from self.backend.stream(
            self._messages(history, user_msg, roots, sources, bare, max_history,
                           url_contents, article, source)))

    def title(self, messages: list[dict]) -> str:
        """為一段對話生一句反映**落點/全貌**的標題（≤20 字）。取材首尾並取（spec 027，
        修正舊版只看開頭 convo[:2000]＝標題凍在第一句）。失敗→退回首個 user 訊息截斷（教訓 3）。"""
        from .capture import title_material
        first = next((m.get("content", "") for m in messages
                      if m.get("role") == "user"), "")
        convo = title_material(messages)
        try:
            t = self.backend.reply([
                {"role": "system", "content":
                 "用一句話（不超過 20 字）描述這段對話**最後得出／聊到什麼（落點）與整體在講什麼**，"
                 "當標題——若中途換了主題，以**最後聊到的**為主，不要只抓開頭。"
                 "只輸出標題，不要引號或別的字。"},
                {"role": "user", "content": convo}])
            t = (t or "").strip().splitlines()[0].strip().strip('"「」') if t else ""
        except Exception:  # noqa: BLE001 - 標題失敗不該讓「存對話」崩
            t = ""
        return t or (first.strip()[:20] if first.strip() else "（未命名對話）")

    def search_query(self, history: list[dict], user_msg: str) -> str:
        """把使用者這輪的問題轉成好的 web 搜尋 query（消歧義）。失敗/空→退回原句。"""
        ctx = ""
        for m in list(history)[-2:]:
            ctx += f"{m.get('role')}：{m.get('content')}\n"
        try:
            q = self.backend.reply([{"role": "system", "content": _SEARCH_Q},
                                    {"role": "user", "content": f"{ctx}使用者：{user_msg}"}])
            q = (q or "").strip().splitlines()[0].strip().strip('"「」') if q else ""
        except Exception:  # noqa: BLE001 - query 抽取失敗退回原句，不拖垮對話
            q = ""
        return q or user_msg

    def segment(self, messages: list[dict]) -> list[dict]:
        """把一段對話切成章節（spec 027）：LLM 判轉折→解析→正規化（涵蓋不重疊）。
        過短/失敗→整段一章（教訓 3）。回 [{title, start, end, summary}]。不落庫。"""
        from .capture import normalize_chapters
        n = len(messages or [])
        if n <= 2:                                   # 太短→整段一章
            return normalize_chapters([], n)
        # 逐則短摘要（每則截 80 字）讓模型看到**全貌**，而非 convo[:N] 截頭只看開頭（真後端照出的坑）
        convo = "\n".join(f"{i}. {m.get('role')}：{(m.get('content') or '')[:80]}"
                          for i, m in enumerate(messages, 1))[:16000]
        try:
            raw = _parse_chapters(self.backend.reply(
                [{"role": "system", "content": _SEGMENT},
                 {"role": "user", "content": convo}]))
        except Exception:  # noqa: BLE001 - 切分失敗不該炸
            raw = []
        return normalize_chapters(raw, n)

    def distill(self, history: list[dict], roots) -> list[CandidateDraft]:
        """蒸餾出一到多條值得留的重點（可能不同層次）。已在理解（roots）的標 already。"""
        convo = "\n".join(f"[{i + 1}] {m.get('role')}：{m.get('content')}"
                          for i, m in enumerate(history))   # 帶則號→AI 標出處（階段29第2階段）
        messages = [{"role": "system", "content": _DISTILL},
                    {"role": "user", "content": convo}]
        cands = _parse_candidates(self.backend.reply(messages))
        # 標「已收過」：主張正規化後已在既有 roots 裡→精選時擋掉、不重複收（原則 6 反囤積）
        anointed = {norm_claim(getattr(r, "claim", "")) for r in (roots or [])}
        for c in cands:
            if norm_claim(c.claim) in anointed:
                c.already = True
        return cands
