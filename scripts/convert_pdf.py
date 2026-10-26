
import fitz  # pymupdf
from app.common.path import DATA_DIR, PDF_DIR

# 如果输出目录不存在，就创建它。
DATA_DIR.mkdir(parents=True, exist_ok=True)

# 遍历 PDF 目录下所有 PDF 文件。
for pdf_path in PDF_DIR.glob("*.pdf"):
    txt_path = DATA_DIR / pdf_path.with_suffix(".txt").name

    print(f"正在转换: {pdf_path.name} ...")

    # 打开 PDF
    all_text = []
    with fitz.open(pdf_path) as doc:
        for page in doc:
            text = page.get_text()
            all_text.append(text)

    # 写入 TXT
    with txt_path.open("w", encoding="utf-8") as f:
        f.write("\n\n".join(all_text))

    doc.close()
    print(f"  已完成 -> {txt_path.name}")

print("\n全部转换完成！")
