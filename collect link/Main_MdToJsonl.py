import os
from MD_TO_JSONL import process_md_to_jsonl


def process_all(processed_folder):
    """
    Quét toàn bộ processed/ → tìm tất cả exam_X.md trong mọi bộ đề
    Bỏ qua file đã có .jsonl rồi
    """
    # Thu thập tất cả file .md cần xử lý
    todo = []
    for bo_de in sorted(os.listdir(processed_folder)):
        exams_dir = os.path.join(processed_folder, bo_de, "exams")
        if not os.path.isdir(exams_dir):
            continue
        for f in sorted(os.listdir(exams_dir)):
            if not f.endswith(".md"):
                continue
            md_path    = os.path.join(exams_dir, f)
            jsonl_path = md_path.replace(".md", ".jsonl")
            todo.append({
                "bo_de":      bo_de,
                "md_path":    md_path,
                "jsonl_path": jsonl_path,
                "done":       os.path.exists(jsonl_path)
            })

    total  = len(todo)
    done   = sum(1 for t in todo if t["done"])
    remain = total - done

    print(f"\n{'='*60}")
    print(f"📁 Thư mục : {processed_folder}")
    print(f"📋 Tổng    : {total} file | ✅ Xong: {done} | ⏳ Còn: {remain}")
    print(f"{'='*60}\n")

    success, failed, skipped = [], [], []

    for i, item in enumerate(todo, 1):
        label = f"[{i}/{total}] {item['bo_de']} / {os.path.basename(item['md_path'])}"

        # Bỏ qua nếu đã có .jsonl
        if item["done"]:
            print(f"⏭️  SKIP {label}")
            skipped.append(label)
            continue

        print(f"\n🔄 {label}")
        try:
            process_md_to_jsonl(item["md_path"])
            success.append(label)
        except Exception as e:
            print(f"❌ LỖI: {e}")
            failed.append(label)

    # Tổng kết
    print(f"\n{'='*60}")
    print(f"🏁 HOÀN TẤT")
    print(f"  ✅ Thành công : {len(success)}")
    print(f"  ⏭️  Đã skip    : {len(skipped)}")
    print(f"  ❌ Thất bại   : {len(failed)}")
    if failed:
        print(f"\n  ❌ Danh sách lỗi:")
        for f in failed:
            print(f"    - {f}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    processed_folder = r"c:/Users/taoda/OneDrive/Desktop/Choice/collect link/processed"
    process_all(processed_folder)