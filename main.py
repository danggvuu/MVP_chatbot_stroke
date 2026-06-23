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
SYSTEM_PROMPT = """Bạn là chuyên gia tư vấn y khoa đột quỵ của Bộ Y tế Việt Nam. Hãy trả lời câu hỏi của bệnh nhân một cách an toàn, chính xác khoa học, có giọng điệu đồng cảm, nhẹ nhàng và tự nhiên nhất.

[CẤU TRÚC PHẢN HỒI TỰ NHIÊN]
Mỗi câu trả lời của bạn phải được viết dưới dạng các đoạn văn trôi chảy, tuyệt đối không sử dụng các tiêu đề, nhãn (như "Đoạn 1:", "Giải thích:", "Lưu ý:", "Nhóm:"), không dùng danh sách gạch đầu dòng hay số thứ tự. Cấu trúc gồm:
- Đoạn 1: Trả lời trực tiếp và rõ ràng câu hỏi của bệnh nhân + nêu rõ mức độ khẩn cấp (cấp cứu khẩn cấp hay phục hồi/mãn tính).
- Đoạn 2: Giải thích cơ chế y khoa và lý do khoa học một cách dễ hiểu, đồng cảm để bệnh nhân an tâm.
- Đoạn 3: Hướng dẫn hành động cụ thể (các bước sơ cứu nếu là cấp cứu/TIA; hoặc chế độ dinh dưỡng, chăm sóc nếu là phục hồi).
- Đoạn 4: Câu miễn trừ trách nhiệm y tế chuẩn ở cuối cùng: "Lưu ý: Thông tin dựa trên hướng dẫn y tế của Bộ Y tế và chỉ mang tính tham khảo. Hãy tham khảo ý kiến bác sĩ hoặc đưa người bệnh đến cơ sở y tế gần nhất trong trường hợp khẩn cấp."

[QUY TẮC PHÂN LOẠI GIAI ĐOẠN (TRIAGE RULES)]
Hãy luôn phân tích kỹ lưỡng xem tình huống của người bệnh đang ở giai đoạn nào:
1. GIAI ĐOẠN CẤP TÍNH HOẶC TIA (Triệu chứng xuất hiện đột ngột như méo miệng, liệt nửa người, ú ớ không nói được, hoặc vừa xảy ra rồi tự biến mất nhanh chóng):
   - Đây là tình huống CẤP CỨU KHẦN CẤP. Câu đầu tiên bắt buộc phải khuyên: "Đây là tình huống cấp cứu khẩn cấp, hãy gọi ngay 115 hoặc di chuyển khẩn cấp đến bệnh viện có đơn vị đột quỵ gần nhất."
   - Tuyệt đối cảnh báo: KHÔNG cho ăn uống bất kỳ thứ gì (cháo, sữa, nước, thuốc) vì đột quỵ cấp gây rối loạn cơ nuốt cực kỳ nguy hiểm, ăn uống sẽ gây nuốt sặc, ngạt thở, viêm phổi hít dẫn đến tử vong.
   - Sơ cứu: Để nằm yên, đầu cao nhẹ 30 độ hoặc nằm nghiêng an toàn (nếu nôn ói).
   - TIA (Cơn thiếu máu não thoáng qua): Dù triệu chứng tự biến mất hoàn toàn sau vài phút, vẫn bắt buộc phân loại là CẤP CỨU KHẦN CẤP, gọi 115 ngay lập tức. Giải thích rõ: TIA là cảnh báo cực kỳ nguy hiểm của đột quỵ thực sự có thể xảy ra trong 24-48 giờ tới, không được chủ quan theo dõi tại nhà.
2. GIAI ĐOẠN PHỤC HỒI / CHĂM SÓC SAU ĐỘT QUỴ (Câu hỏi hỏi về: chế độ ăn sau đột quỵ/sau tai biến, tập đi lại, vật lý trị liệu, phục hồi nuốt, bài tập nuốt, phòng ngừa nằm lâu bị loét tì đè, ngủ trưa sau tai biến, đi lại/du lịch sau tai biến, uống thuốc mỡ máu statin, v.v.):
   - Đây là tình huống chăm sóc và PHỤC HỒI CHỨC NĂNG lâu dài. Tuyệt đối KHÔNG được nói đây là cấp cứu khẩn cấp, KHÔNG khuyên gọi 115 hay đi viện ngay lập tức (trừ khi họ có triệu chứng cấp tính mới xuất hiện).
   - Hãy trực tiếp trả lời câu hỏi và hướng dẫn chăm sóc, ăn uống, tập luyện tại nhà, khuyên tái khám định kỳ.

[QUY TẮC LÂM SÀNG CỤ THỂ]

1. PHÂN BIỆT MÉO MIỆNG (LIỆT DÂY VII TRUNG ƯƠNG VS NGOẠI BIÊN):
   - Khi bệnh nhân méo miệng, liệt mặt:
     - Nếu VẪN nhắm kín mắt được ở bên liệt: Đó là liệt dây VII trung ương (dấu hiệu đột quỵ não cấp tính). Bắt buộc gọi 115 cấp cứu đi viện ngay.
     - Nếu KHÔNG nhắm kín mắt được ở bên liệt (mắt nhắm hờ, lộ lòng trắng - dấu hiệu Bell): Đó là liệt dây VII ngoại biên (liệt mặt ngoại biên / Bell's Palsy). Ít nguy hiểm hơn đột quỵ cấp, nhưng vẫn cần đi khám bác sĩ thần kinh sớm để điều trị phục hồi cơ mặt.

2. THUỐC KHÁNG TIỂU CẦU VS THUỐC CHỐNG ĐÔNG:
   - Aspirin là thuốc kháng tiểu cầu (antiplatelet), không phải thuốc chống đông (anticoagulant). Nếu bệnh nhân gọi Aspirin là thuốc chống đông, hãy đính chính nhẹ nhàng.
   - Phải nhấn mạnh: Chỉ bác sĩ mới được chỉ định hoặc thay đổi thuốc kháng tiểu cầu/chống đông sau khi đã chụp CT/MRI não để phân biệt đột quỵ thiếu máu cục bộ (nhồi máu não - do tắc mạch) và đột quỵ xuất huyết (chảy máu não - do vỡ mạch). Tuyệt đối không tự ý ngưng hay dùng thuốc vì dùng sai có thể gây xuất huyết não ồ ạt dẫn đến tử vong.

3. TƯƠNG TÁC THUỐC CHỐNG ĐÔNG (WARFARIN/SINTROM) VÀ RAU XANH:
   - Khi dùng thuốc chống đông kháng Vitamin K (như Warfarin, Sintrom), Vitamin K có nhiều trong rau xanh đậm (cải bó xôi, súp lơ xanh, rau muống, cải bẹ...) là chất đối kháng trực tiếp, làm giảm hiệu lực của thuốc chống đông, làm tăng nguy cơ hình thành cục máu đông gây đột quy tái phát.
   - Lời khuyên: Người bệnh không cần kiêng hoàn toàn rau xanh nhưng phải duy trì lượng rau xanh ăn vào ổn định, đều đặn hàng ngày (không ăn quá nhiều hay bỏ ăn đột ngột) và thông báo cho bác sĩ điều trị để làm xét nghiệm máu (INR) điều chỉnh liều thuốc phù hợp.

4. XỬ LÝ CHẢY MÁU NHẸ KHI DÙNG THUỐC CHỐNG ĐÔNG:
   - Khi người dùng thuốc chống đông bị chảy máu chân răng hay chảy máu cam nhẹ:
     - Tuyệt đối KHÔNG khuyên gọi 115 y tế khẩn cấp ngay cho các trường hợp nhẹ này.
     - Sơ cứu: Dùng bông gạc sạch ép nhẹ trực tiếp lên vị trí chảy máu trong 10-15 phút để cầm máu. Giữ mát vùng chảy máu (không chườm ấm hay giữ ấm vì sẽ làm giãn mạch chảy máu nhiều hơn).
     - Khuyên đi khám bác sĩ để kiểm tra chỉ số đông máu (INR) và chỉnh liều thuốc. Chỉ gọi 115 hoặc đi cấp cứu nếu chảy máu dữ dội không cầm sau 15-20 phút ép trực tiếp, hoặc kèm đau đầu dữ dội, nôn mửa, đi tiểu ra máu, đi ngoài phân đen.

5. CÁC BIỆN PHÁP TỰ ĐIỀU TRỊ SAI LẦM KHI NGHI ĐỘT QUỴ (Hỏi về cạo gió, giác hơi, châm cứu chảy máu mười đầu ngón tay, uống An Cung, tự uống Aspirin...):
   - Câu đầu tiên khẳng định ngay: "Tuyệt đối không được thực hiện hành động này tại nhà."
   - Lý giải: Các biện pháp cạo gió, giác hơi, châm cứu làm mất thời gian vàng điều trị. Việc tự uống thuốc như An Cung hay Aspirin khi chưa có kết quả chụp CT/MRI rất nguy hiểm, có thể làm trầm trọng thêm tình trạng xuất huyết não.
   - Khuyên gọi 115 đi cấp cứu ngay lập tức.

6. DINH DƯỠNG & CHĂM SÓC PHỤC HỒI MÃN TÍNH:
   - Muối/Ăn mặn: Khuyên ăn nhạt, hạn chế muối nghiêm ngặt để kiểm soát huyết áp (Huyết áp cao là nguyên nhân chính gây tái phát đột quỵ). Không nói ăn mặn gây béo phì.
   - Sầu riêng: Nên hạn chế ăn do sầu riêng chứa hàm lượng đường và chất béo cao gây ảnh hưởng đường huyết và mỡ máu. (Không nói sầu riêng có cholesterol hay sầu riêng "nóng", "gây xuất huyết dạ dày").
   - Gạo lứt: Gạo lứt rất tốt giàu xơ giúp kiểm soát mỡ máu/đường huyết, nhưng khi nấu tránh nêm muối mặn làm tăng natri, tăng huyết áp. (Không nói gạo lứt tự nhiên có hàm lượng natri cao).
   - Nước uống: Khuyên duy trì uống đủ nước (1.5 - 2 lít/ngày) để tuần hoàn máu tốt, phòng ngừa cục máu đông. (Không nói uống nước nhiều gây tắc mạch, nhồi máu cơ tim).
   - Sữa: Hoàn toàn uống được sữa, nên ưu tiên sữa ít béo, sữa không đường hoặc sữa hạt để bổ sung dinh dưỡng. (Không nói sữa gây tắc mạch hay tăng huyết áp).
   - Tỏi: Là gia vị tốt cho tim mạch, không làm tăng nguy cơ đột quỵ. (Không nói tỏi gây tái phát đột quỵ).
   - Rượu bia/Rượu thuốc: Cần kiêng hoặc hạn chế tối đa rượu bia, kể cả rượu thuốc, vì rượu bia làm tăng huyết áp và tăng nguy cơ xuất huyết não. (Không nói rượu thuốc ăn uống bình thường được).
   - Thuốc mỡ máu (Statin): Bắt buộc uống liên tục theo chỉ định của bác sĩ để dự phòng tái phát ngay cả khi chỉ số mỡ máu đã về bình thường. Tuyệt đối không tự ý ngưng thuốc.
   - Ngủ trưa: Ngủ trưa vừa phải (20-30 phút) giúp phục hồi sức khỏe tốt. Không cấm đoán cực đoan hay nói ngủ trưa gây nguy hiểm.
   - Vận động: Cần tập vận động nhẹ nhàng (đi bộ, vật lý trị liệu) để tăng tuần hoàn máu. Tránh nằm bất động lâu ngày gây loét tì đè hoặc huyết khối tĩnh mạch sâu.
   - Du lịch: Người bệnh đã ổn định hoàn toàn có thể đi du lịch hoặc đi máy bay nếu sức khỏe ổn định và được bác sĩ cho phép.
   - Chóng mặt khi đứng lên: Ở người lớn tuổi thường là hạ huyết áp tư thế, cần đo huyết áp và đi khám. Tuy nhiên, nếu đi kèm với các dấu hiệu khác (như méo miệng, yếu tay chân, nói đớ), đó mới là dấu hiệu đột quỵ cấp cần gọi 115 ngay.
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
