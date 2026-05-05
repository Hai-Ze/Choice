import fitz  # PyMuPDF
import json
import re
import os
import sys
from typing import List, Dict, Tuple, Optional

# Fix encoding cho Windows CMD
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# ============================================================
# PARSE PDF TABLE -> JSON (PHIÊN BẢN CHUẨN - BMAD ENHANCED)
# ============================================================

SKIP_KEYWORDS = ["thực hành và trải nghiệm", "hoạt động thực hành", "thực hành"]

# Mapping ký tự Unicode bị lỗi từ PDF → Unicode chuẩn
UNICODE_FIX_MAP = {
    '': '⊂',      # Tập con
    '': '⊃',      # Tập cha
    '': '∅',      # Tập rỗng
    '': '∀',      # For all
    '': '∃',      # Exists
    '': '°',      # Degree
    '': '°',      # Degree variant
    '': '+',      # Plus sign
    '': '-',      # Minus sign
    '': '→',      # Arrow right
    '': '←',      # Arrow left
    '': '⇒',      # Implies
    '': '∑',      # Sum
    '': '∫',      # Integral
    '': '√',      # Square root
    '': '∞',      # Infinity
    '': '≤',      # Less or equal
    '': '≥',      # Greater or equal
    '': '≠',      # Not equal
    '': '≈',      # Approximately
    '': '∪',      # Union
    '': '∩',      # Intersection
    '': '∈',      # Element of
    '': 'π',      # Pi
    '': 'α',      # Alpha
    '': 'β',      # Beta
    '': 'γ',      # Gamma
    '': 'δ',      # Delta
    '': 'θ',      # Theta
    '': 'λ',      # Lambda
    '': 'μ',      # Mu
    '': 'σ',      # Sigma
    '': 'φ',      # Phi
    '': 'ω',      # Omega
    '': '×',      # Multiplication
    '': '÷',      # Division
    '': 'ε',      # Epsilon
}

def fix_unicode_chars(text: str) -> str:
    """Fix các ký tự Unicode bị lỗi từ PDF"""
    if not text:
        return text
    result = text
    for bad_char, good_char in UNICODE_FIX_MAP.items():
        result = result.replace(bad_char, good_char)
    return result

BIG_HEADERS = [
    "ĐẠI SỐ VÀ MỘT SỐ YẾU TỐ GIẢI TÍCH",
    "HÌNH HỌC VÀ ĐO LƯỜNG",
    "THỐNG KÊ VÀ XÁC SUẤT",
    "NỘI DUNG CHUYÊN ĐỀ",
    "Nội dung", "Yêu cầu cần đạt", "Mạch nội dung", "Chủ đề",
]

VALID_TOPICS = [
    "Đại số", "Một số yếu tố giải tích", "Hình học", "Hình học và Đo lường",
    "Thống kê", "Xác suất", "Thống kê và Xác suất", "Giải tích",
    "Hình học không gian", "Một số yếu tố Giải tích", "Chuyên đề",
    "Chuyên đề LỚP 10", "Chuyên đề LỚP 11", "Chuyên đề LỚP 12",
    "Ứng dụng Toán học vào giải quyết vấn đề thực tiễn",
]

def clean_text(text):
    """Làm sạch text và fix Unicode"""
    if not text: return ""
    text = text.replace('\n', ' ')
    text = re.sub(r' {2,}', ' ', text)
    text = fix_unicode_chars(text)
    return text.strip()

def is_big_header(text):
    t = text.strip()
    for h in BIG_HEADERS:
        if t == h or t.lower() == h.lower(): return True
    if t and t == t.upper() and len(t) > 15: return True
    return False

def check_topic(col0, col1, col2):
    t = col0.strip()
    if not t: return None
    if t.lower().startswith("chuyên đề"): return t
    if col2: return None
    if t in VALID_TOPICS: return t
    for topic in VALID_TOPICS:
        if t == topic.upper() or t == topic: return topic
    return None

def split_requirements(text):
    """Tách requirements, có merge các câu bị tách sai"""
    if not text: return []
    parts = re.split(r'(?:\n|^| )[–-]\s+', text)
    results = [clean_text(p) for p in parts if len(p.strip()) > 5]
    if not results and len(text.strip()) > 5: results.append(clean_text(text))
    return results


def merge_broken_requirements(requirements: List[Dict]) -> List[Dict]:
    """
    Merge các requirement bị tách sai thành một.
    Ví dụ: "Vận dụng được..." + "một số bài toán..." → "Vận dụng được một số bài toán..."
    """
    if not requirements:
        return []

    merged = []
    i = 0
    current_id_prefix = None
    accumulated_desc = ""

    for req in requirements:
        desc = req.get("description", "")
        if not desc:
            continue

        # Phát hiện dấu hiệu câu bị tách:
        # - Kết thúc bằng từ nối: "và", "của", "liên", "sản", "xuất", "thực"
        # - Bắt đầu bằng từ thường (không viết hoa)
        # - Có dấu 3 chấm hoặc dấu gạch ngang ở cuối
        prev_desc = accumulated_desc

        # Từ kết thúc có thể bị tách
        continuation_ends = ["và", "của", "liên", "sản", "xuất", "thực", "thực",
                            "một số", "các", "những", "với", "cho", "đến"]

        should_merge = False
        if accumulated_desc:
            # Check xem desc hiện tại có phải là continuation không
            if any(desc.lower().startswith(w) for w in ["một số", "các", "những", "bài toán"]):
                # Check xem câu trước có kết thúc bằng từ nối không
                for end_word in continuation_ends:
                    if prev_desc.rstrip().endswith(end_word) or prev_desc.rstrip().endswith(end_word + " "):
                        should_merge = True
                        break
            # Check kết thúc bằng dấu 3 chấm hoặc gạch ngang
            if prev_desc.rstrip().endswith(("...", "…", "–", "-")):
                should_merge = True

        if should_merge:
            accumulated_desc += " " + desc
        else:
            # Flush accumulated nếu có
            if accumulated_desc:
                merged.append({
                    "id_problem": current_id_prefix,
                    "description": accumulated_desc.strip()
                })
            # Bắt đầu requirement mới
            accumulated_desc = desc
            current_id_prefix = req.get("id_problem", "")

    # Flush requirement cuối cùng
    if accumulated_desc:
        merged.append({
            "id_problem": current_id_prefix,
            "description": accumulated_desc.strip()
        })

    # Re-index ID sau khi merge
    for idx, req in enumerate(merged, 1):
        # Giữ nguyên prefix, thay suffix
        if current_id_prefix:
            parts = current_id_prefix.rsplit("_", 1)
            if len(parts) == 2:
                req["id_problem"] = f"{parts[0]}_{idx}"

    return merged

def extract_tables_from_pages(doc, pages):
    all_rows = []
    for page_num in pages:
        page = doc[page_num]
        tabs = page.find_tables()
        for t in tabs.tables:
            data = t.extract()
            for row in data:
                while len(row) < 3: row.append(None)
                all_rows.append(row)
    return all_rows

def parse_grade(doc, grade, pages, section_counter_ref):
    print(f"\n[Lop {grade}] Trang {list(pages)[0]+1}->{list(pages)[-1]+1}...")
    all_rows = extract_tables_from_pages(doc, pages)
    
    sections = []
    current_topic = "Chưa xác định"
    current_section = None
    current_section_name = ""
    current_subsection = None
    skip_mode = False
    seen_special_topics = False

    sec_id = section_counter_ref[0]
    sub_id = 1

    def flush_subsection():
        nonlocal current_subsection, sub_id
        if current_section and current_subsection and current_subsection.get("requirements"):
            current_section["content"].append(current_subsection)
            sub_id += 1
        current_subsection = None

    def flush_section():
        nonlocal current_section, current_section_name, sec_id, sub_id
        flush_subsection()
        if current_section and current_section.get("content"):
            sections.append(current_section)
            sec_id += 1
        current_section = None
        current_section_name = ""
        sub_id = 1

    GRADE_BOUNDARIES = {
        10: ["đại số và một số yếu tố giải tích", "lớp 11", "hàm số lượng giác"],
        11: ["một số yếu tố giải tích", "lớp 12"],
    }

    for row_raw in all_rows:
        col0, col1, col2 = [clean_text(c) for c in row_raw]
        if not col0 and not col1 and not col2: continue

        # --- Kiểm tra ranh giới lớp ---
        if grade in GRADE_BOUNDARIES:
            for boundary in GRADE_BOUNDARIES[grade]:
                if boundary in col0.lower():
                    # Riêng với 'hàm số lượng giác', dừng luôn không cần thấy chuyên đề
                    # Các cái khác cần seen_special_topics để tránh dừng quá sớm ở đầu lớp
                    if boundary == "hàm số lượng giác" or seen_special_topics:
                        print(f"   [DUNG] Gap ranh gioi '{boundary}' lop {grade}")
                        flush_section()
                        section_counter_ref[0] = sec_id
                        return sections

        detected_topic = check_topic(col0, col1, col2)
        if detected_topic and not col2:
            flush_section()
            current_topic = detected_topic
            if "Chuyên đề" in detected_topic: seen_special_topics = True
            print(f"   [Topic] {current_topic}")
            skip_mode = False
            continue

        if is_big_header(col0) or (col0.lower() == "chuyên đề" and not col1 and not col2):
            continue
        if any(kw in col0.lower() for kw in SKIP_KEYWORDS):
            flush_section()
            skip_mode = True
            continue
        if skip_mode and not col0 and not col1: continue
        else: skip_mode = False

        if col0 and col0 != current_section_name:
            if len(col0) < 6 or col0.lower() in ["nội dung", "chuyên đề"]: continue
            
            # Gộp tên bị cắt
            if current_section:
                s_name = current_section["section"].strip()
                # Các từ kết thúc lửng lơ hoặc tên chuyên đề bị ngắt quãng
                if s_name.endswith("Một") or s_name.endswith("với") or s_name.endswith("Làm") or s_name.endswith("số") or s_name.endswith("yêu") or col0.startswith("số yếu tố"):
                     # Nếu KHÔNG CÓ subsection mới (col1 rỗng), ta coi đây là phần tiếp nối của tên Section
                     if not col1:
                         current_section["section"] += " " + col0
                         current_section_name = current_section["section"]
                         print(f"      🔗 Gộp tên: {current_section_name}")
                         # Nếu có requirement đi kèm ở hàng này, vẫn phải add vào
                         if col2:
                             for r in split_requirements(row_raw[2]):
                                 if current_subsection:
                                     current_subsection["requirements"].append({"id_problem": f"{sec_id}_{sub_id}_{len(current_subsection['requirements'])+1}", "description": r})
                         continue

            if "tổ chức các hoạt động" in col0 or col0.startswith("ng qua"): continue

            flush_section()
            current_section_name = col0
            current_section = {"grade": grade, "topic": current_topic, "section": col0, "id_section": str(sec_id), "content": []}
            sub_id = 1
            print(f"   [{sec_id}] {col0[:60]}...")
            if col1:
                current_subsection = {"subsection": col1, "id_subsection": str(sub_id), "requirements": []}
                if col2:
                    for r in split_requirements(row_raw[2]):
                        current_subsection["requirements"].append({"id_problem": f"{sec_id}_{sub_id}_{len(current_subsection['requirements'])+1}", "description": r})
        elif col1:
            flush_subsection()
            current_subsection = {"subsection": col1, "id_subsection": str(sub_id), "requirements": []}
            if col2:
                for r in split_requirements(row_raw[2]):
                    current_subsection["requirements"].append({"id_problem": f"{sec_id}_{sub_id}_{len(current_subsection['requirements'])+1}", "description": r})
        elif col2 and current_subsection:
            for r in split_requirements(row_raw[2]):
                current_subsection["requirements"].append({"id_problem": f"{sec_id}_{sub_id}_{len(current_subsection['requirements'])+1}", "description": r})

    flush_section()
    section_counter_ref[0] = sec_id
    return sections

def main():
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    PDF_FILE = os.path.join(BASE_DIR, "3__CT_Toan_59b5e.pdf")
    doc = fitz.open(PDF_FILE)
    grade_pages = {10: range(78, 90), 11: range(89, 106), 12: range(105, 115)}
    final_json = []
    section_counter = [1]
    for grade, pages in grade_pages.items():
        grade_sections = parse_grade(doc, grade, pages, section_counter)
        final_json.extend(grade_sections)
    
    for sec_idx, sec in enumerate(final_json, 1):
        sec["id_section"] = str(sec_idx)
        for sub_idx, sub in enumerate(sec.get("content", []), 1):
            sub["id_subsection"] = str(sub_idx)
            for req_idx, req in enumerate(sub.get("requirements", []), 1):
                req["id_problem"] = f"{sec_idx}_{sub_idx}_{req_idx}"

    with open(os.path.join(BASE_DIR, "KhungChuongTrinh_no_api.json"), 'w', encoding='utf-8') as f:
        json.dump(final_json, f, ensure_ascii=False, indent=2)
    print(f"\n[XONG] Tong: {len(final_json)} sections.")
    print(f"[FILE] Output: KhungChuongTrinh_no_api.json")

if __name__ == "__main__":
    main()
