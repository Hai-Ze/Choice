import asyncio
import os
import json
import re
from crawl4ai import AsyncWebCrawler
from bs4 import BeautifulSoup

def get_folder_names(base_path):
    if not os.path.exists(base_path):
        return []
    return [d for d in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, d))]

async def update_exam_info(folder_names, base_path):
    # Chia nhỏ danh sách thư mục thành từng nhóm 10 cái để tránh lỗi trình duyệt Playwright
    batch_size = 10
    total = len(folder_names)
    
    for i in range(0, total, batch_size):
        batch = folder_names[i:i+batch_size]
        print(f"\n🚀 Đang xử lý nhóm {i//batch_size + 1} ({len(batch)} bài)...")
        
        async with AsyncWebCrawler(verbose=False) as crawler:
            for name in batch:
                target_url = f"https://toanmath.com/{name}"
                folder_path = os.path.join(base_path, name)
                
                try:
                    result = await crawler.arun(
                        url=target_url,
                        bypass_cache=True,
                        wait_for=".entry-meta-date"
                    )

                    if result.success and result.html:
                        soup = BeautifulSoup(result.html, 'html.parser')
                        
                        # Nhắm thẳng vào cấu trúc bạn đã gửi
                        date_tag = soup.select_one('.entry-meta-date a') or soup.select_one('.mh-meta a')
                        
                        if not date_tag:
                            # Tìm bất kỳ chuỗi dd/mm/yyyy nào nếu class thất bại
                            date_tag = soup.find(string=re.compile(r'\d{2}/\d{2}/\d{4}'))

                        date_str = date_tag.get_text(strip=True) if hasattr(date_tag, 'get_text') else str(date_tag).strip()
                        
                        # Ghi file với định dạng Link: và Date: như bạn yêu cầu
                        info_file = os.path.join(folder_path, 'info.txt')
                        with open(info_file, 'w', encoding='utf-8') as f:
                            f.write(f"Link: {result.url}\n")
                            f.write(f"Date: {date_str}\n")
                        
                        current_idx = i + batch.index(name) + 1
                        print(f"✅ [{current_idx}/{total}] {name} - {date_str}")
                    else:
                        print(f"❌ [{i + batch.index(name) + 1}/{total}] Lỗi tải {name}")
                except Exception as e:
                    print(f"⚠️ [{i + batch.index(name) + 1}/{total}] Lỗi xử lý {name}: {e}")
                
                # Nghỉ ngắn 0.5s giữa các bài trong cùng 1 nhóm
                await asyncio.sleep(0.5)

async def main():
    # PATH ĐẾN THƯ MỤC PROCESSED
    base_dir = "c:/Users/taoda/OneDrive/Desktop/Choice/collect link/processed"
    
    # 1. Lấy danh sách thư mục
    folders = get_folder_names(base_dir)
    print(f"🚀 Tìm thấy {len(folders)} thư mục để xử lý.")
    
    if not folders:
        print("Không tìm thấy thư mục nào. Vui lòng kiểm tra lại đường dẫn.")
        return

    # 2. Lưu danh sách JSON làm plan trước
    to_crawl_list = [{"folder": f, "url": f"https://toanmath.com/{f}"} for f in folders]
    json_path = "c:/Users/taoda/OneDrive/Desktop/Choice/collect link/exams_to_crawl.json"
    with open(json_path, 'w', encoding='utf-8') as jf:
        json.dump(to_crawl_list, jf, ensure_ascii=False, indent=4)
    print(f"📝 Đã lưu danh sách bài cần cào vào JSON.")

    # 3. Thực hiện cào theo đợt
    await update_exam_info(folders, base_dir)

if __name__ == "__main__":
    asyncio.run(main())
