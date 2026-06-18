"""
StrokeGuard AI — Hybrid Retrieval Engine v2.0
==============================================
Kết hợp BM25 (keyword) + Qdrant (semantic vector) qua Reciprocal Rank Fusion.
Tự phát hiện GPU (MPS / CUDA / CPU) và fallback an toàn về BM25 thuần túy
nếu thiếu thư viện nặng (torch, qdrant-client, sentence-transformers).
"""

import os
import json
import math
import re
import platform
import logging
from collections import Counter

from underthesea import word_tokenize

logger = logging.getLogger(__name__)

# ── Fail-safe imports ──────────────────────────────────────────────────────────
# Nếu máy chưa cài thư viện nặng, hệ thống vẫn chạy bằng BM25 thuần túy.
HAS_VECTOR_SEARCH = False
try:
    from qdrant_client import QdrantClient
    from qdrant_client.http.models import Distance, VectorParams, PointStruct
    from sentence_transformers import SentenceTransformer
    import torch
    import numpy as np
    HAS_VECTOR_SEARCH = True
except ImportError as e:
    logger.warning(f"[Retrieval] Thiếu thư viện vector search ({e}). Chạy chế độ BM25 thuần túy.")

# ── Constants ──────────────────────────────────────────────────────────────────
EMBEDDING_MODEL = os.environ.get(
    "EMBEDDING_MODEL",
    "GreenNode/GreenNode-Embedding-Large-VN-Mixed-V1"
)
QDRANT_DB_PATH = os.environ.get("QDRANT_DB_PATH", "data/qdrant_db")
RRF_K = 60  # Hệ số RRF tiêu chuẩn

VIETNAMESE_STOPWORDS = {
    'và', 'hoặc', 'nhưng', 'vì', 'nên', 'thì', 'ở', 'tại', 'có', 'không',
    'như', 'thế_nào', 'như_thế_nào', 'tôi', 'người', 'nhà', 'người_nhà',
    'này', 'được', 'cho', 'làm', 'sao', 'để', 'của', 'với', 'trong',
    'm', 'k', 'dc', 'ko', 'kh', 'đc', 'bị', 'đã', 'đang', 'sẽ',
    'chúng_tôi', 'chúng_ta', 'bạn', 'mình', 'nếu', 'là', 'cái', 'sự',
    'việc', 'những', 'các', 'ra', 'vào', 'lên', 'xuống', 'đi', 'lại',
    'qua', 'đến', 'nơi', 'nào', 'gì', 'ai', 'đâu', 'khi', 'lúc',
    'sau', 'trước', 'kia', 'đó', 'ấy', 'nọ', 'họ', 'nó', 'chúng',
    'ta', 'tự', 'thường', 'hay', 'rất', 'quá', 'lắm', 'hết', 'cơ',
    'bản', 'mỗi', 'một', 'cả', 'nhất', 'nhỏ', 'lớn', 'nhiều', 'ít',
    'vừa', 'mới', 'còn', 'đều', 'chỉ', 'cũng', 'vẫn', 'thế', 'nào',
    'đó', 'đây', 'kia', 'nào', 'vậy'
}


# ══════════════════════════════════════════════════════════════════════════════
#  GPU Detection
# ══════════════════════════════════════════════════════════════════════════════
def detect_device() -> str:
    """Tự động phát hiện GPU tốt nhất có sẵn trên máy."""
    if not HAS_VECTOR_SEARCH:
        return "cpu"
    try:
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps"       # Apple Silicon (M1/M2/M3)
        if torch.cuda.is_available():
            return "cuda"      # NVIDIA GPU
    except Exception:
        pass
    return "cpu"


# ══════════════════════════════════════════════════════════════════════════════
#  Vietnamese Tokenizer (cho BM25)
# ══════════════════════════════════════════════════════════════════════════════
def tokenize(text: str) -> list:
    """Tách từ tiếng Việt bằng underthesea, loại bỏ stopwords."""
    if not text:
        return []
    text = text.lower()
    segmented = word_tokenize(text, format="text")
    segmented = re.sub(r'[^\w\s]', ' ', segmented)
    tokens = [word for word in segmented.split() if word]
    return [t for t in tokens if t not in VIETNAMESE_STOPWORDS]


# ══════════════════════════════════════════════════════════════════════════════
#  Reciprocal Rank Fusion (RRF)
# ══════════════════════════════════════════════════════════════════════════════
def reciprocal_rank_fusion(
    bm25_ranked_ids: list,
    semantic_ranked_ids: list,
    k: int = RRF_K
) -> list:
    """
    Kết hợp 2 danh sách kết quả bằng RRF.
    RRF_score(d) = Σ 1 / (k + rank_i(d))
    Trả về danh sách doc_id sắp xếp theo RRF score giảm dần.
    """
    rrf_scores = {}
    for rank, doc_id in enumerate(bm25_ranked_ids, start=1):
        rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1.0 / (k + rank)
    for rank, doc_id in enumerate(semantic_ranked_ids, start=1):
        rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1.0 / (k + rank)
    sorted_ids = sorted(rrf_scores.keys(), key=lambda did: rrf_scores[did], reverse=True)
    return sorted_ids


# ══════════════════════════════════════════════════════════════════════════════
#  Main Retriever Class
# ══════════════════════════════════════════════════════════════════════════════
class StrokeRetriever:
    """
    Hybrid Retriever: BM25 + Qdrant Semantic Search + RRF.
    Tự động fallback về BM25 thuần túy nếu không có thư viện vector search.
    """

    def __init__(self, kb_path="data/knowledge_base.json"):
        self.kb_path = kb_path
        self.documents = []
        self.doc_map = {}  # id -> document dict

        # ── BM25 state ──
        self.doc_tokens = []
        self.vocab = set()
        self.doc_freqs = Counter()
        self.N = 0
        self.avg_doc_len = 0.0

        # ── Vector search state ──
        self.use_vector = False
        self.embedder = None
        self.qdrant = None
        self.collection_name = "stroke_chunks"
        self.device = "cpu"

        # Nạp dữ liệu
        self.load_database()

    # ── Database Loading ───────────────────────────────────────────────────
    def load_database(self):
        """Nạp knowledge base JSON và khởi tạo cả BM25 lẫn Qdrant."""
        if not os.path.exists(self.kb_path):
            logger.warning(f"[Retrieval] {self.kb_path} not found. Database is empty.")
            self.documents = []
            return

        try:
            with open(self.kb_path, "r", encoding="utf-8") as f:
                self.documents = json.load(f)
        except Exception as e:
            logger.error(f"[Retrieval] Error loading {self.kb_path}: {e}")
            self.documents = []
            return

        # Build doc_map for fast lookup
        self.doc_map = {doc["id"]: doc for doc in self.documents}

        # ── BM25 Index ──
        self._build_bm25_index()

        # ── Vector Search (Qdrant) ──
        if HAS_VECTOR_SEARCH:
            try:
                self._init_vector_search()
                self.use_vector = True
                logger.info("[Retrieval] ✅ Hybrid mode: BM25 + Qdrant Semantic Search")
            except Exception as e:
                logger.warning(f"[Retrieval] ⚠️ Vector search init failed ({e}). Using BM25 only.")
                self.use_vector = False
        else:
            logger.info("[Retrieval] Chế độ BM25 thuần túy (thiếu thư viện vector search).")

    # ── BM25 ───────────────────────────────────────────────────────────────
    def _build_bm25_index(self):
        """Xây dựng BM25 index cho tất cả document."""
        self.N = len(self.documents)
        self.doc_tokens = [
            tokenize(doc['section_title'] + " " + doc['content'])
            for doc in self.documents
        ]
        self.vocab = set(token for doc in self.doc_tokens for token in doc)

        self.doc_freqs = Counter()
        total_len = 0
        for doc in self.doc_tokens:
            total_len += len(doc)
            for token in set(doc):
                self.doc_freqs[token] += 1
        self.avg_doc_len = total_len / self.N if self.N > 0 else 0.0

    def _bm25_search(self, query: str, top_k: int = 10, k1: float = 1.2, b: float = 0.75, title_weight: float = 2.0) -> list:
        """Tìm kiếm BM25 cho một câu query đơn. Trả về [(doc_id, score), ...]."""
        query_tokens = tokenize(query)
        if not query_tokens:
            return []

        unique_query_tokens = list(set(query_tokens))
        scores = []
        for i, doc in enumerate(self.doc_tokens):
            score = 0.0
            doc_len = len(doc)
            if doc_len == 0:
                continue

            doc_counter = Counter(doc)
            title_tokens = tokenize(self.documents[i]['section_title'])

            for token in unique_query_tokens:
                token_in_body = doc_counter[token] > 0
                token_in_title = token in title_tokens

                if token_in_body or token_in_title:
                    if token in self.vocab:
                        df = self.doc_freqs[token]
                        idf = math.log((self.N + 1) / (df + 0.5)) + 1

                        tf = doc_counter[token]
                        body_score = idf * (tf * (k1 + 1)) / (tf + k1 * (1.0 - b + b * (doc_len / self.avg_doc_len)))
                        title_score = (1.0 if token_in_title else 0.0) * idf * title_weight

                        score += body_score + title_score

            if score > 0:
                scores.append((self.documents[i]["id"], score))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    # ── Vector Search (Qdrant + SentenceTransformer) ───────────────────────
    def _init_vector_search(self):
        """Khởi tạo SentenceTransformer + Qdrant Local, ingest nếu cần."""
        self.device = detect_device()
        logger.info(f"[Retrieval] 🖥️ Embedding device: {self.device}")
        logger.info(f"[Retrieval] 📦 Embedding model: {EMBEDDING_MODEL}")

        self.embedder = SentenceTransformer(EMBEDDING_MODEL, device=self.device)

        # Khởi tạo Qdrant Local (ghi file trực tiếp, không cần Docker)
        os.makedirs(QDRANT_DB_PATH, exist_ok=True)
        self.qdrant = QdrantClient(path=QDRANT_DB_PATH)

        # Kiểm tra collection
        collections = self.qdrant.get_collections().collections
        collection_exists = any(c.name == self.collection_name for c in collections)

        if not collection_exists:
            logger.info("[Retrieval] Qdrant collection chưa tồn tại. Đang tạo mới và ingest vectors...")
            self._ingest_vectors()
        else:
            # Kiểm tra xem số lượng vectors có khớp với knowledge base không
            info = self.qdrant.get_collection(self.collection_name)
            if info.points_count != len(self.documents):
                logger.info(f"[Retrieval] Qdrant có {info.points_count} vectors, KB có {len(self.documents)} docs. Re-ingest...")
                self.qdrant.delete_collection(self.collection_name)
                self._ingest_vectors()
            else:
                logger.info(f"[Retrieval] ✅ Qdrant đã sẵn sàng ({info.points_count} vectors)")

    def _ingest_vectors(self):
        """Sinh vector nhúng cho toàn bộ KB và lưu vào Qdrant."""
        # Lấy vector size từ 1 embedding test
        test_vec = self.embedder.encode("test", convert_to_numpy=True)
        vector_size = len(test_vec)

        self.qdrant.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )

        # Encode tất cả documents
        texts = [
            doc['section_title'] + " " + doc['content']
            for doc in self.documents
        ]
        logger.info(f"[Retrieval] 🔄 Đang tính vector nhúng cho {len(texts)} đoạn văn bản...")
        embeddings = self.embedder.encode(texts, convert_to_numpy=True, show_progress_bar=True, batch_size=32)

        # Upsert vào Qdrant
        points = []
        for i, doc in enumerate(self.documents):
            points.append(PointStruct(
                id=doc["id"],
                vector=embeddings[i].tolist(),
                payload={
                    "doc_id": doc["id"],
                    "source": doc["source"],
                    "url": doc["url"],
                    "title": doc["title"],
                    "section_title": doc["section_title"],
                }
            ))

        # Upsert theo batch 64
        batch_size = 64
        for start in range(0, len(points), batch_size):
            batch = points[start:start + batch_size]
            self.qdrant.upsert(collection_name=self.collection_name, points=batch)

        logger.info(f"[Retrieval] ✅ Đã lưu {len(points)} vectors vào Qdrant (device={self.device})")

    def _semantic_search(self, query: str, top_k: int = 10) -> list:
        """Tìm kiếm ngữ nghĩa qua Qdrant. Trả về [(doc_id, score), ...]."""
        query_vec = self.embedder.encode(query, convert_to_numpy=True).tolist()
        results = self.qdrant.query_points(
            collection_name=self.collection_name,
            query=query_vec,
            limit=top_k,
        )
        return [(hit.payload["doc_id"], hit.score) for hit in results.points]

    # ── Unified Search ─────────────────────────────────────────────────────
    def search(self, query: str, top_k: int = 4) -> list:
        """
        Tìm kiếm lai (Hybrid): BM25 + Semantic + RRF.
        Fallback về BM25 nếu Qdrant không khả dụng.
        """
        if not self.documents:
            self.load_database()
            if not self.documents:
                return []

        # Split multi-sentence queries
        sentences = [s.strip() for s in re.split(r'[.!?]+', query) if s.strip()]
        if not sentences:
            return []

        # ── BM25 search (luôn chạy) ──
        bm25_all = []
        seen_bm25 = set()
        for sentence in sentences:
            for doc_id, score in self._bm25_search(sentence, top_k=top_k * 3):
                if doc_id not in seen_bm25:
                    seen_bm25.add(doc_id)
                    bm25_all.append(doc_id)

        # ── Semantic search (nếu khả dụng) ──
        if self.use_vector and self.qdrant and self.embedder:
            try:
                semantic_all = []
                seen_semantic = set()
                for sentence in sentences:
                    for doc_id, score in self._semantic_search(sentence, top_k=top_k * 3):
                        if doc_id not in seen_semantic:
                            seen_semantic.add(doc_id)
                            semantic_all.append(doc_id)

                # ── RRF Fusion ──
                fused_ids = reciprocal_rank_fusion(bm25_all, semantic_all)
                results = []
                for doc_id in fused_ids[:top_k]:
                    if doc_id in self.doc_map:
                        results.append(self.doc_map[doc_id])
                return results

            except Exception as e:
                logger.warning(f"[Retrieval] Semantic search error ({e}). Falling back to BM25.")

        # ── Fallback: BM25 only ──
        results = []
        for doc_id in bm25_all[:top_k]:
            if doc_id in self.doc_map:
                results.append(self.doc_map[doc_id])
        return results


# ══════════════════════════════════════════════════════════════════════════════
#  CLI Test
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    retriever = StrokeRetriever()
    test_query = "sơ cứu đột quỵ"
    print(f"\nTesting search for: '{test_query}'")
    print(f"Mode: {'Hybrid (BM25 + Qdrant)' if retriever.use_vector else 'BM25 only'}")
    print(f"Device: {retriever.device}")
    print(f"Documents: {len(retriever.documents)}")
    print()
    results = retriever.search(test_query, top_k=3)
    for r in results:
        print(f"- [{r['source']}] {r['section_title']}: {r['content'][:150]}...")
