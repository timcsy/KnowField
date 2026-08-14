"""OpenAI 格式 API 後端（chat completions ＋ embeddings）。

以 stdlib urllib 直接打 OpenAI 相容端點，零新增相依（呼應 experience：重量級相依
藏在可插拔介面後）。實作既有 `Embedder`／`Summarizer` 介面，可與離線 stub 互換。
相容 OpenAI 本身與任何 OpenAI 格式 gateway（自訂 base_url）。
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request

from ..ranking.embeddings import Vector, _l2_normalize

# 剝除模型可能吐出的鷹架前綴。標籤字（第一行/定位/…）只有在後面接分隔符時才算
# 鷹架而剝除——避免把內容裡本就以「定位」「為何值得看」開頭的正常句子誤刪。
_LABEL_RE = re.compile(
    r"^\s*"
    r"(?:[-•*]+\s*)?"                                              # 項目符號
    r"(?:\d+[.、)]\s*)?"                                           # 編號 1. / 1、
    r"(?:(?:第[一二]行|定位|為何值得看|why|positioning)\s*[＝=：:\-–、.]+\s*)?"  # 標籤＋必要分隔符
    r"(?:[＝=：]+\s*)?"                                            # 殘留的起首分隔符
)


def _clean_line(text: str) -> str:
    return _LABEL_RE.sub("", text).strip()


class OpenAIError(RuntimeError):
    pass


def _post(base_url: str, path: str, api_key: str, payload: dict, timeout: int = 60) -> dict:
    req = urllib.request.Request(
        f"{base_url}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise OpenAIError(f"API 錯誤 {e.code}：{body[:300]}") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise OpenAIError(f"API 連線失敗：{e}") from e


class OpenAIEmbedder:
    """OpenAI 格式 /embeddings。回傳 L2 正規化向量，與 HashingEmbedder 介面一致。"""

    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self.dim = 0  # 由第一次回應決定

    def embed(self, text: str) -> Vector:
        return self.embed_many([text])[0]

    def embed_many(self, texts: list[str]) -> list[Vector]:
        """一次 API 呼叫嵌入多筆（分批 ≤64），大幅省延遲——這是 web 即時拉的關鍵優化。"""
        out: list[Vector] = []
        for i in range(0, len(texts), 64):
            chunk = [((t or " ")[:2000]) for t in texts[i:i + 64]]
            data = _post(self.base_url, "/embeddings", self.api_key,
                         {"model": self.model, "input": chunk})
            for d in sorted(data["data"], key=lambda d: d.get("index", 0)):
                vec = [float(x) for x in d["embedding"]]
                self.dim = len(vec)
                out.append(_l2_normalize(vec))
        return out


class OpenAIArticleWriter:
    """走 OpenAI 格式 chat 生成可讀散文（spec 003）。忠實約束：只依原文、不捏造、不下結論。

    最終仍以程式端／抽查把關（experience 教訓 2）；長度不封頂，以完整傳達為準。
    """

    _SYSTEM = (
        "你是 AI 新聞/論文的消化助手。**只用{lang}**（無論原文是什麼語言，都翻譯／改寫成"
        "{lang}）。輸出格式：\n"
        "第一行：一個整理過、像新聞標題的精煉標題（{lang}，不要加「標題：」等字樣、不要引號）。\n"
        "空一行。\n"
        "接著：一篇可讀的散文短文（連貫段落，不要列點）。\n"
        "要求：\n"
        "1) 忠實傳達原文的重點、關鍵數據與適用時機；**原文沒有的數據絕對不要寫**。\n"
        "2) **不要下你自己的結論、評價或趨勢外推**——你在傳達原文，不是給觀點。\n"
        "3) 完整傳達重要訊息優先於長短，但不要為湊字數灌水。"
    )
    _USER = "原標題：{title}\n原文前文/摘要：{abstract}\n讀者關注主題：{topic}"

    def __init__(self, base_url: str, api_key: str, model: str,
                 lang: str = "繁體中文") -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self.lang = lang

    def write_article(self, title: str, abstract: str,
                      matched_topic: str) -> tuple[str, str]:
        data = _post(self.base_url, "/chat/completions", self.api_key, {
            "model": self.model,
            "max_tokens": 900,
            "temperature": 0.3,
            "messages": [
                {"role": "system", "content": self._SYSTEM.format(lang=self.lang)},
                {"role": "user", "content": self._USER.format(
                    title=title, abstract=(abstract or "")[:2000], topic=matched_topic)},
            ],
        })
        text = data["choices"][0]["message"]["content"].strip()
        # 第一段（到第一個空行）為標題，其餘為本體
        parts = text.split("\n", 1)
        headline = parts[0].strip().lstrip("#").strip() or title
        body = parts[1].strip() if len(parts) > 1 else text
        return headline, body


class OpenAISummarizer:
    """OpenAI 格式 /chat/completions。提示明令：只給定位與是否值得看，禁結論式分析。

    長度最終保證仍由 summarize/summarizer.py 的程式端守衛負責（不依賴模型自律）。
    """

    _SYSTEM = (
        "你是新聞分診助手。只用繁體中文，為使用者判斷一則內容值不值得點進去。"
        "嚴禁做任何結論式判斷、評價或深度分析——你的工作只是分診，不是代替使用者思考。"
    )
    _USER = (
        "直接輸出兩行純文字，不要加任何標籤、編號或引號：\n"
        "第一行：一句定位（這則在談什麼）。\n"
        "第二行：一句為何值得看。\n"
        "（只要內容本身，不要把「第一行」「定位」等字樣寫進去。）\n"
        "標題：{title}\n摘要：{abstract}\n關注主題：{topic}"
    )

    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.model = model

    def summarize(self, title: str, abstract: str, matched_topic: str) -> tuple[str, str]:
        data = _post(self.base_url, "/chat/completions", self.api_key, {
            "model": self.model,
            "max_tokens": 200,
            "temperature": 0.3,
            "messages": [
                {"role": "system", "content": self._SYSTEM},
                {"role": "user", "content": self._USER.format(
                    title=title, abstract=(abstract or "")[:1000], topic=matched_topic)},
            ],
        })
        text = data["choices"][0]["message"]["content"].strip()
        lines = [_clean_line(ln) for ln in text.splitlines() if _clean_line(ln)]
        positioning = lines[0] if lines else f"這則談的是「{title}」"
        why = lines[1] if len(lines) > 1 else "值得快速判斷"
        return positioning, why


class OpenAIAnswerer:
    """OpenAI 格式 /chat/completions 做 grounded 問答（spec 005 FR-003/004）。

    提示明令：只根據編號材料作答、逐點以 [n] 標依據、不得使用材料外知識或杜撰、
    材料不足即說「沒有相關材料」。溯源的鐵律不靠模型自律——來源清單由 RagService
    從檢索集合生成（research.md R4）；本後端只負責把材料轉成通順答案。
    """

    _SYSTEM = (
        "你是知識庫問答助手。只用{lang}作答。"
        "根據下列編號材料回答問題，每個論點以 [編號] 標出依據。"
        "**優先根據材料作答**；材料只**部分**相關時，就用相關的部分盡量回答（可說明侷限），"
        "不要因為問題廣泛就拒答。嚴禁使用材料以外的知識、嚴禁杜撰。"
        "**只有在材料與問題『完全無關』時**，才僅輸出一行：沒有相關材料"
    )
    _USER = "問題：{question}\n\n材料：\n{passages}"

    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.model = model

    def answer(self, question: str, passages: list, lang: str) -> str:
        block = "\n".join(
            f"[{i}] {(p.headline or p.title).strip()}：{(p.body or '')[:800]}"
            for i, p in enumerate(passages, 1)
        )
        data = _post(self.base_url, "/chat/completions", self.api_key, {
            "model": self.model,
            "max_tokens": 900,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": self._SYSTEM.format(lang=lang)},
                {"role": "user", "content": self._USER.format(
                    question=question, passages=block)},
            ],
        })
        return data["choices"][0]["message"]["content"].strip()


def _post_stream(base_url: str, path: str, api_key: str, payload: dict, timeout: int = 120):
    """串流版 chat：yield 逐段 token（OpenAI SSE delta），**return finish_reason**。

    回傳值（generator return，呼叫端用 `yield from` 就拿得到）＝最後一個 chunk 的 `finish_reason`；
    `"length"` ＝撞 max_tokens 被切。**不讀它就是靜默半句、看起來像好好講完了**（憲章 V 可觀測性）。
    迭代**整段**都在 try 內：中途斷線（IncompleteRead／reset／timeout）也統一成 OpenAIError——
    原本迭代在 try 外面，這類例外會裸奔穿出去（教訓：邊界要攔**所有**失敗，不只你想到的那種）。
    """
    body = {**payload, "stream": True}
    req = urllib.request.Request(
        f"{base_url}{path}", data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {api_key}"}, method="POST")
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
    except Exception as e:  # noqa: BLE001
        raise OpenAIError(f"對話串流失敗：{e}") from e
    saw_sse = False
    buf = b""
    finish = ""
    try:
        for raw in resp:
            line = raw.decode("utf-8", "ignore").strip()
            if line.startswith("data:"):
                saw_sse = True
                data = line[len("data:"):].strip()
                if data == "[DONE]":
                    break
                try:
                    choice = json.loads(data)["choices"][0]
                except Exception:  # noqa: BLE001 - 心跳/非內容行跳過
                    continue
                finish = choice.get("finish_reason") or finish   # 結束原因多半在最後一個 chunk
                delta = (choice.get("delta") or {}).get("content")
                if delta:
                    yield delta
            else:
                buf += raw          # 非 SSE：後端忽略了 stream，收整包稍後一次吐
    except Exception as e:  # noqa: BLE001 - 中途斷線也要收成友善的 OpenAIError（教訓 3）
        raise OpenAIError(f"對話串流中斷：{e}") from e
    if not saw_sse and buf.strip():   # 後端不支援串流 → 退回解析整包 completion（穩健）
        try:
            choice = json.loads(buf.decode("utf-8", "ignore"))["choices"][0]
            content = choice["message"]["content"]
            finish = choice.get("finish_reason") or finish
        except Exception as e:  # noqa: BLE001
            raise OpenAIError(f"對話回應無法解析：{e}") from e
        if content:
            yield content
    return finish


class OpenAIChatBackend:
    """OpenAI 格式 /chat/completions 多輪對話（spec 022）：直接吃 messages list。

    `poster`／`streamer` 可注入供測試。失敗統一成友善的 `OpenAIError`（教訓 3）。
    """

    def __init__(self, base_url: str, api_key: str, model: str, poster=_post,
                 streamer=_post_stream, max_tokens: int = 4096) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self._poster = poster
        self._streamer = streamer
        self.max_tokens = max_tokens   # 太小→長回答被截斷「到一半斷掉」；可由 env 調

    def _payload(self, messages: list) -> dict:
        return {"model": self.model, "max_tokens": self.max_tokens, "temperature": 0.4,
                "messages": messages}

    def reply(self, messages: list) -> str:
        try:
            data = self._poster(self.base_url, "/chat/completions", self.api_key,
                                self._payload(messages))
            return (data["choices"][0]["message"]["content"] or "").strip()
        except OpenAIError:
            raise
        except Exception as e:  # noqa: BLE001 - 邊界統一成友善 OpenAIError（教訓 3）
            raise OpenAIError(f"對話失敗：{e}") from e

    def stream(self, messages: list):
        """yield 逐段 token，**return finish_reason**（`"length"`＝撞上限被切，供上層標示截斷）。

        失敗拋 OpenAIError（由路由攔成 SSE error 事件）。
        """
        return (yield from self._streamer(self.base_url, "/chat/completions", self.api_key,
                                          self._payload(messages)))
