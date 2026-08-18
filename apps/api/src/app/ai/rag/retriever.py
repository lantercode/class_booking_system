"""
向量检索
职责：根据用户问题检索最相关的 FAQ
"""

from typing import List, Dict


class Retriever:
    """
    FAQ 检索器

    将用户问题向量化，在 Milvus 中检索最相似的 FAQ
    """

    def __init__(self, embedder=None, milvus_client=None):
        self.embedder = embedder
        self.milvus = milvus_client
        self.collection = "faq_collection"
        self.top_k = 3

    async def search(self, query: str) -> List[Dict]:
        """
        检索与问题最相关的 FAQ

        Args:
            query: 用户问题，如"请假规则是什么"

        Returns:
            FAQ 列表 [{"question": "...", "answer": "...", "score": 0.95}]
        """
        # TODO: 接入 Milvus 向量检索
        # 1. 将 query 向量化
        # 2. 在 Milvus 中搜索最近邻
        # 3. 返回 Top-K 结果

        # 临时返回假数据
        return [
            {
                "question": "如何请假？",
                "answer": "开课前2小时可在小程序自助请假，课时自动退回。",
                "score": 0.95
            }
        ]