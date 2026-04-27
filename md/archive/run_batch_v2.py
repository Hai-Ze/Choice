"""
Run batch conversion - Save to jsonl_output folder
"""

import sys
sys.path.append(r"c:\Users\taoda\OneDrive\Desktop\Choice\md")

from md_to_jsonl import batch_process_directory

md_directory = r"C:\Users\taoda\OneDrive\Desktop\Choice\md\md_outputs"

print("Starting batch conversion...")
print(f"Directory: {md_directory}")
print(f"Output: jsonl_output/")
print(f"Total files will be processed: 87")
print()

results = batch_process_directory(
    md_directory,
    use_ai=True,
    max_files=None  # Process all
)

print("\nBatch complete!")
print(f"Successfully converted: {len(results)} files")
print(f"Output folder: jsonl_output/")
