"""导入知识库脚本"""
import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.rag_service import rag_service, BUILT_IN_KNOWLEDGE


async def import_knowledge(filepath: str):
    """从 JSON 文件导入知识库"""
    print(f"正在从 {filepath} 导入知识库...")

    if not os.path.exists(filepath):
        print(f"文件不存在: {filepath}")
        return

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    count = 0
    for item in data:
        question = item.get("question", "")
        answer = item.get("answer", "")
        category = item.get("category", "")
        keywords = item.get("keywords", "")

        if question and answer:
            vector_id = await rag_service.add_document(
                question=question,
                answer=answer,
                category=category,
                keywords=keywords,
            )
            print(f"  已导入: {vector_id} — {question[:30]}...")
            count += 1

    print(f"导入完成！共导入 {count} 条知识。")
    print(f"知识库总量: {len(BUILT_IN_KNOWLEDGE)} 条")


if __name__ == "__main__":
    filepath = sys.argv[1] if len(sys.argv) > 1 else "../knowledge_base/faqs/faqs.json"
    asyncio.run(import_knowledge(filepath))
