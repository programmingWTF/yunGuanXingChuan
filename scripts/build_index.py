"""
构建 FAISS 向量索引
从 data/science/ 和 data/media/ 目录加载文档，调用 embedding API 向量化后保存索引

用法：
    python scripts/build_index.py
"""
import sys
from pathlib import Path

# 确保项目根目录在 path 中
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.knowledge.vector_store import get_vector_store


def main():
    print("=" * 60)
    print("  云观星传 - 向量索引构建工具")
    print("=" * 60)

    store = get_vector_store()

    print("\n[1/3] 加载文档...")
    documents = store._load_all_documents()
    print(f"  共加载 {len(documents)} 个文档")

    if not documents:
        print("\n✗ 没有找到可索引的文档！")
        print("  请确保 data/science/ 和 data/media/ 目录下有 JSON 文件")
        return

    print("\n[2/3] 向量化 + 构建 FAISS 索引...")
    print("  （这一步会调用 embedding API，可能需要几分钟）")
    store.build_index(documents)

    print("\n[3/3] 验证索引...")
    if store.index and store.index.ntotal > 0:
        print(f"  ✓ 索引构建成功！共 {store.index.ntotal} 个向量")
        print(f"  保存位置: {store.index_path}")

        # 测试检索
        print("\n[测试] 尝试检索 '嫦娥六号发射时间'...")
        results = store.search("嫦娥六号发射时间", top_k=3)
        if results:
            for i, r in enumerate(results):
                print(f"  [{i+1}] score={r['score']:.3f} | {r['text'][:60]}...")
        else:
            print("  ✗ 检索无结果（可能 embedding API 调用失败）")
    else:
        print("  ✗ 索引为空，构建失败")
        print("  请检查：")
        print("  1. .env 中 QWEN_API_KEY 和 QWEN_BASE_URL 是否正确")
        print("  2. embedding 模型是否可用（text-embedding-v4）")
        print("  3. 网络是否通畅")


if __name__ == "__main__":
    main()
