import os
import json
import math
import re
from collections import Counter
from underthesea import word_tokenize

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

def tokenize(text):
    if not text:
        return []
    # Lowercase first
    text = text.lower()
    # Word tokenize replaces space in compound words with underscore, e.g. "đột quỵ" -> "đột_quỵ"
    segmented = word_tokenize(text, format="text")
    # Remove punctuation and split by whitespace
    segmented = re.sub(r'[^\w\s]', ' ', segmented)
    tokens = [word for word in segmented.split() if word]
    return [t for t in tokens if t not in VIETNAMESE_STOPWORDS]

class StrokeRetriever:
    def __init__(self, kb_path="data/knowledge_base.json"):
        self.kb_path = kb_path
        self.documents = []
        self.doc_tokens = []
        self.vocab = set()
        self.doc_freqs = Counter()
        self.N = 0
        self.avg_doc_len = 0.0
        self.load_database()

    def load_database(self):
        if not os.path.exists(self.kb_path):
            print(f"Warning: {self.kb_path} not found. Retrieval database is empty.")
            self.documents = []
            return
            
        try:
            with open(self.kb_path, "r", encoding="utf-8") as f:
                self.documents = json.load(f)
        except Exception as e:
            print(f"Error loading {self.kb_path}: {e}")
            self.documents = []
            return
            
        self.N = len(self.documents)
        self.doc_tokens = [tokenize(doc['section_title'] + " " + doc['content']) for doc in self.documents]
        self.vocab = set(token for doc in self.doc_tokens for token in doc)
        
        self.doc_freqs = Counter()
        total_len = 0
        for doc in self.doc_tokens:
            total_len += len(doc)
            unique_tokens = set(doc)
            for token in unique_tokens:
                self.doc_freqs[token] += 1
        self.avg_doc_len = total_len / self.N if self.N > 0 else 0.0
                
    def _search_single_query(self, query, k1=1.2, b=0.75, title_weight=2.0):
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
            matched_count = 0
            
            for token in unique_query_tokens:
                token_in_body = doc_counter[token] > 0
                token_in_title = token in title_tokens
                
                if token_in_body or token_in_title:
                    matched_count += 1
                    
                    if token in self.vocab:
                        df = self.doc_freqs[token]
                        idf = math.log((self.N + 1) / (df + 0.5)) + 1
                        
                        tf = doc_counter[token]
                        body_score = idf * (tf * (k1 + 1)) / (tf + k1 * (1.0 - b + b * (doc_len / self.avg_doc_len)))
                        title_score = (1.0 if token_in_title else 0.0) * idf * title_weight
                        
                        score += body_score + title_score
            
            if score > 0:
                scores.append((score, self.documents[i]))
            
        return sorted(scores, key=lambda x: x[0], reverse=True)

    def search(self, query, top_k=4):
        # Reload database if it was empty
        if not self.documents:
            self.load_database()
            if not self.documents:
                return []
                
        # Split query by punctuation into sentences to perform multi-intent search
        sentences = [s.strip() for s in re.split(r'[.!?]+', query) if s.strip()]
        if not sentences:
            return []
            
        all_results = []
        seen_ids = set()
        
        # Search each sentence separately
        sentence_searches = [self._search_single_query(s) for s in sentences]
        
        # Interleave the search results from each sentence
        max_len = max(len(lst) for lst in sentence_searches) if sentence_searches else 0
        for idx in range(max_len):
            for s_res in sentence_searches:
                if idx < len(s_res):
                    score, doc = s_res[idx]
                    if doc['id'] not in seen_ids:
                        seen_ids.add(doc['id'])
                        all_results.append(doc)
                        if len(all_results) >= top_k:
                            break
            if len(all_results) >= top_k:
                break
                
        return all_results[:top_k]

# Run simple test if executed directly
if __name__ == "__main__":
    retriever = StrokeRetriever()
    test_query = "sơ cứu đột quỵ"
    print(f"Testing search for: '{test_query}'")
    results = retriever.search(test_query, top_k=2)
    for r in results:
        print(f"- [{r['source']}] {r['section_title']}: {r['content'][:150]}...")
