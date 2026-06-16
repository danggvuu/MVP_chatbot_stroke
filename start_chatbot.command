#!/bin/bash

# Lấy đường dẫn thư mục hiện tại của file script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "=========================================="
echo "🚀 Đang khởi động StrokeGuard AI Chatbot..."
echo "=========================================="

# Kiểm tra và kích hoạt môi trường ảo (venv)
if [ -d "venv" ]; then
    echo "[1/2] Đang kích hoạt môi trường ảo..."
    source venv/bin/activate
fi

# Chạy ngầm lệnh mở trình duyệt sau khi đợi server khởi động (2 giây)
(sleep 2 && open http://127.0.0.1:5080) &

# Chạy ứng dụng Flask
echo "[2/2] Đang chạy ứng dụng..."
echo "🌐 Trình duyệt sẽ tự động bật lên sau 2 giây..."
echo "------------------------------------------"
python3 main.py
