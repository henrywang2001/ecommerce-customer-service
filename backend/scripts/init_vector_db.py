"""初始化向量数据库"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.rag_service import rag_service, BUILT_IN_KNOWLEDGE
from app.services.embedding_service import embedding_service
from app.rag.vector_store import vector_store


async def init_vector_db():
    """将内置知识库向量化并存入 ChromaDB"""
    print("正在初始化向量数据库...")

    if not BUILT_IN_KNOWLEDGE:
        print("知识库为空，无需初始化")
        return

    ids = []
    documents = []
    metadatas = []

    for kb in BUILT_IN_KNOWLEDGE:
        text = f"问题: {kb['question']}\n答案: {kb['answer']}"
        ids.append(kb["id"])
        documents.append(kb["answer"])
        metadatas.append({
            "category": kb["category"],
            "question": kb["question"],
            "keywords": kb.get("keywords", ""),
        })

    print(f"正在向量化 {len(documents)} 条知识...")
    # 批量向量化
    texts = [f"问题: {kb['question']}\n答案: {kb['answer']}" for kb in BUILT_IN_KNOWLEDGE]
    embeddings = await embedding_service.encode(texts)
    print(f"已生成 {len(embeddings)} 个向量")

    # 存入向量数据库
    success = await vector_store.add(
        ids=ids,
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas,
    )

    if success:
        print("向量数据库初始化完成！")
    else:
        print("向量数据库初始化失败（可能未安装 chromadb，已使用内置知识库作为 fallback）")


if __name__ == "__main__":
    asyncio.run(init_vector_db())
