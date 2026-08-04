"""
知识库四库种子数据入库 CLI

将 data/libraries/{library}/ 下的种子文档（方法库/顶刊范文库/理论库/文献库）
分块向量化并入索引。

用法：
    python scripts/seed_libraries.py                 # 四库全部入库
    python scripts/seed_libraries.py --library method # 仅方法库
    python scripts/seed_libraries.py --stats          # 只查看四库状态，不入库
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from src.knowledge.libraries import LIBRARY_TYPES, build_library_index, get_library_stats


def main():
    parser = argparse.ArgumentParser(description="知识库四库种子数据入库")
    parser.add_argument("--library", type=str, default="all",
                        choices=["all"] + sorted(LIBRARY_TYPES.keys()),
                        help="指定库（默认 all 全部入库）")
    parser.add_argument("--stats", action="store_true", help="只查看四库状态")
    args = parser.parse_args()

    print("=" * 60)
    print("  云观星传 - 知识库四库种子数据")
    print("=" * 60)

    libs = sorted(LIBRARY_TYPES.keys()) if args.library == "all" else [args.library]

    if args.stats:
        for s in get_library_stats():
            print(f"  [{s['key']}] {s['name']}: 种子文件 {s['file_count']} 个，入库块 {s['chunk_count']}")
        return 0

    for lib in libs:
        try:
            n = build_library_index(lib)
            meta = LIBRARY_TYPES[lib]
            print(f"  ✓ [{lib}] {meta['name']}: 入库 {n} 个文档块")
        except Exception as e:
            print(f"  ✗ [{lib}] 入库失败: {e}")

    print("=" * 60)
    print("  完成。向量索引保存在 data/kg/vectors.faiss")
    print("  提示：分库检索请调用 /api/knowledge/search?library=<库名>&q=<关键词>")
    return 0


if __name__ == "__main__":
    sys.exit(main())
