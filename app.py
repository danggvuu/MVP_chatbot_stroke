import os
import json
import requests
from flask import Flask, request, jsonify, render_template, send_from_directory
from retrieval import StrokeRetriever

app = Flask(__name__, static_folder="static", template_folder="templates")

# Configuration from environment variables
OLLAMA_API_URL = os.environ.get("OLLAMA_API_URL", "http://localhost:11434").rstrip('/')
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")
KB_PATH = os.environ.get("KB_PATH", "data/knowledge_base.json")

# Initialize retriever
retriever = StrokeRetriever(kb_path=KB_PATH)

SYSTEM_PROMPT = """Bạn là StrokeGuard AI, một trợ lý AI chuyên gia y tế được thiết kế theo cấu trúc CARDS để tư vấn và hỗ trợ đột quỵ. Hãy thực hiện phân tích rủi ro kỹ lưỡng trước khi đưa ra câu trả lời.

[C - CONTEXT (Bối cảnh)]
Bạn hoạt động trong bối cảnh tư vấn, phân loại (triage) và chẩn đoán hỗ trợ ban đầu cho người dùng, bệnh nhân và người nhà bệnh nhân đột quỵ tại Việt Nam.

[A - AIMS (Mục tiêu)]
1. Ưu tiên hàng đầu: Bảo vệ an toàn tính mạng người bệnh. Nhận diện các dấu hiệu đột quỵ khẩn cấp (F.A.S.T) để cảnh báo ngay lập tức.
2. Phân loại nguy cơ y khoa: Nhận biết rõ các rủi ro lâm sàng chính từ thông tin người dùng cung cấp.
3. Giải thích hội thoại: Cung cấp lời giải thích ấm áp, đồng cảm nhưng chuyên nghiệp, có cấu trúc và dễ hiểu đối với người dân.

[R - RELEVANT DETAILS (Chi tiết liên quan)]
1. Nếu phát hiện dấu hiệu đột quỵ cấp (méo miệng, yếu liệt chi, nói ngọng/khó nói), bạn phải:
   - Yêu cầu gọi ngay Cấp cứu 115 hoặc đưa đến bệnh viện có đơn vị đột quỵ gần nhất ngay lập tức.
   - Nhắc nhở quy tắc F.A.S.T và hướng dẫn sơ cứu đúng (nằm nghiêng, đầu cao nhẹ, giữ thông thoáng, KHÔNG tự ý cho uống nước, ăn hay uống bất kỳ loại thuốc nào).
2. Phân tích các yếu tố nguy cơ của bệnh nhân (như tăng huyết áp, đái tháo đường, tiền sử đột quỵ tái phát) để đưa ra lời khuyên phù hợp với hướng dẫn y khoa.

[D - DESIGN (Thiết kế hội thoại & Phân tích)]
Để đảm bảo an toàn tuyệt đối, câu trả lời của bạn phải tuân theo cấu trúc sau:
1. **Phân tích rủi ro y khoa (Risk Analysis)**: Viết 1-2 câu ngắn gọn đánh giá mức độ khẩn cấp và các rủi ro tiềm ẩn dựa trên thông tin người dùng cung cấp.
2. **Nội dung tư vấn chính (Core Guidance)**: Trả lời mạch lạc, sử dụng danh sách gạch đầu dòng, phân chia rõ ràng.
3. **Cảnh báo an toàn & Sơ cứu (Safety Warning - nếu có dấu hiệu cấp tính)**: Làm nổi bật hướng dẫn cấp cứu và quy tắc F.A.S.T.
4. **Miễn trừ trách nhiệm (Disclaimer)**: LUÔN LUÔN ghi rõ: "Lưu ý: Thông tin này chỉ mang tính tham khảo và học tập. Hãy luôn tham khảo ý kiến bác sĩ hoặc đưa người bệnh đến cơ sở y tế gần nhất trong trường hợp khẩn cấp." ở cuối câu trả lời.

[S - SOURCE (Nguồn thông tin)]
Hãy ưu tiên sử dụng thông tin từ cơ sở dữ liệu y tế được cung cấp (Vinmec, Bệnh viện Đa khoa Tâm Anh). Nếu sử dụng kiến thức y khoa bên ngoài, hãy nêu rõ để người dùng nắm được.
"""


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/sources', methods=['GET'])
def get_sources():
    """Returns a list of all documents indexed in the database."""
    if not retriever.documents:
        retriever.load_database()
    
    # Return brief metadata of all sections
    sources_summary = []
    for doc in retriever.documents:
        sources_summary.append({
            "id": doc["id"],
            "source": doc["source"],
            "url": doc["url"],
            "title": doc["title"],
            "section_title": doc["section_title"]
        })
    return jsonify(sources_summary)

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json or {}
    messages = data.get("messages", [])
    
    if not messages:
        return jsonify({"error": "No messages provided"}), 400
        
    # Get the last user message to use as the retrieval query
    last_user_msg = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            last_user_msg = msg.get("content", "")
            break
            
    # Search local database for relevant contexts
    retrieved_docs = retriever.search(last_user_msg, top_k=3)
    
    # Format context for Ollama
    context_str = ""
    sources_metadata = []
    
    if retrieved_docs:
        context_parts = []
        for doc in retrieved_docs:
            context_parts.append(
                f"Nguồn: {doc['source']} ({doc['url']})\n"
                f"Tiêu đề: {doc['title']} - Phần: {doc['section_title']}\n"
                f"Nội dung: {doc['content']}\n"
            )
            sources_metadata.append({
                "id": doc["id"],
                "source": doc["source"],
                "url": doc["url"],
                "title": doc["title"],
                "section_title": doc["section_title"],
                "snippet": doc["content"][:200] + "..."
            })
        context_str = "\n---\n".join(context_parts)
    else:
        context_str = "Không tìm thấy tài liệu liên quan trong cơ sở dữ liệu nội bộ."

    # Construct the final message history to send to Ollama
    # 1. Start with system prompt
    ollama_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    # 2. Append conversation history (except the very last user message which we will enrich)
    history_messages = messages[:-1] if len(messages) > 1 else []
    for msg in history_messages:
        ollama_messages.append({
            "role": msg.get("role"),
            "content": msg.get("content")
        })
        
    # 3. Append the enriched last user message containing the context
    user_enriched_content = (
        f"Hãy trả lời câu hỏi dưới đây của tôi.\n\n"
        f"--- NGỮ CẢNH THAM KHẢO ---\n{context_str}\n--------------------------\n\n"
        f"CÂU HỎI CỦA TÔI: {last_user_msg}"
    )
    ollama_messages.append({"role": "user", "content": user_enriched_content})
    
    # Call local Ollama API
    payload = {
        "model": OLLAMA_MODEL,
        "messages": ollama_messages,
        "stream": False,
        "options": {
            "temperature": 0.3 # Low temperature for factual medical responses
        }
    }
    
    try:
        response = requests.post(f"{OLLAMA_API_URL}/api/chat", json=payload, timeout=45)
        if response.status_code != 200:
            return jsonify({
                "error": f"Ollama returned error status {response.status_code}",
                "detail": response.text
            }), 502
            
        ollama_res = response.json()
        assistant_message = ollama_res.get("message", {}).get("content", "")
        
        return jsonify({
            "message": assistant_message,
            "sources": sources_metadata
        })
        
    except requests.exceptions.RequestException as e:
        return jsonify({
            "error": "Could not connect to Ollama server. Please ensure Ollama is running.",
            "detail": str(e),
            "ollama_url": OLLAMA_API_URL
        }), 503

@app.route('/api/health', methods=['GET'])
def health():
    """Verify backend health and check connections."""
    ollama_status = "offline"
    available_models = []
    
    try:
        r = requests.get(f"{OLLAMA_API_URL}/api/tags", timeout=3)
        if r.status_code == 200:
            ollama_status = "online"
            models_data = r.json()
            available_models = [m["name"] for m in models_data.get("models", [])]
    except Exception:
        pass
        
    kb_loaded = len(retriever.documents) > 0
    
    return jsonify({
        "status": "healthy",
        "database_loaded": kb_loaded,
        "database_records": len(retriever.documents),
        "ollama_connection": ollama_status,
        "ollama_url": OLLAMA_API_URL,
        "ollama_model": OLLAMA_MODEL,
        "ollama_model_available": OLLAMA_MODEL in available_models or f"{OLLAMA_MODEL}:latest" in available_models,
        "available_models": available_models
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
