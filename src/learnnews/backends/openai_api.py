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
        # 截斷過長輸入（新聞長文），省成本與延遲；分診相關性靠前段已足夠
        text = (text or " ")[:2000]
        data = _post(self.base_url, "/embeddings", self.api_key,
                     {"model": self.model, "input": text})
        vec = data["data"][0]["embedding"]
        self.dim = len(vec)
        return _l2_normalize([float(x) for x in vec])


class OpenAIArticleWriter:
    """走 OpenAI 格式 chat 生成可讀散文（spec 003）。忠實約束：只依原文、不捏造、不下結論。

    最終仍以程式端／抽查把關（experience 教訓 2）；長度不封頂，以完整傳達為準。
    """

    _SYSTEM = (
        "你是 AI 新聞/論文的消化助手。只用繁體中文，把一則材料寫成一篇**可讀的散文短文**"
        "（連貫段落，不要列點）。要求：\n"
        "1) 忠實傳達原文的重點、關鍵數據與適用時機；**原文沒有的數據絕對不要寫**。\n"
        "2) **不要下你自己的結論、評價或趨勢外推**——你在傳達原文，不是給觀點。\n"
        "3) 完整傳達重要訊息優先於長短，但不要為湊字數灌水。"
    )
    _USER = "標題：{title}\n原文前文/摘要：{abstract}\n讀者關注主題：{topic}\n\n請寫成散文短文。"

    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.model = model

    def write_article(self, title: str, abstract: str, matched_topic: str) -> str:
        data = _post(self.base_url, "/chat/completions", self.api_key, {
            "model": self.model,
            "max_tokens": 800,
            "temperature": 0.3,
            "messages": [
                {"role": "system", "content": self._SYSTEM},
                {"role": "user", "content": self._USER.format(
                    title=title, abstract=(abstract or "")[:2000], topic=matched_topic)},
            ],
        })
        return data["choices"][0]["message"]["content"].strip()


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
