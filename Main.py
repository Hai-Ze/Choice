import fitz  # PyMuPDF
import json
import re
import time
import os
from dotenv import load_dotenv
from google import genai

# Tải trước các biến môi trường từ tệp .env ẩn
load_dotenv()

# =========================================================
# PHẦN 1: TRÍCH XUẤT VÀ LÀM SẠCH DỮ LIỆU TỪ PDF RA JSON
# =========================================================

def extract_pdf_by_grades(pdf_path):
    """
    Hàm đọc file PDF và chia nhỏ khối text theo từng lớp (10, 11, 12).
    """
    doc = fitz.open(pdf_path)
    
    # Định nghĩa ranh giới các trang dựa vào mục lục của file PDF (Trang 10: 79, 11: 89, 12: 105)
    # Lưu ý: Index trong PyMuPDF đếm từ 0, nên trang 79 tương ứng là index 78.
    sections = {
        10: (78, 88), 
        11: (88, 104),
        12: (104, 114) 
    }
    
    grade_texts = {}
    for grade, (start_page, end_page) in sections.items():
        text = ""
        for i in range(start_page, min(end_page, doc.page_count)):
            text += doc.load_page(i).get_text() + "\n"
        grade_texts[grade] = text
        
    return grade_texts

def process_text_with_llm_to_json(text_chunk, grade, api_key):
    """
    Sử dụng LLM API (Gemini) để làm sạch text, tái cấu trúc mảng và đưa công thức về chuẩn LaTeX.
    """
    client = genai.Client(api_key=api_key)

    prompt = rf"""
    Bạn là chuyên gia về chương trình giáo dục Toán học Việt Nam. 
    Hãy phân tích đoạn văn bản thô (được trích xuất từ PDF) của Lớp {grade} dưới đây và chuyển đổi nó về ĐÚNG MỘT KHỐI JSON ARRAY.
    
    YÊU CẦU BẮT BUỘC (CRITICAL):
    1. Trả về đúng cấu trúc (Cách 1). Ví dụ:
    [
      {{
        "grade": {grade},
        "topic": "Đại số" (tương ứng thuộc nội dung nào),
        "section": "Tên chương lớn/Nội dung chính",
        "id_section": "1",
        "content": [
          {{
            "subsection": "Tên tiết học/Chủ đề nhỏ",
            "id_subsection": "1",
            "requirements": [
              {{
                 "id_problem": "1_1_1",
                 "description": "Nội dung mô tả (fix lỗi chính tả nếu có)"
              }}
            ]
          }}
        ]
      }}
    ]
    2. CHUYỂN HÓA LATEX: Mọi kí tự toán học (độ, góc, tích phân, giới hạn...) bọc trong dấu `$`. 
    !!CẢNH BÁO JSON!!: TẤT CẢ các dấu backslash (`\\`) trong chuỗi của bạn PHẢI ĐƯỢC NHÂN ĐÔI (ESCAPE) THÀNH `\\\\`. Ví dụ: `"\\\\lim_{{n\\\\to\\\\infty}}"` KHÔNG ĐƯỢC gõ `"\\lim_{{n\\to\\infty}}"`. Dấu xuyệt đơn sẽ làm sập hàm json.loads().
    3. TUYỆT ĐỐI CHỈ OUTPUT JSON, không có chữ mở đầu/kết thúc hay ```json.

    Dưới đây là văn bản cần phân tích:
    {text_chunk}
    """
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
    )
    raw_response = response.text.strip()
    
    # Đề phòng LLM cố tình trả về block ```json
    if raw_response.startswith('```json'):
        raw_response = raw_response[7:-3].strip()
    elif raw_response.startswith('```'):
        raw_response = raw_response[3:-3].strip()
    
    return json.loads(raw_response)

def build_new_khung_chuong_trinh(pdf_path, output_json, api_key):
    print("-> Đang trích text từ file PDF...")
    grade_texts = extract_pdf_by_grades(pdf_path)
    final_json = []
    
    for grade, text in grade_texts.items():
        print(f"🔧 Đang chạy AI biên dịch chương trình Lớp {grade}...")
        
        # Thử gọi API (Tối đa 2 lần để né rào cản quá tải của bản Free)
        for attempt in range(2):
            try:
                grade_json = process_text_with_llm_to_json(text, grade, api_key)
                final_json.extend(grade_json)
                print(f"✅ Bóc tách hoàn tất Lớp {grade}.")
                break
            except Exception as e:
                error_str = str(e)
                if "429" in error_str and attempt == 0:
                    print("⚠️ Hệ thống API báo đầy. Đang đợi 60 giây để gửi lại...")
                    time.sleep(60)
                else:
                    print(f"❌ Lỗi khi xử lý Lớp {grade}. Chi tiết: {e}")
                    break
                    
        # Nghỉ nhẹ 10s giữa mỗi Lớp để tránh bị Google block
        if grade != 12:
            time.sleep(10)
            
    # TÁI CẤU TRÚC: Đánh lại toàn bộ ID để tăng dần từ 1 -> N xuyên suốt toàn bộ Grade
    current_section_id = 1
    for item in final_json:
        item["id_section"] = str(current_section_id)
        current_subsection_id = 1
        for content in item.get("content", []):
            content["id_subsection"] = str(current_subsection_id)
            current_req_id = 1
            for req in content.get("requirements", []):
                req["id_problem"] = f"{current_section_id}_{current_subsection_id}_{current_req_id}"
                current_req_id += 1
            current_subsection_id += 1
        current_section_id += 1
            
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(final_json, f, ensure_ascii=False, indent=2)
    print("\n🎉 HOÀN THÀNH! File JSON mới đã được lưu tại:", output_json)

# =========================================================
# PHẦN 2: KIỂM TRA CHÉO (VALIDATE) DỮ LIỆU JSON VS PDF
# =========================================================

def validate_json_vs_pdf(json_path, pdf_path):
    """
    Mở file JSON và PDF lên, tìm kiếm String Matching (fuzzy match nhẹ) để xem có sót bài nào không.
    """
    print("-> Đang kiểm tra chéo (Data Validation)...")
    doc = fitz.open(pdf_path)
    full_pdf_text = "".join([doc.load_page(i).get_text() for i in range(doc.page_count)])
    
    # Xoá toàn bộ ký hiệu ngắt dòng để dò string liên tục
    full_pdf_text_clean = re.sub(r'\s+', ' ', full_pdf_text).lower()
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Chưa tìm thấy file {json_path}. Vui lòng chạy xuất dữ liệu trước.")
        return
        
    report = []
    report.append("BÁO CÁO KIỂM TRA CHÉO JSON VS PDF")
    report.append("===================================")
    
    missing_sections = 0
    missing_subsections = 0
    total_sections = len(data)
    
    for item in data:
        section = item.get("section", "")
        # Dọn sạch kí tự Enter dư
        section_clean = re.sub(r'\s+', ' ', section).lower().strip()
        
        # Nếu section có tồn tại nội dung mà dò không dính chữ nào trong PDF => Nguy cơ bịa data
        if section_clean and section_clean not in full_pdf_text_clean:
            # Note: đôi khi LaTeX sinh ra làm sai lệch chữ so với cụm text gốc
            report.append(f"[CẢNH BÁO] Không tìm thấy tên Section '{section}' (Lớp {item.get('grade')}) lặp lại chính xác trong PDF.")
            missing_sections += 1
            
        for content in item.get("content", []):
            subsection = content.get("subsection", "")
            subsection_clean = re.sub(r'\s+', ' ', subsection).lower().strip()
            
            if subsection_clean and subsection_clean not in full_pdf_text_clean:
                report.append(f"    - THIẾU/SAI LỆCH: Subsection '{subsection}' không xuất hiện y hệt trong PDF thô.")
                missing_subsections += 1
                
    report.append(f"\n===================================")
    report.append(f"TỔNG QUÁT: Đã kiểm tra {total_sections} Sections.")
    
    if missing_sections == 0 and missing_subsections == 0:
        report.append("✅ CHÚC MỪNG: Các tiêu đề bài trong JSON đều khớp 100% về mặt text so với bản gốc PDF.")
    else:
        report.append(f"❌ Phát hiện {missing_sections} section và {missing_subsections} subsection ở JSON không giống PDF gốc.")
        report.append("- Lời khuyên: Text PDF thường hay có khoảng cách lạ (VD: 'T oá n'), hoặc do AI đã gộp ý, đổi thành LaTeX. Hãy xem báo cáo chi tiết để quyết định bỏ qua hay cần sửa.")
        
    with open("report_validation.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(report))
        
    print(f"✅ Đã tạo xong báo cáo soát lỗi tại file: report_validation.txt")


if __name__ == "__main__":
    PDF_FILE = "3__CT_Toan_59b5e.pdf"
    OUTPUT_JSON = "KhungChuongTrinh_Moi.json"
    
    # Đã giấu API KEY sang file .env để tránh bị lộ khi đẩy lên Git
    YOUR_GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
    
    if not YOUR_GEMINI_API_KEY:
        print("CẢNH BÁO: Không tìm thấy GEMINI_API_KEY trong file .env!")
        exit()
    
    print("---------------------------------------")
    print("1: Tự động trích xuất PDF thành JSON chuẩn (Cần API Key LLM)")
    print("2: Chạy validate kiểm tra chéo file JSON với file PDF")
    choice = input("\nLựa chọn tính năng bạn muốn (1 hoặc 2): ")
    print("---------------------------------------")
    
    if choice == "1":
        build_new_khung_chuong_trinh(PDF_FILE, OUTPUT_JSON, YOUR_GEMINI_API_KEY)
    elif choice == "2":
        validate_json_vs_pdf(OUTPUT_JSON, PDF_FILE)
    else:
        print("Lựa chọn không hợp lệ.")
