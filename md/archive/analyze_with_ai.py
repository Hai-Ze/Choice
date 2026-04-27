"""
Phan tich cau truc markdown dung AI API
- Ho tro Anthropic Claude API
- Ho tro GLM API (da co trong .env)
- Phan thong minh hown regex
"""

import os
import re
import json
from pathlib import Path
from collections import defaultdict
from dotenv import load_dotenv

# Load env
load_dotenv()

# Try import APIs
try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False
    print("Khong tim thay anthropic SDK. Run: pip install anthropic")


class AIParser:
    """Dung AI de phan tich cau truc file markdown"""

    def __init__(self, api_type="auto"):
        """
        api_type: 'anthropic', 'glm', hoac 'auto' (tu chon)
        """
        self.api_type = api_type
        self.client = None
        self._init_client()

    def _init_client(self):
        """Khoi tao API client"""

        # Thu Anthropic trc
        if self.api_type in ["anthropic", "auto"]:
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if api_key and HAS_ANTHROPIC:
                self.client = anthropic.Anthropic(api_key=api_key)
                self.api_type = "anthropic"
                print(f"Using Anthropic API")
                return

        # Thu GLM
        if self.api_type in ["glm", "auto"]:
            api_key = os.getenv("GLM_API_KEY")
            if api_key:
                # GLM su dung format tuong tu OpenAI
                try:
                    from openai import OpenAI
                    base_url = os.getenv("GLM_BASE_URL", "https://api.z.ai/api/paas/v4")
                    self.client = OpenAI(api_key=api_key, base_url=base_url)
                    self.api_type = "glm"
                    print(f"Using GLM API")
                    return
                except ImportError:
                    print("Khong tim thay openai SDK. Run: pip install openai")

        if not self.client:
            raise Exception("Khong the khoi tao API client. Kiem tra API key.")

    def analyze_structure(self, content, filename="unknown"):
        """
        Phan tich cau truc dung AI

        Returns: dict {
            'total_questions': int,
            'parts': {name: count},
            'has_dap_an': bool,
            'dap_an_location': str,
            'has_loi_giai': bool,
            'loi_giai_type': str,
        }
        """

        # Phan tich toan file - chia thanh cac phan neu qua dai
        MAX_CHARS = 30000  # Tang len tu 10000

        if len(content) > MAX_CHARS:
            # Chia file thanh cac phan
            parts = []
            for i in range(0, len(content), MAX_CHARS):
                parts.append(content[i:i+MAX_CHARS])

            # Phan tich tung phan
            all_results = []
            for i, part in enumerate(parts):
                prompt = f"""Ban la mot chuyen gia phan tich cau truc de thi toan. Hay phan tich PHAN {i+1}/{len(parts)} cua file markdown sau va tra ve JSON.

File: {filename} (Phan {i+1}/{len(parts)})

NOI DUNG:
{part}

YEU CAU:
1. Dem tong so cau hoi trong phan nay (co the la "Cau 1", "1.", hoac format khac)
2. Tim cac phan chia (Phan I, II, III hoac tuong tu) va dem so cau hoi trong moi phan
3. Xac dinh xem co dap an/ket qua khong (co the la "Đáp án", "Đáp số", "Answer", "Kết quả", v.v.)
4. Xac dinh xem co loi giai/giai dap/huong dan khong (co the la "Lời giải", "Giải", "Bài giải", "Hướng dẫn", "Gợi ý", v.v.)
5. Vi tri cua dap an/loi giai (sau de, cuoi file, hoac khong co)

TRA VE JSON DINH DANG:
{{
    "total_questions": <so luong cau hoi>,
    "parts": {{
        "Phần I": <so cau hoac null>,
        "Phần II": <so cau hoac null>,
        "Phần III": <so cau hoac null>
    }},
    "has_dap_an": <true/false>,
    "dap_an_type": <"dap an"/"dap so"/"ket qua"/null>,
    "dap_an_location": <"sau_de"/"cuoi_file"/"none">,
    "has_loi_giai": <true/false>,
    "loi_giai_type": <"loi giai"/"huong dan"/"goi y"/null>,
    "confidence": <0-1, do tin cay>
}}

CHI TRA VE JSON, KHONG COMMENT THEM BAT CU GI."""

                result = self._call_api(prompt)
                if result:
                    all_results.append(result)

            # Gop ket qua
            if all_results:
                return self._merge_results(all_results)
            else:
                return None

        else:
            # File ngan - phan tich binh thuong
            prompt = f"""Ban la mot chuyen gia phan tich cautruc de thi toan. Hay phan tich file markdown sau va tra ve KET QUA CHI DUOI DAY dinh dang JSON.

File: {filename}

NOI DUNG:
{content}

YEU CAU:
1. Dem tong so cau hoi (co the la "Cau 1", "1.", hoac format khac)
2. Tim cac phan chia (Phan I, II, III hoac tuong tu) va dem so cau hoi trong moi phan
3. Xac dinh xem co dap an/ket qua khong (co the la "Đáp án", "Đáp số", "Answer", "Kết quả", v.v.)
4. Xac dinh xem co loi giai/giai dap/huong dan khong (co the la "Lời giải", "Giải", "Bài giải", "Hướng dẫn", "Gợi ý", v.v.)
5. Vi tri cua dap an/loi giai (sau de, cuoi file, hoac khong co)

TRA VE JSON DINH DANG:
{{
    "total_questions": <so luong cau hoi>,
    "parts": {{
        "Phần I": <so cau hoac null>,
        "Phần II": <so cau hoac null>,
        "Phần III": <so cau hoac null>
    }},
    "has_dap_an": <true/false>,
    "dap_an_type": <"dap an"/"dap so"/"ket qua"/null>,
    "dap_an_location": <"sau_de"/"cuoi_file"/"none">,
    "has_loi_giai": <true/false>,
    "loi_giai_type": <"loi giai"/"huong dan"/"goi y"/null>,
    "confidence": <0-1, do tin cay>
}}

CHI TRA VE JSON, KHONG COMMENT THEM BAT CU GI."""

            return self._call_api(prompt)

    def _call_api(self, prompt):
        """Goi API va parse ket qua"""
        try:
            # Goi API
            if self.api_type == "anthropic":
                response = self.client.messages.create(
                    model="claude-3-haiku-20240307",
                    max_tokens=2048,  # Tang token limit
                    messages=[{"role": "user", "content": prompt}]
                )
                result_text = response.content[0].text

            elif self.api_type == "glm":
                response = self.client.chat.completions.create(
                    model="glm-4-plus",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=2048  # Tang token limit
                )
                result_text = response.choices[0].message.content

            # Parse JSON
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return result
            else:
                print(f"Khong tim thay JSON trong response")
                return None

        except Exception as e:
            print(f"Loi khi goi API: {e}")
            return None

    def _merge_results(self, all_results):
        """Gop ket qua tu nhieu phan"""
        merged = {
            "total_questions": 0,
            "parts": {},
            "has_dap_an": False,
            "dap_an_type": None,
            "dap_an_location": "none",
            "has_loi_giai": False,
            "loi_giai_type": None,
            "confidence": 0
        }

        for result in all_results:
            merged["total_questions"] += result.get("total_questions", 0)

            # Gop parts
            for part, count in result.get("parts", {}).items():
                if part in merged["parts"]:
                    merged["parts"][part] += count
                else:
                    merged["parts"][part] = count

            # Gop dap_an
            if result.get("has_dap_an"):
                merged["has_dap_an"] = True
                if not merged["dap_an_type"]:
                    merged["dap_an_type"] = result.get("dap_an_type")

            # Gop loi_giai
            if result.get("has_loi_giai"):
                merged["has_loi_giai"] = True
                if not merged["loi_giai_type"]:
                    merged["loi_giai_type"] = result.get("loi_giai_type")

            # Location (uu tien "sau_de" hon "cuoi_file")
            if result.get("dap_an_location") == "sau_de":
                merged["dap_an_location"] = "sau_de"
            elif merged["dap_an_location"] == "none" and result.get("dap_an_location"):
                merged["dap_an_location"] = result.get("dap_an_location")

            # Average confidence
            merged["confidence"] = max(merged["confidence"], result.get("confidence", 0))

        return merged

    def analyze_structure_old(self, content, filename="unknown"):
        """Phuong thuc cu - dung cho file ngan"""
        return self.analyze_structure(content, filename)


def analyze_all_files_ai(directory_path, max_files=None):
    """Phan tich tat ca file dung AI"""
    md_dir = Path(directory_path)

    if not md_dir.exists():
        print(f"Thu muc khong ton tai: {directory_path}")
        return []

    md_files = sorted(list(md_dir.glob('*.md')))

    if max_files:
        md_files = md_files[:max_files]

    print(f"Tim thay {len(md_files)} file markdown")

    # Khoi tai AI parser
    try:
        parser = AIParser(api_type="auto")
    except Exception as e:
        print(f"Khong the khoi tao AI: {e}")
        print("Vui long cai dat API key trong file .env:")
        print("  ANTHROPIC_API_KEY=your_key")
        print("  hoac")
        print("  GLM_API_KEY=your_key")
        return []

    results = []

    for i, md_file in enumerate(md_files, 1):
        print(f"\n[{i}/{len(md_files)}] Dang phan tich: {md_file.name}...")

        try:
            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read()

            result = parser.analyze_structure(content, md_file.name)

            if result:
                result['filename'] = md_file.name
                result['file_size'] = os.path.getsize(md_file)
                results.append(result)
                print(f"  OK: {result['total_questions']} cau, confidence={result.get('confidence', 0)}")
            else:
                print(f"  FAIL: Khong the phan tich")

        except Exception as e:
            print(f"  ERROR: {e}")

    return results


def generate_ai_report(results, output_file):
    """Tao bao cao tu ket qua AI"""

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("BAO CAO PHAN TICH AI - CAU TRUC DE TOAN\n")
        f.write("=" * 80 + "\n\n")

        f.write(f"Tong so file: {len(results)}\n\n")

        # Thong ke
        total_questions = sum(r.get('total_questions', 0) for r in results)
        with_dapan = sum(1 for r in results if r.get('has_dap_an'))
        with_loigiai = sum(1 for r in results if r.get('has_loi_giai'))

        f.write("=== THONG KE TONG HOP ===\n")
        f.write(f"Tong so cau hoi: {total_questions}\n")
        f.write(f"Trung binh cau/file: {total_questions/len(results):.1f}\n")
        f.write(f"Co dap an: {with_dapan}/{len(results)} ({with_dapan/len(results)*100:.1f}%)\n")
        f.write(f"Co loi giai: {with_loigiai}/{len(results)} ({with_loigiai/len(results)*100:.1f}%)\n\n")

        # Phan bo theo cau truc
        part_counts = defaultdict(int)
        for r in results:
            parts = r.get('parts', {})
            key = "|".join(sorted([f"{k}:{v}" for k, v in parts.items() if v]))
            part_counts[key] += 1

        f.write("=== PHAN BO THEO CAU TRUC ===\n")
        for struct, count in sorted(part_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
            f.write(f"{struct or 'no_parts'}: {count} file\n")

        f.write("\n" + "=" * 80 + "\n")
        f.write("CHI TIET TUNG FILE\n")
        f.write("=" * 80 + "\n\n")

        for r in results:
            f.write(f"FILE: {r['filename']}\n")
            f.write(f"Kich thuoc: {r['file_size']:,} bytes\n")
            f.write(f"Tong cau: {r.get('total_questions', 0)}\n")

            parts = r.get('parts', {})
            if parts:
                f.write("Phan chia:\n")
                for name, count in parts.items():
                    if count:
                        f.write(f"  {name}: {count} cau\n")
            else:
                f.write("Khong co phan chia ro\n")

            f.write(f"Dap an: {'CO' if r.get('has_dap_an') else 'KHONG'}")
            if r.get('dap_an_type'):
                f.write(f" ({r['dap_an_type']})")
            f.write(f"\n")

            f.write(f"Loi giai: {'CO' if r.get('has_loi_giai') else 'KHONG'}")
            if r.get('loi_giai_type'):
                f.write(f" ({r['loi_giai_type']})")
            f.write(f"\n")

            f.write(f"Do tin cay: {r.get('confidence', 0)*100:.0f}%\n")
            f.write("-" * 80 + "\n\n")

    print(f"Da luu bao cao: {output_file}")
    return output_file


if __name__ == "__main__":
    import sys

    md_directory = r"C:\Users\taoda\OneDrive\Desktop\Choice\md\md_outputs"

    if len(sys.argv) > 1:
        md_directory = sys.argv[1]

    # Test vai file trc
    print("DANG PHAN TICH DUNG AI...")
    print("=" * 60)

    # Phan tich tat ca (hoac gioi han)
    results = analyze_all_files_ai(md_directory, max_files=None)

    if results:
        output_file = Path(md_directory).parent / "ai_analysis_report.txt"
        generate_ai_report(results, output_file)

        print("\n" + "=" * 60)
        print("HOAN TAT!")
        print(f"Da phan tich {len(results)} file")
        print(f"Bao cao: {output_file}")
