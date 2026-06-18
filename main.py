import os
import json
import argparse
import requests
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv

from retrieval import StrokeRetriever

load_dotenv()

app = FastAPI(title="StrokeGuard AI API", version="2.0.0")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Configuration from environment variables
OLLAMA_API_URL = os.environ.get("OLLAMA_API_URL", "http://localhost:11434").rstrip('/')
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:3b")
KB_PATH = os.environ.get("KB_PATH", "data/knowledge_base.json")

# Initialize retriever lazily
retriever = None

def get_retriever():
    global retriever
    if retriever is None:
        import time
        t0 = time.time()
        retriever = StrokeRetriever(kb_path=KB_PATH)
        print(f"Retriever initialized in {time.time()-t0:.2f}s")
    return retriever
SYSTEM_PROMPT = """Bạn là trợ lý ảo hỗ trợ tra cứu Hướng dẫn Sơ cứu Đột quỵ của Bộ Y tế. Nhiệm vụ của bạn là trả lời CỰC KỲ NGẮN GỌN, ĐI THẲNG VÀO TRỌNG TÂM câu hỏi và TUÂN THỦ các chỉ dẫn an toàn sau:

[QUY TẮC CỐT LÕI (GIẢM LAN MAN & TẬP TRUNG)]
1. TRẢ LỜI TRỰC TIẾP DÒNG ĐẦU TIÊN: Không chào hỏi, không từ chối kiểu "tôi không thể đưa ra lời khuyên y tế", không giới thiệu bản thân hay viết lời mở đầu lan man. Trả lời thẳng vào câu hỏi.
2. ĐỐI CHIẾU HÀNH ĐỘNG CỤ THỂ: Nếu người dùng hỏi có nên làm một việc gì đó (ví dụ: uống An Cung, uống nước chanh, cạo gió, chích máu tai, tự dừng Aspirin, tự tập vật lý trị liệu...), bạn phải khẳng định hoặc phủ định rõ ràng ngay lập tức.
   - Ví dụ: "Tuyệt đối KHÔNG được uống An Cung hay nước chanh..." hoặc "Không được tự ý dừng thuốc Aspirin...".
3. CHỈ DÙNG NGỮ CẢNH: Trả lời ngắn gọn (dưới 120 từ) dưới dạng các gạch đầu dòng súc tích dựa trên thông tin trong "NGỮ CẢNH THAM KHẢO". Không suy diễn ngoài tài liệu. Trích dẫn nguồn bằng cách thêm ký hiệu [1], [2], [3] hoặc [4] tương ứng với tài liệu số 1, 2, 3, 4 ở cuối câu chứa thông tin trích dẫn.
4. CÂU HỎI NGOÀI CHỦ ĐỀ: Nếu người dùng hỏi các câu hỏi hoàn toàn không liên quan đến y học, sức khỏe hay đột quỵ (ví dụ: lập trình, viết code, viết chương trình, toán học, thời tiết, giải trí, hỏi "m code dc k", "code hộ"...), hãy lịch sự từ chối ngay lập tức và nêu rõ bạn chỉ hỗ trợ tra cứu sơ cứu đột quỵ.

[AN TOÀN Y KHOA (BẮT BUỘC)]
- Nếu câu hỏi mô tả triệu chứng đột quỵ cấp tính (méo miệng, yếu tay chân, khó nói):
  * Yêu cầu đưa đi cấp cứu hoặc gọi 115 ngay lập tức.
  * Hướng dẫn sơ cứu: Nằm nghiêng, đầu cao nhẹ, giữ thông thoáng.
  * Nhấn mạnh: CẤM tự ý cho ăn uống hay uống bất kỳ loại thuốc nào.

[CẤU TRÚC PHẢN HỒI]
1. Trả lời trực tiếp câu hỏi (khẳng định/phủ định hành động hoặc từ chối nếu ngoài chủ đề).
2. Các gạch đầu dòng giải thích ngắn gọn từ tài liệu (nếu đúng chủ đề, kèm trích dẫn số ở cuối câu).
3. Hướng dẫn sơ cứu cấp cứu (nếu là tình huống cấp tính).
4. Miễn trừ trách nhiệm (Luôn ghi ở cuối cùng nếu là câu hỏi y học): "Lưu ý: Thông tin dựa trên hướng dẫn y tế của Bộ Y tế và chỉ mang tính tham khảo. Hãy tham khảo ý kiến bác sĩ hoặc đưa người bệnh đến cơ sở y tế gần nhất trong trường hợp khẩn cấp."
"""

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/sources")
async def get_sources():
    """Returns a list of all documents indexed in the database."""
    r = get_retriever()
    if not r.documents:
        r.load_database()
    
    sources_summary = []
    for doc in r.documents:
        sources_summary.append({
            "id": doc["id"],
            "source": doc["source"],
            "url": doc["url"],
            "title": doc["title"],
            "section_title": doc["section_title"]
        })
    return sources_summary

@app.post("/api/retrieve")
async def retrieve_only(request: Request):
    """Retrieve chunks only without calling LLM."""
    data = await request.json()
    query = data.get("question", "")
    top_k = data.get("top_k", 4)
    
    if not query:
        return JSONResponse(content={"error": "No question provided"}, status_code=400)
        
    r = get_retriever()
    retrieved_docs = r.search(query, top_k=top_k)
    return {"question": query, "chunks": retrieved_docs}

@app.post("/api/chat")
async def chat(request: Request):
    data = await request.json()
    messages = data.get("messages", [])
    stream_requested = data.get("stream", False)
    
    if not messages:
        return JSONResponse(content={"error": "No messages provided"}, status_code=400)
        
    last_user_msg = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            last_user_msg = msg.get("content", "")
            break
            
    r = get_retriever()
    retrieved_docs = r.search(last_user_msg, top_k=4)
    
    context_str = ""
    sources_metadata = []
    
    if retrieved_docs:
        context_parts = []
        for i, doc in enumerate(retrieved_docs):
            context_parts.append(
                f"Tài liệu [{i+1}]:\n"
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

    ollama_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    history_messages = messages[:-1] if len(messages) > 1 else []
    for msg in history_messages:
        ollama_messages.append({
            "role": msg.get("role"),
            "content": msg.get("content")
        })
        
    user_enriched_content = (
        f"Hãy trả lời câu hỏi dưới đây của tôi.\n\n"
        f"--- NGỮ CẢNH THAM KHẢO ---\n{context_str}\n--------------------------\n\n"
        f"CÂU HỎI CỦA TÔI: {last_user_msg}"
    )
    ollama_messages.append({"role": "user", "content": user_enriched_content})
    
    payload = {
        "model": OLLAMA_MODEL,
        "messages": ollama_messages,
        "stream": stream_requested,
        "options": {
            "temperature": 0.3
        }
    }
    
    if stream_requested:
        def event_stream():
            yield f"data: {json.dumps({'sources': sources_metadata})}\n\n"
            try:
                with requests.post(f"{OLLAMA_API_URL}/api/chat", json=payload, stream=True, timeout=45) as r:
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
        headers = {
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
        return StreamingResponse(event_stream(), media_type="text/event-stream", headers=headers)
        
    try:
        response = requests.post(f"{OLLAMA_API_URL}/api/chat", json=payload, timeout=45)
        if response.status_code != 200:
            return JSONResponse(
                content={"error": f"Ollama returned error status {response.status_code}", "detail": response.text}, 
                status_code=502
            )
            
        ollama_res = response.json()
        assistant_message = ollama_res.get("message", {}).get("content", "")
        
        return {"message": assistant_message, "sources": sources_metadata}
        
    except requests.exceptions.RequestException as e:
        return JSONResponse(
            content={"error": "Could not connect to Ollama server.", "detail": str(e)}, 
            status_code=503
        )

@app.get("/api/health")
async def health():
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
        
    r = get_retriever()
    kb_loaded = len(r.documents) > 0
    
    return {
        "status": "healthy",
        "database_loaded": kb_loaded,
        "database_records": len(r.documents),
        "retrieval_mode": "hybrid (BM25 + Qdrant)" if r.use_vector else "BM25 only",
        "embedding_device": r.device,
        "ollama_connection": ollama_status,
        "ollama_url": OLLAMA_API_URL,
        "ollama_model": OLLAMA_MODEL,
        "ollama_model_available": OLLAMA_MODEL in available_models or f"{OLLAMA_MODEL}:latest" in available_models,
        "available_models": available_models
    }

def cli_mode(question, retrieve_only=False):
    """CLI mode for debugging without running the web server."""
    print(f"==========================================")
    print(f"🤖 StrokeGuard CLI Mode")
    print(f"==========================================")
    print(f"Câu hỏi: {question}\n")
    
    r = get_retriever()
    docs = r.search(question, top_k=4)
    
    if retrieve_only:
        print("--- KẾT QUẢ TÌM KIẾM (RETRIEVE ONLY) ---")
        if not docs:
            print("Không tìm thấy tài liệu phù hợp.")
            return
            
        for i, doc in enumerate(docs):
            print(f"[{i+1}] {doc['title']} - {doc['section_title']}")
            print(f"Nguồn: {doc['source']}")
            print(f"Trích dẫn: {doc['content'][:300]}...\n")
        return
        
    print("... Chế độ gọi LLM qua CLI chưa được triển khai đầy đủ. Hãy dùng --retrieve-only để test RAG.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="StrokeGuard AI Backend (FastAPI)")
    parser.add_argument("--retrieve-only", action="store_true", help="Only retrieve chunks, don't use LLM")
    parser.add_argument("--question", type=str, help="Question to ask in CLI mode")
    
    args, unknown = parser.parse_known_args()
    
    if args.question:
        cli_mode(args.question, args.retrieve_only)
    else:
        import uvicorn
        port = int(os.environ.get("PORT", 5080))
        uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
