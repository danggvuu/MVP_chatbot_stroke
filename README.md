# 🛡️ StrokeGuard AI - Trợ lý Sơ cứu Đột quỵ (CARDS RAG MVP)

**StrokeGuard AI** là một hệ thống chatbot y khoa trợ giúp sơ cứu và tư vấn đột quỵ dựa trên Hướng dẫn của Bộ Y tế (Quyết định 3312/QĐ-BYT) và dữ liệu y khoa từ Vinmec & Bệnh viện Tâm Anh. Hệ thống sử dụng mô hình RAG Lexical (BM25) nâng cấp tách từ tiếng Việt để đảm bảo độ chính xác y tế tối đa.

---

## 🚀 Hướng dẫn Khởi chạy Nhanh

### Cách 1: Chạy bằng Docker (Khuyên dùng)
*Đảm bảo ứng dụng chạy ổn định và độc lập trên cổng 5050.*

1. Đảm bảo đã bật **Docker Desktop** và đã tải mô hình `llama3.2` trên Ollama cục bộ (`ollama run llama3.2`).
2. Chạy lệnh tại thư mục dự án:
   ```bash
   docker-compose up -d --build
   ```
3. Truy cập địa chỉ: 👉 **[http://localhost:5050](http://localhost:5050)**

---

### Cách 2: Chạy trực tiếp bằng Python
*Chạy trên môi trường ảo Python cục bộ trên cổng 5080.*

1. ** macOS / Linux:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   python3 app.py
   ```
2. ** Windows:**
   ```cmd
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   python app.py
   ```
3. Truy cập địa chỉ: 👉 **[http://localhost:5080](http://localhost:5080)**

---

## 📂 Cấu trúc Thư mục chính

*   `app.py`: Backend Flask điều phối chat, SSE streaming, và gọi Ollama API.
*   `retrieval.py`: Bộ máy tìm kiếm RAG sử dụng thuật toán BM25 nâng cấp và bộ lọc từ dừng tiếng Việt.
*   `scraper.py`: Công cụ cào và làm sạch dữ liệu y khoa tự động từ Vinmec và Bệnh viện Tâm Anh.
*   `evaluate_stroke_chatbot_2026.py`: Bộ khung đánh giá lâm sàng tự động (LLM-as-a-judge) với 5 ca lâm sàng phức tạp.
*   `static/`: Chứa file giao diện CSS (glassmorphism), JS (SSE client, interactive citations) và sơ đồ kiến trúc động.
*   `templates/`: Giao diện HTML của chatbot.

---

## ⚙️ Điểm nhấn Kỹ thuật cốt lõi (Chuẩn bị Phỏng vấn)

1.  **Tách từ tiếng Việt (Vietnamese Segmentation)**: Sử dụng thư viện `underthesea` liên kết các từ ghép (như `đột_quỵ`, `nhồi_máu_não`), ngăn chặn lỗi chia nhỏ từ của tokenizer tiếng Anh làm hỏng ngữ nghĩa.
2.  **Bộ lọc từ dừng y khoa (Stopwords Filter)**: Lọc bỏ các từ chức năng phổ biến (`và`, `hoặc`, `như thế nào`, `m`, `k`...) để loại bỏ nhiễu tìm kiếm, giải quyết triệt để hiện tượng lấy nhầm văn bản y khoa khi hỏi câu hỏi ngoài chủ đề.
3.  **Thuật toán BM25 & Sentence-Split Interleaving**:
    *   Sử dụng BM25 chuẩn hóa độ dài văn bản (`k1=1.2`, `b=0.75`).
    *   Tự động tách câu hỏi nhiều ý của người dùng thành các câu đơn, chạy BM25 độc lập rồi trộn xen kẽ (interleave) kết quả để đảm bảo ngữ cảnh của tất cả các ý đều được truyền vào LLM.
4.  **Interactive Citation Links (Liên kết ngược bằng chứng)**: Tự động chuyển đổi các trích dẫn `[1]`, `[2]` trong câu trả lời thành link hoạt họa. Khi nhấp vào, giao diện sẽ cuộn mượt và kích hoạt hiệu ứng chớp sáng (highlight flash) thẻ tài liệu tham khảo tương ứng ở thanh bên.
5.  **Thời gian phản hồi siêu tốc**: Tích hợp luồng dữ liệu Server-Sent Events (SSE) streaming giúp giảm thời gian phản hồi từ LLM xuống dưới 0.5 giây.

---

## 🔬 Chạy thử nghiệm Đánh giá Lâm sàng (Clinical Evaluation)

Hệ thống tích hợp bộ đánh giá tự động dựa trên Framework nghiên cứu lâm sàng 2026 (Đạt **100% điểm số an toàn y khoa**):

```bash
# Đánh giá bằng Ollama cục bộ (llama3.2):
python evaluate_stroke_chatbot_2026.py

# Đánh giá nâng cao bằng Cloud API (Gemini/OpenAI):
export GEMINI_API_KEY="your_gemini_key"
python evaluate_stroke_chatbot_2026.py
```
Kết quả báo cáo chi tiết sẽ được tự động xuất ra file `data/evaluation_report_2026.md`.
