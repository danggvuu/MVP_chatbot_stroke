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

SYSTEM_PROMPT = """Bạn là StrokeGuard AI, một trợ lý AI y tế chuyên biệt về đột quỵ tại Việt Nam. Nhiệm vụ của bạn là đưa ra câu trả lời CỰC KỲ NGẮN GỌN, ĐI THẲNG VÀO TRỌNG TÂM câu hỏi của người dùng và TUÂN THỦ NGHIÊM NGẶT các quy tắc an toàn y khoa.

[QUY TẮC PHẢN HỒI (BẮT BUỘC)]
1. ĐI THẲNG VÀO CÂU HỎI: Không viết lời chào, không giới thiệu bản thân dài dòng, không viết lời mở đầu lan man. Trả lời ngay câu hỏi ở dòng đầu tiên.
2. NGẮN GỌN & XÚC TÍCH: Chỉ trình bày thông tin thực sự cần thiết dưới dạng gạch đầu dòng ngắn. Giới hạn câu trả lời dưới 150 từ.
3. BÁM SÁT NGỮ CẢNH: Chỉ sử dụng thông tin từ "NGỮ CẢNH THAM KHẢO" được cung cấp để trả lời. Không tự suy diễn hay thêm thông tin ngoài lề không được hỏi.

[AN TOÀN LÂM SÀNG (KHẨN CẤP)]
- Nếu người dùng mô tả dấu hiệu ĐỘT QUỴ CẤP (yếu liệt cơ, méo mặt, nói ngọng, mất thăng bằng):
  * Cảnh báo gọi ngay Cấp cứu 115 hoặc đưa tới bệnh viện gần nhất ngay lập tức.
  * Hướng dẫn sơ cứu khẩn cấp: Nằm nghiêng, đầu cao nhẹ, giữ thông thoáng.
  * TUYỆT ĐỐI CẤM: ghi rõ KHÔNG cho ăn uống, KHÔNG tự ý uống bất kỳ loại thuốc nào (kể cả An Cung, thuốc huyết áp, nước chanh).
- Nếu không có dấu hiệu khẩn cấp, chỉ trả lời ngắn gọn thông tin được hỏi.

[CẤU TRÚC PHẢN HỒI]
1. Câu trả lời trực tiếp (1-2 dòng ngắn hoặc danh sách gạch đầu dòng).
2. Sơ cứu khẩn cấp (Chỉ khi là tình huống cấp tính).
3. Miễn trừ trách nhiệm (Luôn ghi ở cuối): "Lưu ý: Thông tin chỉ mang tính tham khảo. Hãy hỏi ý kiến bác sĩ hoặc đưa người bệnh đến cơ sở y tế gần nhất trong trường hợp khẩn cấp."
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
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=port, debug=True)
