import os
import json
import re
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(
    api_key=os.getenv("GLM_API_KEY"),
    base_url=os.getenv("GLM_BASE_URL")
)


# ====================================================================
# BƯỚC 0: Tách câu từ .md
# ====================================================================

def detect_answer(block):
    # Dạng 1: "Chọn A / ### Chọn B / **Chọn C**"
    m = re.search(r'(?:#{1,6}\s*)?\*{0,2}[Cc]họn\s*\*{0,2}([A-Da-d])', block)
    if m:
        return True, m.group(1).upper()

    # Dạng 2: "**Đáp án:** 0,14" / "Đáp án: B"
    m = re.search(r'\*{0,2}[Đđ]áp\s*án\*{0,2}\s*[:\.]?\s*\*{0,2}(\S+)', block)
    if m:
        return True, m.group(1).strip("*.,")

    # Dạng 3: Bảng ĐÚNG/SAI (phần 2)
    if re.search(r'<td>\s*(?:ĐÚNG|SAI|Đúng|Sai)\s*</td>', block):
        return True, None

    # Dạng 4: a) Đúng / b) Sai dạng text
    if re.search(r'[a-d]\)\s*(?:Đúng|Sai|ĐÚNG|SAI)', block):
        return True, None

    # Dạng 5: "**Trả lời: 0,7**" / "Trả lời: 0,7" / "**Trả lời:** 0,7"
    # Dấu [:] BẮt BUỘC – tránh match câu hướng dẫn "Trả lời từ câu 1 đến..."
    m = re.search(r'\*{0,2}[Tt]rả\s*lời\*{0,2}\s*[:\.]+\s*\*{0,2}(\S+)', block)
    if m:
        val = m.group(1).strip("*.,")
        # Loại bỏ các từ không phải đáp án (=các từ tiếng Việt thông dụng)
        BLACKLIST = {"từ", "trên", "dưới", "theo", "câu", "phương", "sao", "bên", "như", "các", "mỗi"}
        # Loại bỏ ký tự trống/placeholder: ☐☐☐ hoặc ............ hoặc [ ] [ ]
        PLACEHOLDER_CHARS = set("☐□_.…[] \t")
        is_placeholder = all(c in PLACEHOLDER_CHARS for c in val)
        if val.lower() not in BLACKLIST and not is_placeholder and val.strip(". ") != "":
            return True, val

    # Dạng 6: "Đáp số: 4031" / "**Đáp số:** 4031"
    m = re.search(r'\*{0,2}[Đđ]áp\s*số\*{0,2}\s*[:\.]+ \s*\*{0,2}(\S+)', block)
    if not m:
        m = re.search(r'\*{0,2}[Đđ]áp\s*số\*{0,2}\s*[:\.]+\s*\*{0,2}(\S+)', block)
    if m:
        val = m.group(1).strip("*.,")
        if val.strip():
            return True, val

    return False, None


def detect_section(block):
    """Nhận diện section dựa vào nội dung câu hỏi"""
    # Section 2: có statements a) b) c) d)
    if re.search(r'(?m)^\s*[a-d]\)', block):
        return 2

    # Section 1: có options A. B. C. D. ở đầu dòng
    if re.search(r'(?m)^\s*[A-D]\.', block):
        return 1

    # Section 1 dạng LaTeX: \text{A.} hoặc \text{A } bên trong $$ ... $$
    if re.search(r'\\text\{[A-D][\.\ ]', block):
        return 1

    # Section 3: tự luận, không có options
    return 3


def get_questions(md_content):
    """Tách .md thành list câu hỏi, tự động gộp (merge) nếu câu hỏi bị lặp lại ở phần Lời giải"""
    q_dict = {} # key: (section, number)

    matches = list(re.finditer(r'(?m)^\s*\*{0,2}[Cc]âu\s+(\d+)[\.\:]\*{0,2}', md_content))
    
    for i in range(len(matches)):
        start = matches[i].start()
        end = matches[i+1].start() if i + 1 < len(matches) else len(md_content)
        
        block = md_content[start:end]
        q_num = matches[i].group(1)
        
        block_clean = block.strip()
        if len(block_clean) < 20: continue

        # Bỏ câu bị ghép options lỗi
        if len(re.findall(r'(?m)^\s*A\.', block)) > 1:
            print(f"  ⚠️ Câu {q_num}: bị ghép options → bỏ qua")
            continue

        has_answer, answer_val = detect_answer(block)
        section = detect_section(block)
        key = (section, q_num)

        new_data = {
            "number":     q_num,
            "text":       block_clean,
            "has_image":  "![" in block,
            "section":    section,
            "has_answer": has_answer,
            "answer_val": answer_val
        }

        if key not in q_dict:
            q_dict[key] = new_data
        else:
            # GỘP DỮ LIỆU: Nếu câu này đã tồn tại, ưu tiên lấy phần có đáp án hoặc text dài hơn
            old = q_dict[key]
            # Nếu bản cũ chưa có đáp án mà bản mới có -> lấy bản mới
            if not old["has_answer"] and new_data["has_answer"]:
                old.update({
                    "text": block_clean, 
                    "has_answer": True, 
                    "answer_val": answer_val,
                    "has_image": old["has_image"] or new_data["has_image"]
                })
            # Nếu bản mới dài hơn đáng kể (thường là phần lời giải) -> gộp text
            elif len(block_clean) > len(old["text"]):
                old["text"] = block_clean
                if new_data["has_answer"]:
                    old["has_answer"] = True
                    old["answer_val"] = answer_val

    return list(q_dict.values())


# ====================================================================
# HÀM CHÍNH
# ====================================================================

def process_md_to_jsonl(md_file_path):
    output_path = md_file_path.replace(".md", ".jsonl")

    with open(md_file_path, "r", encoding="utf-8") as f:
        md_content = f.read()

    system_prompt = """Bạn là AI số hóa đề thi Toán sang JSON. Vi phạm → output bị hủy.

CẤU TRÚC theo [SECTION=X]:
- section=1 (Trắc nghiệm ABCD): {"section":1,"content":{"stem":"...","options":[{"label":"A.","content":"..."}...],"answer":"...","solution":"..."}}
- section=2 (Đúng/Sai):         {"section":2,"content":{"stem":"...","statements":[{"label":"a)","content":"...","answer":"T/F/null"}...],"solution":"..."}}
- section=3 (Trả lời ngắn):     {"section":3,"content":{"stem":"...","answer":"...","solution":"..."}}

QUY TẮC SECTION:
- Dùng ĐÚNG section từ [SECTION=X], KHÔNG tự thay đổi.
- section=3 là tự luận → TUYỆT ĐỐI KHÔNG có "options", KHÔNG có A/B/C/D.

QUY TẮC ĐÁP ÁN - QUAN TRỌNG NHẤT:
⛔ BẠN LÀ MÁY ĐÁNH MÁY. TUYỆT ĐỐI KHÔNG tự tính, suy luận, đoán đáp án.
- [HAS_ANSWER=NO]  → "answer": null. DÙ BIẾT ĐÁP ÁN → VẪN null.
- [HAS_ANSWER=YES] → copy đáp án từ văn bản vào "answer".
- [ANSWER=X]       → copy đúng giá trị X vào "answer", không cần tìm.
- section=2 + [HAS_ANSWER=NO]  → TẤT CẢ statement "answer": null.
- section=2 + [HAS_ANSWER=YES] → đọc bảng ĐÚNG/SAI → điền "T"/"F" đúng thứ tự.
- "solution": copy lời giải nếu có, XÓA câu chốt đáp án ("Chọn A","Đáp án B"). Không có → null.

QUY TẮC KHÁC:
- "stem": KHÔNG ghi "Câu X." vào đầu.
- Xóa rác: Facebook, SĐT, số trang, tác giả.
- LaTeX: double escape \\\\ (ví dụ: \\\\cos, \\\\frac).
- 1 câu → 1 JSON object. KHÔNG tự chế thêm."""

    print(f"--- Processing: {os.path.basename(md_file_path)} ---")

    # ================================================================
    # BƯỚC 1: Tách câu, gắn metadata, lọc hình
    # ================================================================
    all_questions   = get_questions(md_content)
    clean_questions = [q for q in all_questions if not q["has_image"]]
    img_questions   = [q for q in all_questions if q["has_image"]]

    print(f"  📋 Tổng: {len(all_questions)} | ✅ Sạch: {len(clean_questions)} | ❌ Hình: {len(img_questions)}")
    if img_questions:
        print(f"  ❌ Bỏ câu có hình: {[q['number'] for q in img_questions]}")
    print(f"  📌 Phân loại:")
    for q in clean_questions:
        ans_info = f"✅ '{q['answer_val']}'" if q["answer_val"] else ("✅ có" if q["has_answer"] else "⬜ null")
        print(f"    Câu {q['number']} → S{q['section']} | {ans_info}")

    # ================================================================
    # BƯỚC 2: Gửi API theo chunk
    # ================================================================
    CHUNK_SIZE = 5
    chunks = [clean_questions[i:i + CHUNK_SIZE] for i in range(0, len(clean_questions), CHUNK_SIZE)]
    all_json_objs = []

    for i, chunk in enumerate(chunks, 1):
        print(f"\n  -> Chunk {i}/{len(chunks)}: Câu {[q['number'] for q in chunk]}...")

        chunk_parts = []
        for q in chunk:
            tags = f"[SECTION={q['section']}] [HAS_ANSWER={'YES' if q['has_answer'] else 'NO'}]"
            if q["answer_val"]:
                tags += f" [ANSWER={q['answer_val']}]"
            chunk_parts.append(f"{tags}\n{q['text']}")

        user_prompt = f"""Số hóa {len(chunk)} câu sau → trả về ĐÚNG {len(chunk)} JSON object.

⚠️ [HAS_ANSWER=NO]  → "answer": null. Dù biết đáp án → VẪN null. Không tự tính.
⚠️ [ANSWER=X]       → copy đúng X vào "answer". Không đổi.
⚠️ section=3        → KHÔNG có options A/B/C/D.
⚠️ Dùng ĐÚNG section từ [SECTION=X].

---
{"---".join(chunk_parts)}
---"""

        try:
            response = client.chat.completions.create(
                model="GLM-4-Plus",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_prompt}
                ],
                temperature=0.0,
                max_tokens=8192
            )
            result_text = response.choices[0].message.content.strip()
            if "```" in result_text:
                result_text = re.sub(r'```[a-z]*\n|```', '', result_text)

            # Bóc tách JSON bằng đếm ngoặc {}
            parsed, stack, start = [], 0, -1
            for k, ch in enumerate(result_text):
                if ch == '{':
                    if stack == 0: start = k
                    stack += 1
                elif ch == '}':
                    stack -= 1
                    if stack == 0 and start != -1:
                        parsed.append(result_text[start:k + 1])

            if len(parsed) != len(chunk):
                print(f"  ⚠️ Gửi {len(chunk)} câu nhưng nhận {len(parsed)} JSON!")

            for j, js in enumerate(parsed):
                all_json_objs.append((js, chunk[j] if j < len(chunk) else None))

        except Exception as e:
            print(f"  ❌ API Error: {e}")

    # ================================================================
    # BƯỚC 3: Hậu xử lý & validate
    # ================================================================
    pretty_lines = []
    stats = {"kept": 0, "empty_stem": 0, "invalid_opt": 0, "forced_null": 0, "parse_err": 0}

    for json_str, q_meta in all_json_objs:
        try:
            # Parse JSON, tự fix LaTeX escape nếu lỗi
            try:
                obj = json.loads(json_str)
            except json.JSONDecodeError:
                obj = json.loads(re.sub(r'(?<!\\)\\(?![\\n"trbf/u])', r'\\\\', json_str))

            # Override section từ .md (không tin LLM)
            if q_meta:
                obj["section"] = q_meta["section"]

            content = obj.get("content", {})
            if not isinstance(content, dict):
                stats["empty_stem"] += 1
                continue

            # Xóa "**Câu X.**" ở đầu stem
            stem = re.sub(r'^\s*\*{0,2}[Cc]âu\s+\d+\*{0,2}[\.\:]?\s*', '', content.get("stem", "")).strip()
            if not stem:
                stats["empty_stem"] += 1
                continue
            content["stem"] = stem

            section = obj.get("section")

            # Section 3: xóa options nếu LLM vẫn thêm
            if section == 3:
                content.pop("options", None)

            # Section 1: validate options A→D liên tục
            if section == 1:
                labels = [o.get("label", "").strip().rstrip(".") for o in content.get("options", [])]
                if labels and labels != ["A", "B", "C", "D"][:len(labels)]:
                    stats["invalid_opt"] += 1
                    print(f"  ⚠️ Bỏ câu options lỗi: {labels}")
                    continue

            # Force null cho Section 1 & 3 nếu .md không có đáp án (LUÔN LUÔN - không tin AI)
            # Section 2 KHÔNG có trường answer tổng (chỉ có answer trong từng statement)
            if q_meta and not q_meta["has_answer"]:
                if section == 1 or section == 3:
                    content["answer"] = None
                    if content.get("answer") is not None:
                        stats["forced_null"] += 1
                        print(f"  🔧 Câu {q_meta['number']}: force answer → null")
                elif section == 2:
                    # Section 2: force null cho từng statement
                    for stmt in content.get("statements", []):
                        stmt["answer"] = None

            # Force đúng answer nếu đã biết từ .md
            if q_meta and q_meta["has_answer"] and q_meta["answer_val"]:
                if section == 1:
                    # Chỉ chấp nhận A/B/C/D - nếu answer_val từ md là text khác thì bỏ qua
                    val = q_meta["answer_val"].upper()
                    if re.fullmatch(r'[A-D]', val):
                        content["answer"] = val
                elif section == 3:
                    content["answer"] = q_meta["answer_val"]

            # Ràng buộc cuối: Section 1 answer chỉ được là A/B/C/D
            if section == 1:
                raw_ans = content.get("answer")
                if raw_ans is not None:
                    # Thử trích chữ cái A/B/C/D từ chuỗi AI trả về (VD: "Chọn D", "D.", "đáp án B")
                    m_letter = re.search(r'\b([A-Da-d])\b', str(raw_ans))
                    if m_letter:
                        content["answer"] = m_letter.group(1).upper()
                    else:
                        content["answer"] = None

            # Ràng buộc cuối: Section 2 - mỗi statement answer chỉ được là "T", "F", hoặc null
            if section == 2:
                TRUE_WORDS  = {"t", "true", "đúng", "dung", "đ", "yes"}
                FALSE_WORDS = {"f", "false", "sai", "s", "no"}
                for stmt in content.get("statements", []):
                    raw = stmt.get("answer")
                    if raw is None:
                        continue
                    normalized = str(raw).strip("*. ").lower()
                    if normalized in TRUE_WORDS:
                        stmt["answer"] = "T"
                    elif normalized in FALSE_WORDS:
                        stmt["answer"] = "F"
                    else:
                        stmt["answer"] = None  # không nhận dạng được → null

            # Ràng buộc cuối: Section 3 - answer phải là giá trị ngắn (số/biểu thức)
            if section == 3:
                raw_ans = content.get("answer")
                if raw_ans is not None:
                    cleaned = str(raw_ans).strip("*. ").upper()
                    # Nếu là chữ cái A, B, C, D đơn độc thì là lỗi (S3 phải là số)
                    if re.fullmatch(r'[A-D]', cleaned):
                        content["answer"] = None
                    # Nếu dài hơn 50 ký tự → AI nhiều khả năng copy cả câu → null
                    elif len(cleaned) > 50:
                        content["answer"] = None
                    else:
                        content["answer"] = cleaned if cleaned else None


            obj["content"] = content
            for f in ["question_number", "question_id"]:
                obj.pop(f, None)

            pretty_lines.append(json.dumps(obj, ensure_ascii=False, indent=2))
            stats["kept"] += 1

        except json.JSONDecodeError as e:
            stats["parse_err"] += 1
            print(f"  ⚠️ Parse lỗi: {e} | {json_str[:100]}...")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(pretty_lines))

    print(f"\n{'='*50}")
    print(f"✅ DONE: {os.path.basename(output_path)}")
    print(f"{'='*50}")
    print(f"  📥 Gửi LLM       : {len(clean_questions)} câu")
    print(f"  ✅ Giữ lại        : {stats['kept']} câu")
    print(f"  🖼️  Bỏ (hình)     : {len(img_questions)} câu")
    print(f"  ⬜ Bỏ (stem rỗng) : {stats['empty_stem']} câu")
    print(f"  ❌ Bỏ (opt lỗi)  : {stats['invalid_opt']} câu")
    print(f"  🔧 Force null     : {stats['forced_null']} câu")
    print(f"  💥 Parse lỗi     : {stats['parse_err']} câu")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    test_file = r"c:/Users/taoda/OneDrive/Desktop/Choice/collect link/processed/12-de-thi-thu-bam-sat-cau-truc-de-tham-khao-tn-thpt-2025-mon-toan/exams/exam_19.md"
    process_md_to_jsonl(test_file)