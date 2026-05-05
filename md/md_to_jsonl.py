"""
MD to JSONL Converter - Phiên bản hoàn hảo cho md_outputs
Kết hợp:
- Phân tích cấu trúc bằng AI (đã có sẵn trong ai_analysis_report.txt)
- Regex phát hiện đáp án/lời giải chính xác
- Validate và force dữ liệu theo metadata từ .md
"""

import os
import json
import re
import time
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Khoi tao GLM client
GLM_API_KEY = os.getenv("GLM_API_KEY")

client = OpenAI(
    api_key=GLM_API_KEY,
    base_url=os.getenv("GLM_BASE_URL", "https://api.z.ai/api/paas/v4")
)

# ====================================================================
# BƯỚC 0: Tách câu từ .md (Cải tiến từ code gốc)
# ====================================================================

def detect_answer(block):
    """Phát hiện đáp án trong block văn bản với nhiều pattern"""

    # Dạng 1: "Chọn A / ### Chọn B / **Chọn C**"
    m = re.search(r'(?:#{1,6}\s*)?\*{0,2}[Cc]họn\s*\*{0,2}([A-Da-d])', block)
    if m:
        return True, m.group(1).upper()

    # Dạng 2: "**Đáp án:** 0,14" / "Đáp án: B"
    m = re.search(r'\*{0,2}[Đđ]áp\s*án\*{0,2}\s*[:\.]?\s*\*{0,2}(\S+)', block)
    if m:
        return True, m.group(1).strip("*., ")

    # Dạng 3: Bảng ĐÚNG/SAI (phần 2)
    if re.search(r'<td>\s*(?:ĐÚNG|SAI|Đúng|Sai)\s*</td>', block):
        return True, None

    # Dạng 4: a) Đúng / b) Sai dạng text
    if re.search(r'[a-d]\)\s*(?:Đúng|Sai|ĐÚNG|SAI)', block):
        return True, None

    # Dạng 5: "**Trả lời: 0,7**" / "Trả lời: 0,7" / "**Trả lời:** 0,7"
    # Dấu [:] BẮT BUỘC – tránh match câu hướng dẫn "Trả lời từ câu 1 đến..."
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

    # Dạng 7: "Answer: A" / "Answer: 0.5"
    m = re.search(r'\*{0,2}[Aa]nswer\*{0,2}\s*[:\.]+\s*\*{0,2}(\S+)', block)
    if m:
        val = m.group(1).strip("*.,")
        if val.strip():
            return True, val

    return False, None


def detect_solution(block):
    """Phát hiện xem block có chứa lời giải/hướng dẫn không"""
    solution_patterns = [
        r'\*{0,2}[Ll]ời\s*giải\*{0,2}\s*[:\.]',
        r'\*{0,2}[Gg]iải\*{0,2}\s*[:\.]',
        r'\*{0,2}[Hh]ướng\s*dẫn\*{0,2}\s*[:\.]',
        r'\*{0,2}[Bb]ài\s*giải\*{0,2}\s*[:\.]',
        r'\*{0,2}[Gg]ợi\s*ý\*{0,2}\s*[:\.]',
    ]
    return any(re.search(p, block) for p in solution_patterns)


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
    q_dict = {}  # key: (section, number)

    matches = list(re.finditer(r'(?m)^\s*\*{0,2}[Cc]âu\s+(\d+)[\.\:]\*{0,2}', md_content))

    for i in range(len(matches)):
        start = matches[i].start()
        end = matches[i+1].start() if i + 1 < len(matches) else len(md_content)

        block = md_content[start:end]
        q_num = matches[i].group(1)

        block_clean = block.strip()
        if len(block_clean) < 20:
            continue

        # Bỏ câu bị ghép options lỗi
        if len(re.findall(r'(?m)^\s*A\.', block)) > 1:
            print(f"  WARNING Cau {q_num}: bi ghep options -> bo qua")
            continue

        has_answer, answer_val = detect_answer(block)
        has_solution = detect_solution(block)
        section = detect_section(block)
        key = (section, q_num)

        new_data = {
            "number": q_num,
            "text": block_clean,
            "has_image": "![" in block,
            "section": section,
            "has_answer": has_answer,
            "answer_val": answer_val,
            "has_solution": has_solution
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
            # Nếu bản mới có lời giải mà bản cũ không -> lấy bản mới
            elif new_data["has_solution"] and not old["has_solution"]:
                old["text"] = block_clean
                old["has_solution"] = True
            # Nếu bản mới dài hơn đáng kể (thường là phần lời giải) -> gộp text
            elif len(block_clean) > len(old["text"]):
                old["text"] = block_clean
                if new_data["has_answer"]:
                    old["has_answer"] = True
                    old["answer_val"] = answer_val
                if new_data["has_solution"]:
                    old["has_solution"] = True

    return list(q_dict.values())


def split_by_ma_de(md_content):
    """
    Tách file MD thành các phần theo mã đề

    Returns:
        List tuple: [(ma_de, content), ...]
        Nếu không có mã đề: [("001", full_content)]
    """
    # Các pattern tìm mã đề
    patterns = [
        (r'Mã đề\s*[:\.\-]\s*(\d+)', 'Mã đề:'),
        (r'Mãđề\s*[:\.\-]\s*(\d+)', 'Mãđề:'),
        (r'Mã đề thi\s*(\d+)', 'Mã đề thi'),
        (r'ĐỀ ÔN TẬP TỐT NGHIỆP SỐ\s*(\d+)', 'ĐỀ ÔN TẬP TỐT NGHIỆP SỐ'),
        (r'ĐỀ THI THỬ.*?ĐỀ\s*(\d+)', 'ĐỀ THI TH�'),
        (r'Đề số\s*(\d+)', 'Đề số'),
    ]

    # Tìm tất cả các vị trí mã đề
    found = []
    for pattern, label in patterns:
        for match in re.finditer(pattern, md_content, re.IGNORECASE | re.MULTILINE):
            ma_de = match.group(1)
            pos = match.start()
            found.append((pos, ma_de, label))

    if not found:
        # Không có mã đề, trả về toàn bộ nội dung
        return [("001", md_content)]

    # Sắp xếp theo vị trí
    found.sort()

    # Tách nội dung theo mã đề
    parts = []
    for i, (pos, ma_de, label) in enumerate(found):
        # Tìm vị trí bắt đầu của phần này
        start = pos

        # Tìm vị trí kết thúc (đến mã đề tiếp theo hoặc hết file)
        if i + 1 < len(found):
            end = found[i + 1][0]
        else:
            end = len(md_content)

        content = md_content[start:end].strip()
        if content:  # Chỉ thêm nếu có nội dung
            parts.append((ma_de, content))

    return parts


# ====================================================================
# HÀM CHÍNH
# ====================================================================

def process_md_to_jsonl(md_file_path, use_ai=True):
    """
    Chuyển đổi file markdown sang JSONL

    Args:
        md_file_path: Đường dẫn đến file .md
        use_ai: Có dùng AI để parse hay không (nếu False sẽ dùng regex thuần)
    """
    md_path = Path(md_file_path)

    with open(md_file_path, "r", encoding="utf-8") as f:
        md_content = f.read()

    # ================================================================
    # BƯỚC 0: Tách theo mã đề
    # ================================================================
    ma_de_parts = split_by_ma_de(md_content)

    if len(ma_de_parts) > 1:
        print(f"\n{'='*60}")
        print(f"Processing: {md_path.name}")
        print(f"Phat hien {len(ma_de_parts)} ma de: {[m for m, _ in ma_de_parts]}")
        print(f"{'='*60}")
    else:
        print(f"\n{'='*60}")
        print(f"Processing: {md_path.name}")
        print(f"Khong co ma de - xu ly nhu 1 đề duy nhat")
        print(f"{'='*60}")

    # Tao folder theo ten file MD
    jsonl_dir = Path(r"C:\Users\taoda\OneDrive\Desktop\Choice\md\jsonl_outputs") / md_path.stem
    jsonl_dir.mkdir(parents=True, exist_ok=True)

    all_output_paths = []

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
- [ANSWER=X]       → copy NGUYÊN giá trị X vào "answer". KHÔNG sửa, KHÔNG parse lại từ text.
- Ví dụ: [ANSWER=11,5] → "answer": "11,5" (KHÔNG phải "ĐÁP" hay "Đáp số").
- section=2 + [HAS_ANSWER=NO]  → TẤT CẢ statement "answer": null.
- section=2 + [HAS_ANSWER=YES] → đọc bảng ĐÚNG/SAI → điền "T"/"F" đúng thứ tự.
- "solution": copy lời giải nếu có, XÓA câu chốt đáp án ("Chọn A","Đáp án B"). Không có → null.

QUY TẮC KHÁC:
- "stem": KHÔNG ghi "Câu X." vào đầu.
- Xóa rác: Facebook, SĐT, số trang, tác giả.
- LaTeX: double escape \\\\ (ví dụ: \\\\cos, \\\\frac).
- 1 câu → 1 JSON object. KHÔNG tự chế thêm."""

    # Xử lý từng mã đề
    for ma_de, part_content in ma_de_parts:
        print(f"\n  ---> Xu ly ma de: {ma_de}")

        # ================================================================
        # BƯỚC 1: Tách câu, gắn metadata, lọc hình
        # ================================================================
        all_questions = get_questions(part_content)
        clean_questions = [q for q in all_questions if not q["has_image"]]
        img_questions = [q for q in all_questions if q["has_image"]]

        print(f"      Tong: {len(all_questions)} | Sach: {len(clean_questions)} | Hinh: {len(img_questions)}")
        if img_questions:
            print(f"      Bo cau co hinh: {[q['number'] for q in img_questions]}")

        # Thống kê phân loại
        sec_count = {1: 0, 2: 0, 3: 0}
        for q in clean_questions:
            sec_count[q['section']] += 1
        print(f"      Phan loai: Section1={sec_count[1]}, Section2={sec_count[2]}, Section3={sec_count[3]}")

        # Thống kê đáp án
        has_ans_count = sum(1 for q in clean_questions if q['has_answer'])
        print(f"      Co dap an: {has_ans_count}/{len(clean_questions)}")

        if not clean_questions:
            print(f"      Khong co cau de xu ly -> bo qua")
            continue

        # ================================================================
        # BƯỚC 2: Xử lý từng chunk
        # ================================================================
        if use_ai:
            all_json_objs = process_with_ai(
                clean_questions,
                system_prompt,
                chunk_size=5
            )
        else:
            # Fallback: dùng regex thuần
            all_json_objs = process_with_regex(clean_questions)

        # ================================================================
        # BƯỚC 3: Hậu xử lý & validate
        # ================================================================
        pretty_lines, stats = validate_and_format(
            all_json_objs,
            clean_questions
        )

        # Tên file output: ma-de-XXX.jsonl
        output_filename = f"ma-de-{ma_de}.jsonl"
        output_path = jsonl_dir / output_filename

        # Ghi output
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n\n".join(pretty_lines))

        print(f"      DONE: {output_filename}")
        print(f"      Gui LLM: {len(clean_questions)} cau | Giu lai: {stats['kept']} cau")

        all_output_paths.append(output_path)

    print(f"\n{'='*60}")
    print(f"HOAN TAT: {len(all_output_paths)} file JSONL tao ra trong folder {md_path.stem}/")
    print(f"{'='*60}\n")

    return all_output_paths


def process_with_ai(questions, system_prompt, chunk_size=5):
    """Gửi câu hỏi cho AI để parse"""
    chunks = [questions[i:i + chunk_size] for i in range(0, len(questions), chunk_size)]
    all_results = []

    for i, chunk in enumerate(chunks, 1):
        print(f"\n  -> Chunk {i}/{len(chunks)}: Câu {[q['number'] for q in chunk]}...")

        chunk_parts = []
        for q in chunk:
            tags = f"[SECTION={q['section']}] [HAS_ANSWER={'YES' if q['has_answer'] else 'NO'}]"
            if q["answer_val"]:
                tags += f" [ANSWER={q['answer_val']}]"
            if q.get("has_solution"):
                tags += f" [HAS_SOLUTION=YES]"
            chunk_parts.append(f"{tags}\n{q['text']}")

        user_prompt = f"""Số hóa {len(chunk)} câu sau → trả về ĐÚNG {len(chunk)} JSON object.

⚠️ [HAS_ANSWER=NO]  → "answer": null. Dù biết đáp án → VẪN null. Không tự tính.
⚠️ [ANSWER=X]       → copy NGUYÊN giá trị X vào "answer". KHÔNG sửa, KHÔNG parse lại từ text.
⚠️ Ví dụ: [ANSWER=11,5] → "answer": "11,5" (KHÔNG phải "ĐÁP" hay "Đáp số").
⚠️ section=3        → KHÔNG có options A/B/C/D.
⚠️ Dùng ĐÚNG section từ [SECTION=X].
⚠️ [HAS_SOLUTION=YES] → copy lời giải đầy đủ vào "solution".

---
{"---".join(chunk_parts)}
---"""

        try:
            # Rate limiting cho OpenRouter
            time.sleep(3.5)

            response = client.chat.completions.create(
                model="glm-4.5-air",  # GLM model
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.0,
                max_tokens=8192
            )
            result_text = response.choices[0].message.content.strip()

            # Xóa code block markdown
            if "```" in result_text:
                result_text = re.sub(r'```[a-z]*\n|```', '', result_text)

            # Bóc tách JSON bằng đếm ngoặc {}
            parsed, stack, start = [], 0, -1
            for k, ch in enumerate(result_text):
                if ch == '{':
                    if stack == 0:
                        start = k
                    stack += 1
                elif ch == '}':
                    stack -= 1
                    if stack == 0 and start != -1:
                        parsed.append(result_text[start:k + 1])

            if len(parsed) != len(chunk):
                print(f"  WARNING Gui {len(chunk)} cau nhung nhan {len(parsed)} JSON!")

            for j, js in enumerate(parsed):
                all_results.append((js, chunk[j] if j < len(chunk) else None))

        except Exception as e:
            print(f"  ERROR API: {e}")
            # Thêm placeholder cho chunk bị lỗi
            for q in chunk:
                all_results.append((None, q))

    return all_results


def process_with_regex(questions):
    """Xử lý bằng regex khi không có AI"""
    results = []
    for q in questions:
        # Tạo JSON object cơ bản
        obj = {
            "section": q["section"],
            "content": {
                "stem": q["text"][:500]  # Giới hạn stem
            }
        }

        if q["section"] == 1:
            obj["content"]["options"] = []  # Cần parse thêm
            obj["content"]["answer"] = q["answer_val"] if q["has_answer"] else None
        elif q["section"] == 2:
            obj["content"]["statements"] = []  # Cần parse thêm
        elif q["section"] == 3:
            obj["content"]["answer"] = q["answer_val"] if q["has_answer"] else None

        obj["content"]["solution"] = None  # Cần parse thêm

        results.append((json.dumps(obj, ensure_ascii=False), q))
    return results


def validate_and_format(all_json_objs, questions_metadata):
    """Validate và format kết quả"""
    pretty_lines = []
    stats = {
        "kept": 0,
        "empty_stem": 0,
        "invalid_opt": 0,
        "forced_null": 0,
        "parse_err": 0
    }

    for json_str, q_meta in all_json_objs:
        if json_str is None:
            stats["parse_err"] += 1
            continue

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
            stem = re.sub(
                r'^\s*\*{0,2}[Cc]âu\s+\d+\*{0,2}[\.\:]?\s*',
                '',
                content.get("stem", "")
            ).strip()
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
                labels = [o.get("label", "").strip().rstrip(".")
                         for o in content.get("options", [])]
                if labels and labels != ["A", "B", "C", "D"][:len(labels)]:
                    stats["invalid_opt"] += 1
                    print(f"  WARNING Bo cau options loi: {labels}")
                    continue

            # Force null cho Section 1 & 3 nếu .md không có đáp án
            if q_meta and not q_meta["has_answer"]:
                if section == 1 or section == 3:
                    content["answer"] = None
                    if content.get("answer") is not None:
                        stats["forced_null"] += 1
                elif section == 2:
                    for stmt in content.get("statements", []):
                        stmt["answer"] = None

            # Force đúng answer nếu đã biết từ .md
            if q_meta and q_meta["has_answer"] and q_meta["answer_val"]:
                if section == 1:
                    val = q_meta["answer_val"].upper()
                    if re.fullmatch(r'[A-D]', val):
                        content["answer"] = val
                elif section == 3:
                    content["answer"] = q_meta["answer_val"]

            # Ràng buộc cuối: Section 1 answer chỉ được là A/B/C/D
            if section == 1:
                raw_ans = content.get("answer")
                if raw_ans is not None:
                    m_letter = re.search(r'\b([A-Da-d])\b', str(raw_ans))
                    if m_letter:
                        content["answer"] = m_letter.group(1).upper()
                    else:
                        content["answer"] = None

            # Ràng buộc cuối: Section 2 - mỗi statement answer chỉ được là "T", "F", hoặc null
            if section == 2:
                TRUE_WORDS = {"t", "true", "đúng", "dung", "đ", "yes", "1"}
                FALSE_WORDS = {"f", "false", "sai", "s", "no", "0"}
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
                        stmt["answer"] = None

            # Ràng buộc cuối: Section 3 - answer phải là giá trị ngắn
            if section == 3:
                raw_ans = content.get("answer")
                if raw_ans is not None:
                    cleaned = str(raw_ans).strip("*. ").upper()
                    if re.fullmatch(r'[A-D]', cleaned):
                        content["answer"] = None
                    elif len(cleaned) > 50:
                        content["answer"] = None
                    else:
                        content["answer"] = cleaned if cleaned else None

            obj["content"] = content

            # Xóa các trường không cần thiết
            for f in ["question_number", "question_id"]:
                obj.pop(f, None)

            pretty_lines.append(json.dumps(obj, ensure_ascii=False, indent=2))
            stats["kept"] += 1

        except json.JSONDecodeError as e:
            stats["parse_err"] += 1
            print(f"  WARNING Parse loi: {e} | {json_str[:100]}...")

    return pretty_lines, stats


def batch_process_directory(directory_path, use_ai=True, max_files=None):
    """Xử lý hàng loạt file trong thư mục"""
    md_dir = Path(directory_path)

    if not md_dir.exists():
        print(f"Thu muc khong ton tai: {directory_path}")
        return []

    md_files = sorted(list(md_dir.glob('*.md')))

    if max_files:
        md_files = md_files[:max_files]

    print(f"\n{'='*60}")
    print(f"BATCH PROCESS: {len(md_files)} files")
    print(f"Thu muc: {md_dir}")
    print(f"Use AI: {use_ai}")
    print(f"{'='*60}")

    results = []

    for i, md_file in enumerate(md_files, 1):
        print(f"\n[{i}/{len(md_files)}] ", end="")
        try:
            output_path = process_md_to_jsonl(md_file, use_ai=use_ai)
            results.append(output_path)
        except Exception as e:
            print(f"\n  ERROR processing {md_file.name}: {e}")

    # Tổng kết
    print(f"\n{'='*60}")
    print(f"BATCH COMPLETE!")
    print(f"{'='*60}")
    print(f"  Tong files: {len(md_files)}")
    print(f"  Thanh cong: {len(results)}")
    print(f"  That bai: {len(md_files) - len(results)}")
    print(f"{'='*60}\n")

    return results


if __name__ == "__main__":
    import sys

    # Mặc định xử lý md_outputs
    md_directory = r"C:\Users\taoda\OneDrive\Desktop\Choice\md\md_outputs"

    use_ai = True
    max_files = None

    # Parse arguments
    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == "--no-ai":
            use_ai = False
        elif arg.startswith("--max="):
            max_files = int(arg.split("=")[1])
        elif arg.startswith("--dir="):
            md_directory = arg.split("=")[1]
        elif not arg.startswith("--") and i == 1:
            # First positional arg is directory
            md_directory = arg
        i += 1

    # Chạy batch
    batch_process_directory(
        md_directory,
        use_ai=use_ai,
        max_files=max_files
    )
