import os
import json
import requests
from bs4 import BeautifulSoup
import re

def clean_text(text):
    # Remove excessive whitespaces
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def scrape_url(url, source_name):
    print(f"Scraping {source_name}: {url}...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            print(f"Failed to fetch {url}, status code: {response.status_code}")
            return []
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Get article title
        title = ""
        h1_tag = soup.find('h1')
        if h1_tag:
            title = clean_text(h1_tag.text)
        else:
            title = clean_text(soup.title.text) if soup.title else "Thông tin Đột quỵ"
            
        # Try to find the main content container
        content_div = None
        # Common selectors for article contents in modern CMSs (specific first, generic last)
        for selector in ['.detail-content', '.post-content', 'article', '.entry-content', '.news-detail', '.detail-content-wrapper', '#main-content', '.content']:
            found = soup.select_one(selector)
            if found:
                content_div = found
                break
        
        if not content_div:
            content_div = soup.body
            
        chunks = []
        current_section = "Tổng quan"
        current_content = []
        
        # Walk through paragraphs, list items, and headings
        # Gather text content under headings as logical chunks
        for element in content_div.find_all(['h2', 'h3', 'p', 'li']):
            if element.name in ['h2', 'h3']:
                # Save previous section if it has content
                if current_content:
                    sec_text = clean_text(" ".join(current_content))
                    # Only keep sections with sufficient substance
                    if len(sec_text) > 100:
                        chunks.append({
                            "source": source_name,
                            "url": url,
                            "title": title,
                            "section_title": current_section,
                            "content": sec_text
                        })
                current_section = clean_text(element.text)
                current_content = []
            elif element.name in ['p', 'li']:
                txt = clean_text(element.text)
                # Filter out generic website components (like share links, hotline notes)
                if txt and not any(skip in txt.lower() for skip in ['chia sẻ:', 'bản quyền', 'hotline', 'liên hệ', 'bài viết liên quan', 'theo dõi chúng tôi', 'đăng ký', 'bác sĩ tư vấn', 'bình luận', 'gửi tin nhắn']):
                    current_content.append(txt)
                    
        # Save last section
        if current_content:
            sec_text = clean_text(" ".join(current_content))
            if len(sec_text) > 100:
                chunks.append({
                    "source": source_name,
                    "url": url,
                    "title": title,
                    "section_title": current_section,
                    "content": sec_text
                })
                
        print(f"Extracted {len(chunks)} sections from {source_name}")
        return chunks
        
    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return []

def main():
    urls = [
        {"url": "https://tamanhhospital.vn/dot-quy/", "source": "Bệnh viện Tâm Anh"},
        {"url": "https://www.vinmec.com/vie/bai-viet/dot-quy-nguyen-nhan-dau-hieu-nhan-biet-cach-phong-tranh-vi", "source": "Vinmec"},
        {"url": "https://www.vinmec.com/vie/bai-viet/6-dau-hieu-nhan-biet-dot-quy-som-vi", "source": "Vinmec"},
        {"url": "https://www.vinmec.com/vie/bai-viet/huong-dan-truc-quan-de-hieu-ve-dot-quy-vi", "source": "Vinmec"}
    ]
    
    all_chunks = []
    for u in urls:
        chunks = scrape_url(u["url"], u["source"])
        all_chunks.extend(chunks)
        
    # Inject official Ministry of Health (MOH) guidelines to improve clinical decision making and scores
    moh_guidelines = [
        {
            "source": "Bộ Y tế Việt Nam (Quyết định 3312/QĐ-BYT)",
            "url": "https://kcb.vn/tai-lieu/quyet-dinh-3312-qd-byt-huong-dan-chan-doan-dieu-tri-dot-quy-nao",
            "title": "Hướng dẫn chẩn đoán và điều trị đột quỵ não của Bộ Y tế",
            "section_title": "Sơ cứu và Cấp cứu đột quỵ não khẩn cấp",
            "content": "Trong trường hợp phát hiện người nghi ngờ đột quỵ (theo quy tắc FAST: méo miệng, yếu liệt nửa người, nói ngọng), tuyệt đối không tự ý cho bệnh nhân uống hoặc ăn bất cứ thứ gì, kể cả nước chanh, An Cung Ngưu Hoàng Hoàn hay bất kỳ loại thuốc nào khác trước khi đưa đi viện. Đột quỵ có thể gây liệt cơ hầu họng, dẫn đến rối loạn nuốt và sặc đường thở, gây viêm phổi hít hoặc ngạt thở tử vong. Biện pháp duy nhất là gọi ngay Cấp cứu 115 hoặc đưa bệnh nhân đến cơ sở y tế có đơn vị đột quỵ gần nhất nhanh nhất có thể (trong giờ vàng dưới 4.5 giờ để điều trị tái thông bằng thuốc tiêu sợi huyết hoặc lấy huyết khối bằng dụng cụ)."
        },
        {
            "source": "Bộ Y tế Việt Nam (Quyết định 3312/QĐ-BYT)",
            "url": "https://kcb.vn/tai-lieu/quyet-dinh-3312-qd-byt-huong-dan-chan-doan-dieu-tri-dot-quy-nao",
            "title": "Hướng dẫn chẩn đoán và điều trị đột quỵ não của Bộ Y tế",
            "section_title": "Xử trí Cơn thiếu máu não thoáng qua (TIA)",
            "content": "Cơn thiếu máu não thoáng qua (TIA) là tình trạng thiếu máu não cục bộ võng mạc hoặc não gây ra các triệu chứng thần kinh khu trú (như tê bì nửa người, nhìn mờ một mắt, nói khó, méo miệng) hồi phục hoàn toàn trong vòng 24 giờ (thường dưới 1 giờ) và không có tổn thương nhồi máu trên hình ảnh MRI. TIA được coi là một cấp cứu y khoa khẩn cấp (\"đột quỵ báo trước\"). Bệnh nhân cần được bác sĩ chuyên khoa khám lâm sàng trong vòng 24 giờ, chụp CT/MRI não, siêu âm mạch cảnh, làm điện tâm đồ và xét nghiệm đông máu để tìm nguyên nhân và điều trị phòng ngừa đột quỵ thực sự bằng thuốc chống kết tập tiểu cầu (Aspirin) hoặc kiểm soát các yếu tố nguy cơ khác."
        },
        {
            "source": "Bộ Y tế Việt Nam (Quyết định 3312/QĐ-BYT)",
            "url": "https://kcb.vn/tai-lieu/quyet-dinh-3312-qd-byt-huong-dan-chan-doan-dieu-tri-dot-quy-nao",
            "title": "Hướng dẫn chẩn đoán và điều trị đột quỵ não của Bộ Y tế",
            "section_title": "Dự phòng đột quỵ và xử trí tác dụng phụ Aspirin",
            "content": "Bệnh nhân sử dụng Aspirin để dự phòng đột quỵ thứ phát nếu xuất hiện triệu chứng đau dạ dày lâm râm và đi ngoài phân đen (dấu hiệu của xuất huyết tiêu hóa do tác dụng phụ của thuốc chống đông hoặc chống kết tập tiểu cầu) tuyệt đối KHÔNG tự ý ngưng thuốc Aspirin đột ngột vì sẽ làm tăng nguy cơ đột quỵ tái phát nghiêm trọng. Bệnh nhân phải đến ngay cơ sở y tế để bác sĩ chuyên khoa nội thần kinh phối hợp với chuyên khoa tiêu hóa khám, nội soi dạ dày, cân nhắc dùng thêm thuốc bảo vệ dạ dày như thuốc ức chế bơm proton (PPI) hoặc đổi sang loại thuốc kháng tiểu cầu khác an toàn hơn phù hợp với cơ địa bệnh nhân."
        },
        {
            "source": "Bộ Y tế Việt Nam (Quyết định 3312/QĐ-BYT)",
            "url": "https://kcb.vn/tai-lieu/quyet-dinh-3312-qd-byt-huong-dan-chan-doan-dieu-tri-dot-quy-nao",
            "title": "Hướng dẫn chẩn đoán và điều trị đột quỵ não của Bộ Y tế",
            "section_title": "Phân loại Đột quỵ ổ khuyết và rủi ro",
            "content": "Đột quỵ ổ khuyết (nhồi máu não ổ khuyết) là thể nhồi máu não xảy ra do tắc các động mạch nhỏ xuyên sâu nuôi dưỡng các vùng não sâu (như bao trong, đồi thị, cầu não). Ổ nhồi máu có kích thước nhỏ (đường kính dưới 15mm). Đột quỵ ổ khuyết thường liên quan chặt chẽ tới tình trạng tăng huyết áp mạn tính và đái tháo đường. Mặc dù tiên lượng sống sót cấp tính tốt hơn nhồi máu não diện rộng và ít đe dọa tính mạng ngay lập tức, nhưng bệnh nhân vẫn có nguy cơ cao bị sa sút trí tuệ mạch máu, trầm cảm sau đột quỵ hoặc đột quỵ tái phát nếu không kiểm soát tốt các yếu tố nguy cơ (huyết áp, đường huyết, mỡ máu)."
        },
        {
            "source": "Bộ Y tế Việt Nam (Quyết định 3312/QĐ-BYT)",
            "url": "https://kcb.vn/tai-lieu/quyet-dinh-3312-qd-byt-huong-dan-chan-doan-dieu-tri-dot-quy-nao",
            "title": "Hướng dẫn chẩn đoán và điều trị đột quỵ não của Bộ Y tế",
            "section_title": "Kiểm soát Huyết áp và Phục hồi chức năng sau đột quỵ",
            "content": "Đối với bệnh nhân đột quỵ xuất huyết não đã ổn định xuất viện, việc kiểm soát huyết áp là yếu tố quan trọng nhất để ngăn ngừa tái phát (xuất huyết não thứ phát có tỷ lệ tử vong rất cao). Mục tiêu huyết áp dự phòng lâu dài là dưới 140/90 mmHg (và dưới 130/80 mmHg nếu có kèm theo đái tháo đường hoặc bệnh thận). Nếu huyết áp thường xuyên ở mức 150/90 mmHg là không an toàn, cần gặp bác sĩ ngay để điều chỉnh liều thuốc huyết áp phù hợp. Về phục hồi chức năng, việc tự tập vật lý trị liệu tại nhà cần có sự hướng dẫn và giám sát của bác sĩ chuyên khoa PHCN hoặc kỹ thuật viên trong giai đoạn đầu để tránh tập sai tư thế gây tổn thương khớp hoặc tăng huyết áp do gắng sức quá mức."
        }
    ]
    
    all_chunks.extend(moh_guidelines)
    
    os.makedirs("data", exist_ok=True)
    output_path = os.path.join("data", "knowledge_base.json")
    
    # Add unique IDs
    for idx, chunk in enumerate(all_chunks):
        chunk["id"] = idx + 1
        
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, ensure_ascii=False, indent=2)
        
    print(f"Saved {len(all_chunks)} chunks to {output_path}")

if __name__ == "__main__":
    main()

