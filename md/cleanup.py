"""
Don dep sau khi batch conversion hoan tat
- Giu lai: file .md goc + file .jsonl trong jsonl_output
- Xoa: file .jsonl o thu muc cha, cac file report tam thoi
"""

import os
import sys
from pathlib import Path

def cleanup_after_batch(md_directory):
    """Don dep sau khi batch hoan tat"""

    md_dir = Path(md_directory)
    jsonl_dir = md_dir / "jsonl_output"

    print("="*60)
    print("DON DEP SAU BATCH CONVERSION")
    print("="*60)

    # 1. Dem file .jsonl trong thu muc cha
    parent_jsonl = list(md_dir.glob("*.jsonl"))
    print(f"\n1. File .jsonl o thu muc cha: {len(parent_jsonl)}")

    if parent_jsonl:
        print(f"   -> Can xong: {len(parent_jsonl)} file")

        # Xoa file .jsonl o thu muc cha
        for f in parent_jsonl:
            try:
                f.unlink()
                print(f"   - Da xoa: {f.name}")
            except Exception as e:
                print(f"   - LOI xoa {f.name}: {e}")

    # 2. Dem file .jsonl trong jsonl_output
    if jsonl_dir.exists():
        jsonl_files = list(jsonl_dir.glob("*.jsonl"))
        print(f"\n2. File .jsonl trong jsonl_output: {len(jsonl_files)}")
        print(f"   -> GIU LAI (file chinh)")
    else:
        print(f"\n2. Folder jsonl_output KHONG ton tai")

    # 3. Xoa cac file report tam thoi
    temp_files = [
        "structure_report.md",
        "structure_summary.txt",
        "structure_detailed.txt",
        "multi_exam_report.txt",
        "ai_analysis_report.txt"
    ]

    print(f"\n3. File report tam thoi:")
    for fname in temp_files:
        fpath = md_dir.parent / fname
        if fpath.exists():
            try:
                fpath.unlink()
                print(f"   - Da xoa: {fname}")
            except Exception as e:
                print(f"   - LOI xoa {fname}: {e}")

    # 4. Tong ket
    print(f"\n{'='*60}")
    print("TONG KET DON DEP")
    print(f"{'='*60}")
    print(f"Thu muc .md: {md_dir}")
    print(f"  - File .md: {len(list(md_dir.glob('*.md')))}")
    print(f"  - File .jsonl: {len(list(md_dir.glob('*.jsonl')))} (nen la 0)")

    if jsonl_dir.exists():
        print(f"\nThu muc jsonl_output: {jsonl_dir}")
        print(f"  - File .jsonl: {len(list(jsonl_dir.glob('*.jsonl')))}")

    print(f"\nCac file da GIU LAI:")
    print(f"  - File .md goc (87 files)")
    print(f"  - File .jsonl trong jsonl_output/")

    print(f"\nCac file DA XOA:")
    print(f"  - File .jsonl o thu muc cha")
    print(f"  - File report tam thoi")

    print(f"\n{'='*60}")
    print("HOAN TAT DON DEP!")
    print(f"{'='*60}")


if __name__ == "__main__":
    md_directory = r"C:\Users\taoda\OneDrive\Desktop\Choice\md\md_outputs"

    if len(sys.argv) > 1:
        md_directory = sys.argv[1]

    cleanup_after_batch(md_directory)
