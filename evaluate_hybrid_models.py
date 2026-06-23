import time
from retrieval import StrokeRetriever

TEST_QUERIES = [
    "Bị méo miệng có nên cho uống An cung ngưu hoàng hoàn trước khi đi cấp cứu không?",
    "Tôi bị nhức đầu và tê tay trái 10 phút rồi tự hết, đó là bệnh gì?",
    "Người nhà đang bị đột quỵ, có nên dùng kim chích nặn máu 10 đầu ngón tay không?",
    "Tôi đang uống Aspirin nhưng bị đau dạ dày đi ngoài phân đen, có nên tự ý dừng không?",
    "Thời gian vàng để tiêm thuốc tiêu sọ huyết khối rTPA là bao nhiêu tiếng?"
]

def run_evaluation(model_name, collection_name):
    print(f"\n{'='*60}")
    print(f"BẮT ĐẦU ĐÁNH GIÁ MÔ HÌNH: {model_name}")
    print(f"{'='*60}")
    
    # Init retriever
    t0 = time.time()
    retriever = StrokeRetriever(
        kb_path="data/knowledge_base.json", 
        embedding_model=model_name, 
        collection_name=collection_name
    )
    init_time = time.time() - t0
    print(f"[+] Thời gian tải mô hình và index DB: {init_time:.2f} giây")
    print(f"[+] Số lượng documents: {len(retriever.documents)}")
    
    total_latency = 0
    for i, query in enumerate(TEST_QUERIES, 1):
        print(f"\n--- Câu {i} ---")
        print(f"Q: {query}")
        
        t0 = time.time()
        results = retriever.search(query, top_k=3)
        latency = time.time() - t0
        total_latency += latency
        
        print(f"Thời gian tìm kiếm: {latency:.4f} giây")
        for j, r in enumerate(results, 1):
            print(f"  Top {j}: [{r['source']}] {r['section_title']}")
            
    print(f"\n=> TỐC ĐỘ TRUNG BÌNH: {total_latency / len(TEST_QUERIES):.4f} giây/câu hỏi")

if __name__ == "__main__":
    import logging
    logging.getLogger("retrieval").setLevel(logging.WARNING) # Ẩn bớt log rác
    
    # 1. Đánh giá vietnamese-sbert
    run_evaluation(
        model_name="keepitreal/vietnamese-sbert",
        collection_name="stroke_chunks_sbert"
    )
    
    # 2. Đánh giá GreenNode (Mô hình cũ siêu nặng)
    run_evaluation(
        model_name="GreenNode/GreenNode-Embedding-Large-VN-Mixed-V1",
        collection_name="stroke_chunks_greennode"
    )
