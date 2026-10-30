"""纯 Python 中文检索索引（离线演示模式的知识库内核）。

不依赖模型与向量数据库：
1. 扫描 ``ragagent/data`` 下的 txt/pdf；
2. 按段落切成约 240 字的片段；
3. 用「中文字符二元组 + 英文/数字词」建倒排索引，BM25 打分。

对 ~150KB 的知识库，构建 + 查询都在毫秒级，因此不需要任何外部服务。
"""

from __future__ import annotations

import hashlib
import math
import re
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

CHUNK_SIZE = 240

_CJK_RE = re.compile(r"[\u4e00-\u9fff]+")
_LATIN_RE = re.compile(r"[a-zA-Z0-9]+")

try:  # 可选依赖：装了 jieba 就用词级分词，精度更高
    import logging
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        import jieba
        import jieba.posseg as _posseg

        jieba.setLogLevel(logging.WARNING)
    _HAS_JIEBA = True
except ImportError:  # pragma: no cover - 走二元组回退
    _HAS_JIEBA = False
    _posseg = None  # type: ignore[assignment]

_STOPWORDS = {
    "的", "了", "吗", "呢", "吧", "啊", "呀", "哦", "嗯", "我", "你", "他", "她", "它",
    "是", "有", "在", "和", "与", "就", "都", "也", "还", "很", "太", "这", "那", "些",
    "一个", "什么", "怎么", "怎样", "如何", "为什么", "哪些", "哪个", "多少", "请问",
    "一下", "需要", "可以", "是否", "应该", "能不能", "有没有", "这个", "那个", "以及",
}

#: 只用于**查询侧**的框架词：它们描述"提问方式/结果状态"，不指向主题。
#: 例如「回充失败」里的"失败"会把无关的"固件升级失败"顶上来。
_QUERY_STOPWORDS = {
    "失败", "问题", "原因", "方法", "情况", "总是", "一直", "突然", "出现", "发生",
    "处理", "解决", "办法", "建议", "注意", "一般", "正常", "时候",
}


def tokenize(text: str) -> list[str]:
    """中英文混合分词：jieba 词级切分（缺失时退化为二元组）。"""
    text = text.lower()
    tokens: list[str] = [m.group(0) for m in _LATIN_RE.finditer(text)]

    if _HAS_JIEBA:
        for word in jieba.lcut(text):
            word = word.strip()
            if not word or word in _STOPWORDS:
                continue
            if _CJK_RE.fullmatch(word):
                if len(word) < 2:
                    continue
                tokens.append(word)
                # 词 + 二元组混合：缓解 jieba 把"有水痕"合成一个词导致的漏召回
                if len(word) >= 3:
                    tokens.extend(word[i : i + 2] for i in range(len(word) - 1))
            elif word.isalnum():
                tokens.append(word)
        return tokens

    for run in _CJK_RE.findall(text):
        if len(run) <= 2:
            tokens.append(run)
            continue
        tokens.extend(run[i : i + 2] for i in range(len(run) - 1))
        if len(run) <= 6:
            tokens.append(run)
    return tokens


@dataclass
class Chunk:
    id: str
    source: str
    title: str
    text: str
    order: int
    terms: Counter[str] = field(default_factory=Counter, repr=False)
    length: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source": self.source,
            "title": self.title,
            "order": self.order,
            "chars": len(self.text),
            "preview": preview(self.text, 120),
        }


@dataclass
class Hit:
    chunk: Chunk
    score: float
    rank: int

    def to_dict(self, width: int = 200) -> dict[str, Any]:
        return {
            "id": self.chunk.id,
            "source": self.chunk.source.strip(),
            "title": chunk_title(self.chunk.text) or self.chunk.title,
            "score": round(self.score, 3),
            "rank": self.rank,
            "snippet": preview(self.chunk.text, width),
            "text": self.chunk.text,
        }


_NAV_HEADING_RE = re.compile(r"^[一二三四五六七八九十]+[、.．]")


def preview(text: str, width: int = 180) -> str:
    kept: list[str] = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or _NAV_HEADING_RE.match(line):
            continue
        kept.append(line)
    flat = " ".join(kept).replace("**", "").replace("`", "")
    flat = re.sub(r"\s+", " ", flat).strip()
    return flat if len(flat) <= width else flat[: width - 1] + "…"


def chunk_title(text: str) -> str:
    """取片段里真正的问答标题（跳过 ``### 章节``、``四、分类`` 这类导航行）。"""
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#") or _NAV_HEADING_RE.match(line):
            continue
        cleaned = re.sub(r"^\d{1,3}\s*[.、)）]\s*", "", line).replace("**", "").strip()
        if len(cleaned) >= 4:
            return cleaned[:60]
    return ""


def _read_text(path: Path) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return path.read_text(encoding=encoding)
        except (UnicodeDecodeError, OSError):
            continue
    return ""


def _pdf_text(path: Path) -> tuple[str, str]:
    """返回 (文本, 不可用原因)。"""
    try:
        from pypdf import PdfReader
    except ImportError:
        return "", "未安装 pypdf，无法解析 PDF"

    try:
        reader = PdfReader(str(path))
        pages = [(page.extract_text() or "") for page in reader.pages]
    except Exception as exc:  # pragma: no cover - 依赖具体 PDF
        return "", f"PDF 解析失败：{exc}"

    text = "\n".join(pages).strip()
    if not text:
        return "", "PDF 无可提取文本"
    cjk = len(_CJK_RE.findall(text))
    if cjk < len(text) * 0.05:
        # 该 PDF 内嵌字体缺少中文 ToUnicode 映射，抽取结果全是乱码/空字符
        return "", "PDF 字体缺少中文编码映射，无法提取正文（工程内已附同名 txt，将使用 txt）"
    return text, ""


_ITEM_NUMBER_RE = re.compile(r"^\s*\d{1,3}\s*[.、)）]")
_HEADING_RE = re.compile(r"^\s*#{1,6}\s")


def _starts_new_item(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if _ITEM_NUMBER_RE.match(stripped):
        return True
    # PDF 里"问题？"单独成行、答案在下一行
    return len(stripped) <= 60 and stripped.endswith(("？", "?"))


def split_text(text: str) -> list[str]:
    """按「问答条目」切块，保证一个片段只包含一条问答。

    语料是条目化的（``1. **问题？**`` + ``- 回答``），因此以行首编号 / 标题 /
    疑问句作为条目边界：遇到新条目就落盘，标题行挂到下一条目上。
    """
    normalized = (
        text.replace("\u3000", " ")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\ufeff", "")
    )
    chunks: list[str] = []
    buffer = ""
    pending_headings: list[str] = []

    def flush() -> None:
        nonlocal buffer
        if buffer.strip():
            chunks.append(buffer.strip())
        buffer = ""

    for raw_line in normalized.split("\n"):
        line = raw_line.strip()
        if not line:
            flush()
            pending_headings = []
            continue

        if _HEADING_RE.match(line):
            flush()
            pending_headings.append(line)
            continue

        if _starts_new_item(line):
            flush()
            prefix = "\n".join(pending_headings)
            pending_headings = []
            buffer = f"{prefix}\n{line}" if prefix else line
            continue

        if buffer and len(buffer) + len(line) + 1 > CHUNK_SIZE:
            flush()
        buffer = f"{buffer}\n{line}" if buffer else line

    flush()
    return [chunk for chunk in chunks if _is_content_chunk(chunk)]


def _is_content_chunk(chunk: str) -> bool:
    """过滤纯标题行（如文件首行「…故障检测与修复200条」），保留真实条目。"""
    if len(chunk.strip()) < 4:
        return False
    if "\n" in chunk:
        return True
    flat = re.sub(r"^\d{1,3}\s*[.、)）]\s*", "", chunk.strip())
    if len(flat) > 40:
        return True
    return any(mark in flat for mark in "：:；;？?")


def _noun_or_verb_tokens(text: str) -> set[str]:
    """取名词/动词，作为「主题词」候选（排除"耐用""怎么办"这类修饰/疑问词）。"""
    if not _HAS_JIEBA or _posseg is None:
        return set()
    out: set[str] = set()
    for word, flag in _posseg.cut(text):
        word = word.strip()
        if len(word) < 2 or not _CJK_RE.fullmatch(word):
            continue
        if flag and flag[0] in {"n", "v"}:
            out.add(word)
    return out


class LocalSearchIndex:
    """基于 BM25 的本地检索索引。"""

    K1 = 1.5
    B = 0.75
    #: 稀有词放大指数：把区分度高的词（回充/滤网/水痕）权重抬起来
    IDF_POWER = 1.5
    #: 未命中「主题词」的片段降权系数
    SUBJECT_PENALTY = 0.25

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.chunks: list[Chunk] = []
        self._docs: list[dict[str, Any]] = []
        self._idf: dict[str, float] = {}
        self._avgdl = 1.0
        self.built_at: str | None = None
        self.build_ms: float = 0.0

    # ------------------------------------------------------------------ #
    # 构建
    # ------------------------------------------------------------------ #
    def build(self) -> None:
        started = time.perf_counter()
        self.chunks = []
        self._docs = []

        if self.data_dir.is_dir():
            for path in sorted(self.data_dir.iterdir(), key=lambda p: p.name):
                if not path.is_file():
                    continue
                suffix = path.suffix.lower()
                if suffix not in {".txt", ".pdf"}:
                    continue
                self._docs.append(self._ingest(path, suffix))

        self._finalize()
        self.built_at = time.strftime("%Y-%m-%d %H:%M:%S")
        self.build_ms = round((time.perf_counter() - started) * 1000, 2)

    def _ingest(self, path: Path, suffix: str) -> dict[str, Any]:
        raw_size = path.stat().st_size
        md5 = hashlib.md5(path.read_bytes()).hexdigest()
        reason = ""
        if suffix == ".txt":
            text = _read_text(path)
            if not text.strip():
                reason = "文件为空或编码无法识别"
        else:
            text, reason = _pdf_text(path)

        chunks: list[Chunk] = []
        if text.strip() and not reason:
            title, body = _strip_doc_title(text, path.stem)
            for order, piece in enumerate(split_text(body)):
                if len(piece.strip()) < 4:
                    continue
                chunks.append(
                    Chunk(
                        id=f"{path.stem}#{order:03d}",
                        source=path.name,
                        title=title,
                        text=piece.strip(),
                        order=order,
                    )
                )

        self.chunks.extend(chunks)
        return {
            "name": path.name,
            "type": suffix.lstrip("."),
            "size": raw_size,
            "md5": md5,
            "chunks": len(chunks),
            "chars": sum(len(c.text) for c in chunks),
            "ok": bool(chunks),
            "reason": reason or ("" if chunks else "未切分出有效片段"),
            "title": _guess_title(text, path.stem) if text.strip() else path.stem,
        }

    def _finalize(self) -> None:
        df: Counter[str] = Counter()
        total_length = 0
        for chunk in self.chunks:
            terms = Counter(tokenize(chunk.text))
            chunk.terms = terms
            chunk.length = sum(terms.values()) or 1
            total_length += chunk.length
            df.update(set(terms))

        count = len(self.chunks) or 1
        self._avgdl = total_length / count if self.chunks else 1.0
        self._idf = {
            term: math.log(1 + (count - freq + 0.5) / (freq + 0.5)) for term, freq in df.items()
        }

    # ------------------------------------------------------------------ #
    # 查询
    # ------------------------------------------------------------------ #
    def search(self, query: str, k: int = 3) -> list[Hit]:
        ordered_terms = list(dict.fromkeys(term for term in tokenize(query) if term))
        # 只保留语料中真实出现过的词：像"总是""半路"这种词无法区分片段，
        # 却会稀释覆盖度权重，反而把正确答案挤下去。
        ordered_terms = [term for term in ordered_terms if term in self._idf]
        # 去掉"失败/问题/总是"这类框架词，它们不指向主题
        ordered_terms = [term for term in ordered_terms if term not in _QUERY_STOPWORDS]
        query_terms = set(ordered_terms)
        if not query_terms or not self.chunks:
            return []

        idf_map = {term: self._idf[term] for term in query_terms}
        # 用 idf 的幂次衡量词的区分度，稀有词（回充/滤网/水痕）压过高频词（机器人/怎么办）；
        # 再叠加位置权重：中文提问通常"主题在前"。
        span = max(1, len(ordered_terms) - 1)
        position = {
            term: 1.0 + 0.3 * (span - index) / span for index, term in enumerate(ordered_terms)
        }
        weights = {
            term: (value**self.IDF_POWER) * position[term] for term, value in idf_map.items()
        }
        total_weight = sum(weights.values()) or 1.0

        # 主题词 = 区分度最高的名词/动词（回充、滤网、迷路、电池），
        # 排除"耐用""怎么办"这类修饰/疑问词。
        theme = (_noun_or_verb_tokens(query) & query_terms) or query_terms
        subject = max(theme, key=lambda term: idf_map[term])

        scored: list[tuple[float, Chunk]] = []
        for chunk in self.chunks:
            raw = 0.0
            matched_weight = 0.0
            norm = self.K1 * (1 - self.B + self.B * chunk.length / self._avgdl)
            for term, weight in weights.items():
                freq = chunk.terms.get(term)
                if not freq:
                    continue
                matched_weight += weight
                raw += weight * (freq * (self.K1 + 1)) / (freq + norm)
                if term in chunk.title or term in chunk.source:
                    raw += weight * 0.35
            if raw <= 0:
                continue
            # 覆盖度加权：只命中"机器人""怎么办"这类高频词的片段会被显著降权
            coverage = matched_weight / total_weight
            score = raw * (0.25 + 0.75 * coverage)
            if subject and subject not in chunk.terms:
                score *= self.SUBJECT_PENALTY
            scored.append((score, chunk))

        scored.sort(key=lambda item: item[0], reverse=True)
        top = scored[: max(1, min(k, 10))]
        if not top:
            return []
        best = top[0][0]
        return [
            Hit(chunk=chunk, score=round(score / best, 3), rank=index + 1)
            for index, (score, chunk) in enumerate(top)
        ]

    # ------------------------------------------------------------------ #
    # 元信息
    # ------------------------------------------------------------------ #
    def documents(self) -> list[dict[str, Any]]:
        return list(self._docs)

    def stats(self) -> dict[str, Any]:
        ok_docs = [doc for doc in self._docs if doc["ok"]]
        return {
            "documents": len(self._docs),
            "indexed_documents": len(ok_docs),
            "chunks": len(self.chunks),
            "vocab": len(self._idf),
            "avg_chunk_terms": round(self._avgdl, 1),
            "built_at": self.built_at,
            "build_ms": self.build_ms,
            "data_dir": str(self.data_dir),
        }


def _strip_doc_title(text: str, fallback: str) -> tuple[str, str]:
    """首行是文档标题（如「扫地机器人100问」），从正文中剥离并作为文档 title。"""
    lines = text.splitlines()
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        title = re.sub(r"^#{1,6}\s*", "", stripped).strip()
        body = "\n".join(lines[index + 1 :])
        if not body.strip():
            return (title or fallback), text
        return (title[:80] or fallback), body
    return fallback, text


def _guess_title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        line = line.strip().lstrip("#").strip()
        if not line:
            continue
        if 2 <= len(line) <= 40:
            return line
        break
    return fallback
