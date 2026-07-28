"""RAG 模块 — 文本分块"""
from typing import List


class TextSplitter:
    """文本分块器"""

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 100):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split(self, text: str) -> List[str]:
        """将文本按指定大小分块"""
        if len(text) <= self.chunk_size:
            return [text]

        chunks = []
        start = 0
        while start < len(text):
            end = start + self.chunk_size
            # 尝试在换行符或句号处断开
            if end < len(text):
                # 向前找最近的断点
                for sep in ["\n\n", "\n", "。", "！", "？", ".", "!", "?"]:
                    pos = text.rfind(sep, start, end)
                    if pos > start:
                        end = pos + 1
                        break
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            start = end - self.chunk_overlap if end < len(text) else len(text)

        return chunks

    def split_by_sentences(self, text: str, max_sentences: int = 5) -> List[str]:
        """按句子分块"""
        import re
        sentences = re.split(r'(?<=[。！？.!?])\s*', text)
        sentences = [s.strip() for s in sentences if s.strip()]

        chunks = []
        i = 0
        while i < len(sentences):
            chunk = "".join(sentences[i:i + max_sentences])
            chunks.append(chunk)
            i += max_sentences
        return chunks
