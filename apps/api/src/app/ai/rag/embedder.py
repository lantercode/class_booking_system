"""
FAQ 向量化
职责：将文本转为向量，存入 Milvus
"""

from typing import List


class Embedder:
    """
    文本向量化器

    使用 OpenAI text-embedding-3-small 将文本转为 1536 维向量
    """

    def __init__(self, api_key: str = None):
        self.api_key = api_key
        self.model = "text-embedding-3-small"
        self.dimension = 1536

    async def embed(self, texts: List[str]) -> List[List[float]]:
        """
        将文本列表转为向量列表

        Args:
            texts: 文本列表

        Returns:
            向量列表
        """
        # TODO: 接入 OpenAI Embedding API
        # import openai
        # response = await openai.embeddings.create(
        #     model=self.model,
        #     input=texts
        # )
        # return [item.embedding for item in response.data]

        # 临时返回假数据
        return [[0.0] * self.dimension for _ in texts]