"""
文档录入命令行入口
解析上传的文档（txt/md/pdf/docx），按自定义规则智能切片后写入向量库

用法：
    python scripts/ingest_docs.py data/uploads/xxx.pdf          # 单文件入库
    python scripts/ingest_docs.py data/uploads/                  # 目录内全部入库
    python scripts/ingest_docs.py doc.md --preview               # 只预览切片，不入库
    python scripts/ingest_docs.py doc.txt --chunk-max 600        # 自定义切片大小
"""
import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

from src.knowledge.preprocessor import get_preprocessor, SUPPORTED_EXTS


def collect_files(paths: list) -> list:
    """展开文件/目录参数为文件列表"""
    files = []
    for p in paths:
        p = Path(p)
        if p.is_dir():
            for f in sorted(p.iterdir()):
                if f.is_file() and f.suffix.lower() in SUPPORTED_EXTS:
                    files.append(f)
        elif p.is_file():
            if p.suffix.lower() not in SUPPORTED_EXTS:
                raise ValueError(
                    f"不支持的文件类型 '{p.suffix}'，仅支持: {', '.join(sorted(SUPPORTED_EXTS))}"
                )
            files.append(p)
        else:
            raise FileNotFoundError(f"路径不存在: {p}")
    return files


def main():
    parser = argparse.ArgumentParser(description="文档预处理与智能切片入库工具")
    parser.add_argument("paths", nargs="+", help="文件或目录路径（可多个）")
    parser.add_argument("--preview", action="store_true",
                        help="只预览切片结果，不写入向量库")
    parser.add_argument("--chunk-min", type=int, default=300, help="每块最少字数（默认 300）")
    parser.add_argument("--chunk-max", type=int, default=500, help="每块最多字数（默认 500）")
    parser.add_argument("--overlap", type=int, default=50, help="相邻块重叠字数（默认 50）")
    parser.add_argument("--library", type=str, default="",
                        choices=["", "journal_article", "theory", "top_journal_example", "method"],
                        help="入库到指定知识库（四库：journal_article/theory/top_journal_example/method）；默认普通上传")
    args = parser.parse_args()

    print("=" * 60)
    print("  云观星传 - 文档预处理与智能切片")
    print("=" * 60)

    try:
        files = collect_files(args.paths)
    except (ValueError, FileNotFoundError) as e:
        print(f"✗ {e}")
        sys.exit(1)

    if not files:
        print("✗ 未找到可处理的文件")
        sys.exit(1)

    print(f"待处理文件: {len(files)} 个")
    for f in files:
        print(f"  - {f}")

    preprocessor = get_preprocessor()
    total_chunks = 0

    for file in files:
        print(f"\n[{file}] 处理中...")
        try:
            text = preprocessor.extract_text(file)
            if not text.strip():
                print("  ✗ 未提取到文本内容")
                continue
            chunks = preprocessor.smart_chunk(
                text,
                source=file.name,
                chunk_min=args.chunk_min,
                chunk_max=args.chunk_max,
                overlap=args.overlap,
            )
            print(f"  ✓ 解析出 {len(chunks)} 个文档块")

            if args.preview:
                total_chunks += len(chunks)
                for c in chunks[:5]:
                    print(f"    ── [{c.section or '(无标题)'}] ({c.language}, "
                          f"{c.date or '无日期'})")
                    print(f"       {c.text[:60].replace(chr(10), ' ')}...")
                if len(chunks) > 5:
                    print(f"    ... 其余 {len(chunks) - 5} 块省略")
            else:
                preprocessor.ingest_chunks(chunks, library=args.library)
                total_chunks += len(chunks)
        except Exception as e:
            print(f"  ✗ 处理失败: {e}")
            continue

    if not args.preview:
        print(f"\n{'=' * 60}")
        print(f"  完成：共入库 {total_chunks} 个文档块")
        print(f"  （向量索引保存在 data/kg/vectors.faiss）")
    else:
        print(f"\n预览模式：共 {total_chunks} 个待入库块（未写入）")
        print("去掉 --preview 参数即可入库")

    return 0


if __name__ == "__main__":
    sys.exit(main())
