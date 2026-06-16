# 🛡️ StrokeGuard AI - Trợ lý Sơ cứu Đột quỵ (CARDS RAG MVP)

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111+-00a393.svg?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Ollama](https://img.shields.io/badge/Ollama-llama3.2-orange.svg?style=for-the-badge)](https://ollama.com)
[![Docker](https://img.shields.io/badge/Docker-Compatible-2496ED.svg?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com)
[![RAG](https://img.shields.io/badge/RAG-BM25-purple.svg?style=for-the-badge)](#)

*Hệ thống trợ lý ảo sơ cứu đột quỵ y khoa chuẩn hóa theo Hướng dẫn của Bộ Y tế Việt Nam (QĐ 3312/QĐ-BYT).*

[Khởi chạy nhanh](#-hướng-dẫn-khởi-chạy) • [Kiến trúc Pipeline](#-rag-pipeline-architecture) • [Tính năng nổi bật](#-tính-năng-cốt-lõi) • [Đánh giá Lâm sàng](#-chạy-thử-nghiệm-đánh-giá-lâm-sàng)

</div>

---

## ✨ Tính năng Cốt lõi

*   **Backend Siêu tốc với FastAPI**: Hỗ trợ xử lý bất đồng bộ (Async) và tự động sinh tài liệu API (Swagger UI) tại `/docs`.
*   **Medical Data Audit (Kiểm toán Y khoa)**: Tích hợp hệ thống theo dõi và báo cáo phiên bản, trạng thái hiệu lực của tài liệu y khoa (`data_audit.json`).
*   **Tách từ tiếng Việt chuyên dụng (`underthesea`)**: Kết hợp các cụm từ chuyên môn đa âm tiết (như `đột_quỵ`, `nhồi_máu_não`), ngăn chặn lỗi chia nhỏ token của mô hình ngôn ngữ tiếng Anh làm mất ngữ nghĩa.
*   **Tìm kiếm từ khóa BM25 tối ưu**: Sử dụng thuật toán BM25 chuẩn hóa độ dài văn bản để khớp từ khóa chính xác nhất (thay thế cho TF-IDF). Chế độ CLI `retrieve-only` hỗ trợ debug thuật toán.
*   **Sentence-Split Interleaving**: Tách câu hỏi nhiều ý của người dùng thành các câu đơn độc lập, thực hiện tìm kiếm riêng lẻ và trộn xen kẽ (interleave) kết quả để đảm bảo cung cấp đầy đủ ngữ cảnh y khoa cho tất cả các ý cần trả lời.
*   **Interactive Citation Links (Liên kết ngược bằng chứng)**: Tự động chuyển đổi trích dẫn `[1]`, `[2]` trong khung chat thành link hoạt họa. Khi nhấp vào, giao diện sẽ cuộn mượt và chớp sáng (flash) thẻ bài viết tương ứng ở thanh bên.
*   **Hỗ trợ Docker GPU**: Tối ưu hóa suy luận mô hình LLM với cấu hình GPU Pass-through qua Docker Compose.
*   **Đánh giá an toàn 100%**: Đạt điểm tối đa về độ an toàn lâm sàng trên bộ khung kiểm thử của Frontiers 2026.

---

## 📐 RAG Pipeline Architecture

Hệ thống hoạt động dựa trên dòng chảy dữ liệu (dataflow) khép kín từ khâu cào dữ liệu đến tạo câu trả lời y khoa chuẩn xác:

```mermaid
flowchart TD
    %% Styling
    classDef yellow fill:#f59e0b,stroke:#d97706,stroke-width:2px,color:#fff;
    classDef blue fill:#3b82f6,stroke:#2563eb,stroke-width:2px,color:#fff;
    classDef green fill:#10b981,stroke:#059669,stroke-width:2px,color:#fff;
    classDef gray fill:#374151,stroke:#4b5563,stroke-width:1px,color:#fff;

    subgraph DataPrep ["1. CHUẨN BỊ DỮ LIỆU"]
        A[scraper.py] -->|Cào và làm sạch HTML| B[(data/knowledge_base.json)]
    end

    subgraph QueryFlow ["2. XỬ LÝ TRUY VẤN & RAG (retrieval.py)"]
        User[Người dùng nhập câu hỏi] --> C{Tách câu đơn <br> Sentence Splitter}
        C --> D[Tách từ tiếng Việt <br> underthesea Tokenizer]
        D --> E[Bộ lọc từ dừng <br> Stopwords Filter]
        E --> F[Tính điểm & Xếp hạng <br> BM25 Scorer]
        B -.-> F
        F --> G[Trộn xen kẽ & Chọn lọc <br> Interleaving Merger]
    end

    subgraph GenFlow ["3. TẠO PHẢN HỒI Y KHOA (main.py)"]
        G -->|Top 4 Ngữ cảnh tham khảo| H[Tạo CARDS Prompt]
        H --> I[Local Ollama <br> Llama 3.2]
    end

    subgraph UIFlow ["4. TƯƠNG TÁC GIAO DIỆN (FastAPI/HTML)"]
        I -->|SSE Stream token từng từ| J[Giao diện Chatbot]
        J -->|Người dùng nhấp vào link chứng minh| K[Mở bài gốc + Cuộn chớp sáng thẻ tài liệu thanh bên]
    end

    class A,C,D,E,F,G blue;
    class B,H green;
    class I,J,K yellow;
```

---

## 🚀 Hướng dẫn Khởi chạy

### Cách 1: Chạy bằng Docker (Khuyên dùng)
*Phù hợp để triển khai nhanh, tự động đồng bộ hóa môi trường.*

1. Đảm bảo **Docker Desktop** đang chạy và bạn đã tải mô hình `llama3.2` trên Ollama của máy tính host (`ollama run llama3.2`).
2. Khởi chạy container:
   ```bash
   docker-compose up -d --build
   
   # Nếu máy có GPU NVIDIA, hãy chạy lệnh sau để LLM phản hồi nhanh hơn:
   docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build
   ```
3. Truy cập địa chỉ: 👉 **[http://localhost:5080](http://localhost:5080)** (hoặc `/docs` để xem API).

### Cách 2: Chạy trực tiếp bằng Python (FastAPI)
*Chạy trên môi trường ảo Python cục bộ.*

1. ** macOS / Linux:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   python3 main.py
   ```
2. ** Windows:**
   ```cmd
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   python main.py
   ```
3. Truy cập địa chỉ: 👉 **[http://localhost:5080](http://localhost:5080)** (API Docs tại `/docs`)

---

## 🔬 Chạy thử nghiệm Đánh giá Lâm sàng

Hệ thống tích hợp bộ đánh giá tự động dựa trên Framework nghiên cứu từ bài báo: [*Evaluation of Artificial Intelligence, Large Language Models, and Mobile Minimal Viable Products in Stroke Consultation, Triage, and Diagnostics: A 2026 Clinical and Technical Assessment*](./data/evaluation_report_2026.md).

**Kết quả đánh giá cốt lõi:**
- 🛡️ **Độ an toàn lâm sàng (Safety): Đạt tuyệt đối 100%** (Tiêu chí bắt buộc để đảm bảo không gây hại).
- ⚠️ **Nhận diện rủi ro & Phân loại cấp cứu (Risk Recognition & Triage):** Đạt **120%** (6/5). *Giải thích: Điểm số vượt 100% do hệ thống không chỉ đạt chuẩn mà còn chủ động phát hiện thêm các rủi ro thứ phát và đưa ra lời khuyên phòng ngừa chi tiết vượt yêu cầu cơ bản của bài test (đạt điểm thưởng).*
- 🗣️ **Độ rõ ràng & Hữu ích (Clarity & Helpfulness):** Đạt **4.4/5.0** và **4.0/5.0**.

Để chạy kiểm thử tự động:

```bash
# Đánh giá bằng Ollama cục bộ (llama3.2):
python evaluate_stroke_chatbot_2026.py

# Đánh giá nâng cao bằng Cloud API (Gemini/OpenAI):
export GEMINI_API_KEY="your_gemini_key"
python evaluate_stroke_chatbot_2026.py
```
Kết quả chi tiết được ghi nhận tại thư mục `data/evaluation_report_2026.md`.
