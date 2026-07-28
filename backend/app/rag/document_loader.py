"""RAG 模块 — 文档加载器"""
import os
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


class DocumentLoader:
    """文档加载器 — 支持多种格式"""

    SUPPORTED_EXTENSIONS = {".txt", ".md", ".json", ".csv"}

    def load_directory(self, directory: str) -> List[Dict[str, str]]:
        """加载目录中的所有支持文档"""
        documents = []
        if not os.path.isdir(directory):
            logger.warning(f"目录不存在: {directory}")
            return documents

        for root, dirs, files in os.walk(directory):
            for filename in files:
                ext = os.path.splitext(filename)[1].lower()
                if ext not in self.SUPPORTED_EXTENSIONS:
                    continue
                filepath = os.path.join(root, filename)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        content = f.read()
                    category = os.path.basename(root)
                    documents.append({
                        "filename": filename,
                        "category": category,
                        "content": content,
                    })
                    logger.info(f"已加载: {filepath}")
                except Exception as e:
                    logger.error(f"加载失败 {filepath}: {e}")
        return documents

    def load_qa_pairs(self, filepath: str) -> List[Dict[str, str]]:
        """从 JSON 文件加载 QA 对"""
        import json
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        # 期望格式: [{"question": "...", "answer": "...", "category": "..."}]
        return data
