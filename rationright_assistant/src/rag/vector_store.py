"""
ChromaDB vector store and semantic retriever for RationRight data dictionaries,
schema definitions, and system alert rules.
"""
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import chromadb
from chromadb.api.models.Collection import Collection
from sentence_transformers import SentenceTransformer

from src.config import settings
from src.rag.dictionary_data import DICTIONARY_CHUNKS

# Force offline mode for local cached SentenceTransformer
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

COLLECTION_NAME = "rationright_data_dictionary"
MODEL_NAME = "all-MiniLM-L6-v2"


class DictionaryRetriever:
    """Manages ChromaDB vector store and semantic search over system documentation."""

    def __init__(self, chroma_dir: Optional[Path] = None):
        self.chroma_dir = chroma_dir or settings.CHROMA_DIR
        self.chroma_dir.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(self.chroma_dir))
        self.embedding_model = SentenceTransformer(MODEL_NAME, local_files_only=True)
        self.collection = self._get_or_create_collection()

    def _get_or_create_collection(self) -> Collection:
        """Retrieve existing collection or create and populate it."""
        collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"description": "RationRight PDS Data Dictionary & Policy Corpus"},
        )
        if collection.count() == 0:
            self._seed_collection(collection)
        return collection

    def _seed_collection(self, collection: Collection) -> None:
        """Seed the ChromaDB collection with structured data dictionary chunks."""
        ids = [chunk["id"] for chunk in DICTIONARY_CHUNKS]
        documents = [chunk["content"] for chunk in DICTIONARY_CHUNKS]
        metadatas = [
            {
                "title": chunk["title"],
                "category": chunk["category"],
                "keywords": ", ".join(chunk.get("keywords", [])),
            }
            for chunk in DICTIONARY_CHUNKS
        ]

        # Compute embeddings locally
        embeddings = self.embedding_model.encode(documents).tolist()

        collection.upsert(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )

    def query(
        self,
        query_text: str,
        top_k: int = 3,
        category: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Execute semantic search against documentation chunks.
        Returns matched chunks with title, category, content, and similarity distance.
        """
        query_embedding = self.embedding_model.encode([query_text]).tolist()
        
        where_filter = {"category": category} if category else None

        results = self.collection.query(
            query_embeddings=query_embedding,
            n_results=min(top_k, self.collection.count()),
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )

        formatted_results: List[Dict[str, Any]] = []
        if results and results["ids"] and len(results["ids"][0]) > 0:
            for idx in range(len(results["ids"][0])):
                doc_id = results["ids"][0][idx]
                doc_text = results["documents"][0][idx]
                meta = results["metadatas"][0][idx]
                distance = results["distances"][0][idx] if "distances" in results and results["distances"] else 0.0
                
                # Convert distance to normalized similarity score (for cosine / l2)
                score = round(1.0 / (1.0 + float(distance)), 4)

                formatted_results.append({
                    "id": doc_id,
                    "title": meta.get("title", ""),
                    "category": meta.get("category", ""),
                    "content": doc_text,
                    "score": score,
                })

        return formatted_results


# Global retriever instance
_retriever: Optional[DictionaryRetriever] = None


def get_retriever() -> DictionaryRetriever:
    """Lazy singleton accessor for the DictionaryRetriever."""
    global _retriever
    if _retriever is None:
        _retriever = DictionaryRetriever()
    return _retriever

