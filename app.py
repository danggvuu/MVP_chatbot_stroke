import os
import json
import requests
from flask import Flask, request, jsonify, render_template, send_from_directory, Response
from retrieval import StrokeRetriever

app = Flask(__name__, static_folder="static", template_folder="templates")

# Configuration from environment variables
OLLAMA_API_URL = os.environ.get("OLLAMA_API_URL", "http://localhost:11434").rstrip('/')
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")
KB_PATH = os.environ.get("KB_PATH", "data/knowledge_base.json")

# Initialize retriever
retriever = StrokeRetriever(kb_path=KB_PATH)

SYSTEM_PROMPT = """Bạn là trợ lý ảo hỗ trợ tra cứu Hướng dẫn Sơ cứu Đột quỵ của Bộ Y tế. Nhiệm vụ của bạn là trả lời CỰC KỲ NGẮN GỌN, ĐI THẲNG VÀO TRỌNG TÂM câu hỏi và TUÂN THỦ các chỉ dẫn an toàn sau:

[QUY TẮC CỐT LÕI (GIẢM LAN MAN & TẬP TRUNG)]
1. TRẢ LỜI TRỰC TIẾP DÒNG ĐẦU TIÊN: Không chào hỏi, không từ chối kiểu "tôi không thể đưa ra lời khuyên y tế", không giới thiệu bản thân hay viết lời mở đầu lan man. Trả lời thẳng vào câu hỏi.
2. ĐỐI CHIẾU HÀNH ĐỘNG CỤ THỂ: Nếu người dùng hỏi có nên làm một việc gì đó (ví dụ: uống An Cung, uống nước chanh, cạo gió, chích máu tai, tự dừng Aspirin, tự tập vật lý trị liệu...), bạn phải khẳng định hoặc phủ định rõ ràng ngay lập tức.
   - Ví dụ: "Tuyệt đối KHÔNG được uống An Cung hay nước chanh..." hoặc "Không được tự ý dừng thuốc Aspirin...".
3. CHỈ DÙNG NGỮ CẢNH: Trả lời ngắn gọn (dưới 120 từ) dưới dạng các gạch đầu dòng súc tích dựa trên thông tin trong "NGỮ CẢNH THAM KHẢO". Không suy diễn ngoài tài liệu.

[AN TOÀN Y KHOA (BẮT BUỘC)]
- Nếu câu hỏi mô tả triệu chứng đột quỵ cấp tính (méo miệng, yếu tay chân, khó nói):
  * Yêu cầu đưa đi cấp cứu hoặc gọi 115 ngay lập tức.
  * Hướng dẫn sơ cứu: Nằm nghiêng, đầu cao nhẹ, giữ thông thoáng.
  * Nhấn mạnh: CẤM tự ý cho ăn uống hay uống bất kỳ loại thuốc nào.

[CẤU TRÚC PHẢN HỒI]
1. Trả lời trực tiếp câu hỏi (khẳng định/phủ định hành động).
2. Các gạch đầu dòng giải thích ngắn gọn từ tài liệu.
3. Hướng dẫn sơ cứu cấp cứu (nếu là tình huống cấp tính).
4. Miễn trừ trách nhiệm (Luôn ghi ở cuối cùng): "Lưu ý: Thông tin dựa trên hướng dẫn y tế của Bộ Y tế và chỉ mang tính tham khảo. Hãy tham khảo ý kiến bác sĩ hoặc đưa người bệnh đến cơ sở y tế gần nhất trong trường hợp khẩn cấp."
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
    stream_requested = data.get("stream", False)
    
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
        "stream": stream_requested,
        "options": {
            "temperature": 0.3 # Low temperature for factual medical responses
        }
    }
    
    if stream_requested:
        def generate():
            # Send citations first
            yield f"data: {json.dumps({'sources': sources_metadata})}\n\n"
            try:
                r = requests.post(f"{OLLAMA_API_URL}/api/chat", json=payload, stream=True, timeout=45)
                if r.status_code != 200:
                    yield f"data: {json.dumps({'error': 'Ollama error', 'detail': r.text})}\n\n"
                    return
                for line in r.iter_lines():
                    if line:
                        decoded_line = line.decode('utf-8')
                        try:
                            json_line = json.loads(decoded_line)
                            content = json_line.get("message", {}).get("content", "")
                            if content:
                                yield f"data: {json.dumps({'delta': content})}\n\n"
                            if json_line.get("done", False):
                                break
                        except json.JSONDecodeError:
                            pass
            except Exception as e:
                yield f"data: {json.dumps({'error': 'Connection error', 'detail': str(e)})}\n\n"
        return Response(generate(), mimetype='text/event-stream')
        
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
    port = int(os.environ.get("PORT", 5080))
    app.run(host="0.0.0.0", port=port, debug=True)
