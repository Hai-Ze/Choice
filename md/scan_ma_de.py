"""
Quét tất cả file MD để tìm các pattern mã đề khác nhau
"""

import os
import re
from pathlib import Path
from collections import defaultdict

# Thư mục chứa file MD
md_dir = Path(r"C:\Users\taoda\OneDrive\Desktop\Choice\md\md_outputs")

# Các pattern có thể có của mã đề
patterns = [
    r'Mã đề\s*[:\.\-]\s*(\d+)',
    r'Mãđề\s*[:\.\-]\s*(\d+)',
    r'Ma de\s*[:\.\-]\s*(\d+)',
    r'CODE\s*[:\.\-]\s*(\d+)',
    r'Code\s*[:\.\-]\s*(\d+)',
    r'DE\s*[:\.\-]\s*(\d+)',
    r'Đề\s*[:\.\-]\s*(\d+)',
    r'Đề thi\s*[:\.\-]\s*(\d+)',
    r'Số báo danh\s*[:\.\-]\s*(\d+)',
    r'SBD\s*[:\.\-]\s*(\d+)',
    # Pattern mới
    r'ĐỀ ÔN TẬP TỐT NGHIỆP SỐ\s*(\d+)',
    r'ĐỀ\s*(\d+)',
    r'ĐỀ THI THỬ.*?ĐỀ\s*(\d+)',
    r'Đề số\s*(\d+)',
    # Pattern mới 2
    r'Mã đề thi\s*(\d+)',
]

results = defaultdict(list)
pattern_counts = defaultdict(int)

print("Dang quet cac file MD...")

for md_file in md_dir.glob("*.md"):
    try:
        with open(md_file, 'r', encoding='utf-8') as f:
            content = f.read()

        file_found = False

        # Test từng pattern
        for pattern in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                pattern_counts[pattern] += 1
                results[str(md_file.name)].extend(matches)
                file_found = True

        if not file_found:
            results[str(md_file.name)].append("KHONG CO MA DE")

    except Exception as e:
        results[str(md_file.name)].append(f"LOI: {e}")

# Ghi báo cáo
output_file = Path(r"C:\Users\taoda\OneDrive\Desktop\Choice\md\ma_de_report.txt")

with open(output_file, 'w', encoding='utf-8') as f:
    f.write("="*80 + "\n")
    f.write("BAO CAO MA DE TRONG CAC FILE MD\n")
    f.write("="*80 + "\n\n")

    f.write("THONG KE PATTERN:\n")
    f.write("-"*80 + "\n")
    for pattern, count in sorted(pattern_counts.items(), key=lambda x: -x[1]):
        f.write(f"  {pattern}: {count} file\n")

    f.write("\n" + "="*80 + "\n")
    f.write("CHI TIET THEO FILE:\n")
    f.write("="*80 + "\n\n")

    for filename, ma_de_list in sorted(results.items()):
        f.write(f"\n{filename}:\n")
        if "KHONG CO MA DE" in ma_de_list:
            f.write("  -> KHONG CO MA DE\n")
        elif "LOI:" in str(ma_de_list):
            f.write(f"  -> {ma_de_list[0]}\n")
        else:
            # Lọc unique và sắp xếp
            unique_ma_de = sorted(set(ma_de_list))
            f.write(f"  -> So ma de: {len(unique_ma_de)}\n")
            f.write(f"  -> Cac ma de: {', '.join(unique_ma_de)}\n")

print(f"Xong! Ket qua duoc ghi vao: {output_file}")
print(f"Tong file: {len(results)}")
print(f"File co ma de: {sum(1 for v in results.values() if 'KHONG CO MA DE' not in v and 'LOI:' not in str(v))}")
print(f"File khong co ma de: {sum(1 for v in results.values() if 'KHONG CO MA DE' in v)}")
