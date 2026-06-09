import os
import json
import math
import re
from collections import Counter
from underthesea import word_tokenize

def tokenize(text):
    if not text:
        return []
    # Lowercase first
    text = text.lower()
    # Word tokenize replaces space in compound words with underscore, e.g. "đột quỵ" -> "đột_quỵ"
    segmented = word_tokenize(text, format="text")
    # Remove punctuation and split by whitespace
    segmented = re.sub(r'[^\w\s]', ' ', segmented)
    return [word for word in segmented.split() if word]

class StrokeRetriever:
    def __init__(self, kb_path="data/knowledge_base.json"):
        self.kb_path = kb_path
        self.documents = []
        self.doc_tokens = []
        self.vocab = set()
        self.doc_freqs = Counter()
        self.N = 0
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
        for doc in self.doc_tokens:
            unique_tokens = set(doc)
            for token in unique_tokens:
                self.doc_freqs[token] += 1
                
    def search(self, query, top_k=3):
        # Reload database if it was empty (e.g. if scraper just ran)
        if not self.documents:
            self.load_database()
            if not self.documents:
                return []
                
        query_tokens = tokenize(query)
        if not query_tokens:
            return self.documents[:top_k]
            
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
            
            # Calculate TF-IDF score
            for token in unique_query_tokens:
                token_in_body = doc_counter[token] > 0
                token_in_title = token in title_tokens
                
                if token_in_body or token_in_title:
                    matched_count += 1
                    tf = doc_counter[token] / doc_len if doc_len > 0 else 0
                    
                    if token_in_title:
                        tf += 0.5  # Title boost factor
                        
                    if token in self.vocab:
                        df = self.doc_freqs[token]
                        idf = math.log((self.N + 1) / (df + 0.5)) + 1
                        score += tf * idf
            
            # Apply coordination factor: rewards documents matching more query terms
            if matched_count > 0 and len(unique_query_tokens) > 0:
                coordination = (matched_count / len(unique_query_tokens)) ** 2
                score *= coordination
                
            scores.append((score, self.documents[i]))
            
        # Sort by score descending
        sorted_docs = sorted(scores, key=lambda x: x[0], reverse=True)
        
        # Keep only matches with a positive score
        results = [doc for score, doc in sorted_docs if score > 0]
        
        # If no positive matches, fall back to default top chunks
        if not results:
            return self.documents[:top_k]
            
        return results[:top_k]

# Run simple test if executed directly
if __name__ == "__main__":
    retriever = StrokeRetriever()
    test_query = "sơ cứu đột quỵ"
    print(f"Testing search for: '{test_query}'")
    results = retriever.search(test_query, top_k=2)
    for r in results:
        print(f"- [{r['source']}] {r['section_title']}: {r['content'][:150]}...")
