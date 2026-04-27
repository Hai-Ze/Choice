"""
Chay batch va don dep tu dong khi hoan tat
"""

import sys
import time
sys.path.append(r"c:\Users\taoda\OneDrive\Desktop\Choice\md")

from md_to_jsonl import batch_process_directory

md_directory = r"C:\Users\taoda\OneDrive\Desktop\Choice\md\md_outputs"

print("="*60)
print("BATCH CONVERSION + AUTO CLEANUP")
print("="*60)
print(f"Directory: {md_directory}")
print(f"Output: jsonl_output/")
print(f"Total files: 87")
print("="*60)

# 1. Chay batch
print("\n[1/2] DANG CHAY BATCH CONVERSION...")
results = batch_process_directory(
    md_directory,
    use_ai=True,
    max_files=None
)

# 2. Don dep
print("\n[2/2] DANG DON DEP...")
sys.path.append(r"c:\Users\taoda\OneDrive\Desktop\Choice\md")
from cleanup import cleanup_after_batch
cleanup_after_batch(md_directory)

print("\n" + "="*60)
print("HOAN TAT TAT CA!")
print("="*60)
print(f"Da chuyen doi: {len(results)} files")
print(f"Da don dep: xoa file tam thoi")
print(f"\nCau truc cuoi:")
print(f"  md_outputs/")
print(f"    ├── *.md (87 files goc)")
print(f"    └── jsonl_output/")
print(f"        └── *.jsonl ({len(results)} files)")
print("="*60)
