"""Embeddings locaux, déterministes et sans dépendance réseau.

Ce repli permet au service RAG de rester utilisable lorsqu'un modèle
SentenceTransformers ou une clé OpenAI n'est pas disponible.
"""

from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from typing import List


class LocalHashEmbeddings:
    """Représentation vectorielle légère fondée sur les mots normalisés."""

    dimension = 384

    @staticmethod
    def _tokens(text: str) -> List[str]:
        normalized = unicodedata.normalize("NFKD", text.lower())
        normalized = "".join(char for char in normalized if not unicodedata.combining(char))
        return re.findall(r"[a-z0-9]+", normalized)

    def _embed(self, text: str) -> List[float]:
        vector = [0.0] * self.dimension
        for token in self._tokens(text):
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            value = int.from_bytes(digest, "big")
            index = value % self.dimension
            vector[index] += 1.0 if value & 1 else -1.0

        norm = math.sqrt(sum(value * value for value in vector))
        return [value / norm for value in vector] if norm else vector

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> List[float]:
        return self._embed(text)
