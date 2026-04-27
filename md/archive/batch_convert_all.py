import json
import sys
from pathlib import Path

# Fix encoding cho Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def clean_text(text):
    """GIỮ NGUYÊN y nguyên text từ JSON"""
    if not text:
        return ""

    # KHÔNG thay đổi gì cả, trả về nguyên văn
    return text

def process_json_folder(json_folder, output_file):
    """Xử lý một folder JSON và xuất ra 1 file MD"""
    json_path = Path(json_folder)
    json_files = sorted(json_path.glob('*.json'))

    if not json_files:
        return None

    all_content = []

    for json_file in json_files:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Thêm separator
            all_content.append(f"\n\n{'='*60}\n")
            all_content.append(f"# {json_file.stem}\n")
            all_content.append(f"{'='*60}\n\n")

            for item in data:
                if isinstance(item, dict):
                    category = item.get('category', 'Text')
                    text = clean_text(item.get('text', ''))

                    # Xử lý category
                    if category in ['Image', 'Figure', 'Picture', 'Pic']:
                        # Ghi chú vị trí hình ảnh
                        all_content.append(f"\n📷 **[HÌNH ẢNH TẠI ĐÂY]**\n\n")
                        continue

                    if not text:
                        continue

                    if category == 'Title':
                        all_content.append(f"## {text}\n")
                    elif category == 'Section-header':
                        all_content.append(f"### {text}\n")
                    else:
                        # Giữ nguyên text, kể cả Table HTML
                        all_content.append(f"{text}\n")

        except Exception as e:
            all_content.append(f"# Lỗi: {e}\n")

    # Ghi file
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(''.join(all_content))

    return len(json_files)

def batch_convert_all(input_root, output_root):
    """Chuyển tất cả folder trong input_root"""
    input_path = Path(input_root)
    output_path = Path(output_root)

    # Tạo thư mục output
    output_path.mkdir(parents=True, exist_ok=True)

    # Lấy danh sách tất cả folder
    folders = [f for f in input_path.iterdir() if f.is_dir()]

    print(f"📁 Tìm thấy {len(folders)} thư mục trong {input_root}")
    print(f"📝 Xuất ra: {output_root}\n")
    print("="*60)

    success = 0
    failed = 0

    for i, folder in enumerate(folders, 1):
        output_file = output_path / f"{folder.name}.md"
        print(f"[{i}/{len(folders)}] {folder.name[:50]}... ", end='', flush=True)

        try:
            count = process_json_folder(folder, output_file)
            if count:
                print(f"✓ ({count} files)")
                success += 1
            else:
                print(f"⚠ (không có file JSON)")
                failed += 1
        except Exception as e:
            print(f"✗ Lỗi: {e}")
            failed += 1

    print("="*60)
    print(f"\n✅ Hoàn tất!")
    print(f"   - Thành công: {success} thư mục")
    print(f"   - Thất bại: {failed} thư mục")
    print(f"   - File output: {output_root}")

if __name__ == "__main__":
    print("="*60)
    print("  BATCH JSON → MARKDOWN CONVERTER")
    print("="*60)
    print()

    if len(sys.argv) < 2:
        print("Cách dùng:")
        print("  python batch_convert_all.py <input_folder> [output_folder]")
        print()
        print("Ví dụ:")
        print("  python batch_convert_all.py outputs_2")
        print("  python batch_convert_all.py outputs_2 md_output")
        sys.exit(1)

    input_folder = sys.argv[1]
    output_folder = sys.argv[2] if len(sys.argv) > 2 else "md_output"

    batch_convert_all(input_folder, output_folder)
