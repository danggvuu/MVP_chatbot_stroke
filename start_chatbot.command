#!/bin/bash
# ============================================================
# 🧠 StrokeGuard AI - Khởi động nhanh (macOS)
# ============================================================

# Lấy đường dẫn thư mục chứa script này
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "  🧠  ╔══════════════════════════════════════════╗"
echo "      ║     StrokeGuard AI - Khởi động nhanh     ║"
echo "      ║   Hệ thống Tư vấn Sơ cứu Đột quỵ       ║"
echo "      ╚══════════════════════════════════════════╝"
echo ""

# --- 1. Kiểm tra Python ---
if ! command -v python3 &> /dev/null; then
    echo "  ❌  Python3 chưa được cài đặt!"
    echo "      Tải tại: https://www.python.org/downloads/"
    echo ""
    read -p "  Nhấn Enter để thoát..."
    exit 1
fi
PYTHON_CMD="python3"
echo "  ✅  Python:  $($PYTHON_CMD --version)"

# --- 2. Tạo virtual environment nếu chưa có ---
if [ ! -d "venv" ]; then
    echo "  ⏳  Đang tạo virtual environment..."
    $PYTHON_CMD -m venv venv
    echo "  ✅  Đã tạo venv/"
fi

# Kích hoạt venv
source venv/bin/activate
echo "  ✅  Đã kích hoạt virtual environment"

# --- 3. Cài đặt dependencies ---
echo "  ⏳  Kiểm tra và cài đặt dependencies..."
pip install -r requirements.txt -q 2>&1 | tail -1
echo "  ✅  Dependencies đã sẵn sàng"

# --- 4. Kiểm tra knowledge base ---
if [ ! -f "data/knowledge_base.json" ]; then
    echo ""
    echo "  ⏳  Chưa có knowledge base. Đang cào dữ liệu y khoa..."
    $PYTHON_CMD data_pipeline/scraper.py
    echo ""
fi
CHUNK_COUNT=$(python3 -c "import json; print(len(json.load(open('data/knowledge_base.json'))))" 2>/dev/null || echo "0")
echo "  ✅  Knowledge Base: $CHUNK_COUNT phân đoạn y khoa"

# --- 5. Kiểm tra Ollama ---
echo ""
OLLAMA_MODEL="${OLLAMA_MODEL:-qwen2.5:3b}"
if command -v ollama &> /dev/null; then
    echo "  ✅  Ollama đã cài đặt"
    if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo "  ✅  Ollama server đang chạy"
        # Kiểm tra model
        if ollama list 2>/dev/null | grep -q "$OLLAMA_MODEL"; then
            echo "  ✅  Model $OLLAMA_MODEL đã sẵn sàng"
        else
            echo "  ⚠️  Model $OLLAMA_MODEL chưa tải. Đang tải..."
            ollama pull "$OLLAMA_MODEL"
        fi
    else
        echo "  ⚠️  Ollama chưa chạy. Đang khởi động..."
        ollama serve &> /dev/null &
        sleep 2
        if ! ollama list 2>/dev/null | grep -q "$OLLAMA_MODEL"; then
            echo "  ⏳  Đang tải model $OLLAMA_MODEL (lần đầu có thể mất vài phút)..."
            ollama pull "$OLLAMA_MODEL"
        fi
        echo "  ✅  Ollama đã khởi động"
    fi
else
    echo "  ⚠️  Ollama chưa cài đặt!"
    echo "      Tải tại: https://ollama.com/download"
    echo "      Sau khi cài, chạy: ollama pull $OLLAMA_MODEL"
    echo ""
    echo "  ⏳  Server vẫn sẽ khởi động nhưng chatbot sẽ không trả lời được."
fi

# --- 6. Khởi động server ---
echo ""
echo "  ╔══════════════════════════════════════════╗"
echo "  ║  🚀  Khởi động StrokeGuard AI Server... ║"
echo "  ║  📍  http://localhost:5080               ║"
echo "  ║  📄  API Docs: http://localhost:5080/docs║"
echo "  ║  ⏹   Nhấn Ctrl+C để tắt server          ║"
echo "  ╚══════════════════════════════════════════╝"
echo ""

# Mở trình duyệt sau 2 giây
(sleep 2 && open "http://localhost:5080") &

# Chạy FastAPI server
$PYTHON_CMD main.py
