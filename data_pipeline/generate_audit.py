import json
import os
from datetime import datetime

def generate_audit():
    kb_path = "../data/knowledge_base.json"
    audit_path = "../data/data_audit.json"
    
    # Đảm bảo đường dẫn chính xác dựa trên vị trí file hiện tại
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    if not os.path.exists(kb_path):
        print(f"❌ Không tìm thấy file {kb_path}. Hãy chạy scraper.py trước.")
        return
        
    with open(kb_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    audit_records = {}
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    # Quét qua các chunks để tổng hợp theo Nguồn (Source)
    for doc in data:
        source_name = doc.get("source", "Unknown Source")
        if source_name not in audit_records:
            # Gán trạng thái Active mặc định cho các tài liệu mới
            # Trong môi trường thực tế, cờ Active sẽ do bác sĩ đánh giá và quyết định
            audit_records[source_name] = {
                "source_name": source_name,
                "url": doc.get("url", ""),
                "chunks_count": 0,
                "status": "Active",
                "version": "Mới nhất",
                "last_audited": current_date,
                "notes": "Phác đồ/Tài liệu đang có hiệu lực. Hệ thống chỉ RAG trên tài liệu Active."
            }
        audit_records[source_name]["chunks_count"] += 1
        
    # Lưu kết quả Audit
    with open(audit_path, 'w', encoding='utf-8') as f:
        json.dump(list(audit_records.values()), f, ensure_ascii=False, indent=4)
        
    print(f"✅ Đã tạo Medical Audit Log với {len(audit_records)} tài liệu y khoa.")
    print(f"📁 Vị trí file: {os.path.abspath(audit_path)}")

if __name__ == "__main__":
    generate_audit()
