"""
云观星传 - 缺陷修复回归测试

每个测试类对应一个已修复的 Bug，防止回归：
  Bug① rag_checker.verify_claim_semantic 曾给 chat_json 传不存在的 json_mode
       关键字，TypeError 被 try/except 吞掉 → LLM 语义校验静默失效
  Bug② LLMClient.chat 曾把 max_tokens=None 显式传给 API（部分端点拒绝）
  Bug③ _chat_with_search 曾丢失 temperature/max_tokens（硬编码默认值）
  Bug④ _fix_truncated_json 第二次扫描不跳过转义字符，导致补全括号错误
  Bug⑤ 阶段"失败→重跑成功"后 error 字段残留，前端持续展示陈旧错误
  Bug⑥ /result/{task_id} 等端点 task_id 直接拼磁盘路径与 glob 模式，
       存在路径穿越与 glob 注入
  Bug⑦ vector_store.chunk_text 在 overlap >= chunk_size 时 start 不前进，
       死循环
"""
import sys
import json
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import patch, MagicMock

# Mock 重型依赖（未安装时兜底；已安装则不影响）
# 注意：不能 mock httpx —— openai 依赖真实 httpx，误 mock 会让 OpenAI() 构造失败
for mod_name in ['faiss']:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()


# ===========================================================================
# Bug①: rag_checker 语义校验路径
# ===========================================================================

@pytest.fixture
def rag_checker_with_mocks():
    """构造 mock 依赖的 RAGChecker（不打真实 API / 不建索引）"""
    with patch("src.verification.rag_checker.get_vector_store") as m_get_vs, \
         patch("src.verification.rag_checker.get_llm_client") as m_get_llm:
        vs = MagicMock()
        vs.search.return_value = [
            {"text": "嫦娥六号带回1935.3克月壤", "metadata": {"source": "新华社"}},
            {"text": "嫦娥六号2024年6月25日返回地球", "metadata": {"source": "CNASA"}},
        ]
        m_get_vs.return_value = vs

        llm = MagicMock()
        llm.chat_json.return_value = {
            "consistent": True,
            "confidence": 0.9,
            "evidence_summary": "断言与参考文本一致",
            "key_sources": ["新华社"],
            "notes": "ok",
        }
        m_get_llm.return_value = llm

        from src.verification.rag_checker import RAGChecker
        yield RAGChecker(), llm, vs


class TestRagCheckerSemanticPath:
    """回归 Bug①：LLM 语义校验路径必须真正生效"""

    def test_semantic_path_actually_used(self, rag_checker_with_mocks):
        """verify_claim_semantic 应真正调用 chat_json 并返回语义结果"""
        checker, llm, _ = rag_checker_with_mocks
        result = checker.verify_claim_semantic("嫦娥六号带回1935.3克月壤")

        llm.chat_json.assert_called_once()
        assert result["semantic_check"] is True
        assert result["status"] == "supported"
        assert result["confidence"] == 0.9

    def test_no_illegal_json_mode_kwarg(self, rag_checker_with_mocks):
        """传给 chat_json 的关键字必须与其真实签名匹配（json_mode 不存在）"""
        checker, llm, _ = rag_checker_with_mocks
        checker.verify_claim_semantic("任意断言")

        from src.llm_client import LLMClient
        sig_params = set(
            __import__("inspect").signature(LLMClient.chat_json).parameters
        )
        kwargs = llm.chat_json.call_args.kwargs
        assert kwargs, "chat_json 应以关键字参数形式被调用"
        for k in kwargs:
            assert k in sig_params, (
                f"chat_json 收到不存在的关键字 {k!r}（会 TypeError 被吞掉，"
                f"语义校验静默失效——Bug① 回归）"
            )
        assert "json_mode" not in kwargs

    def test_verify_claim_no_silent_fallback(self, rag_checker_with_mocks):
        """verify_claim 语义路径成功时不得静默回退到相似度匹配"""
        checker, llm, vs = rag_checker_with_mocks
        result = checker.verify_claim("嫦娥六号带回1935.3克月壤")

        llm.chat_json.assert_called_once()
        # 回退路径（向量相似度）不应被触发
        vs.verify_claim.assert_not_called()
        assert result.get("semantic_check") is True


# ===========================================================================
# Bug②/③: LLMClient 参数透传
# ===========================================================================

def _make_client(base_url):
    from src.llm_client import LLMClient
    return LLMClient(
        api_key="sk-test-only", base_url=base_url,
        max_retries=1, retry_delay=0,
    )


def _fake_completion(content):
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = content
    return resp


class TestChatMaxTokens:
    """回归 Bug②：max_tokens=None 时不得把 None 显式传给 API"""

    def test_none_max_tokens_omitted(self):
        c = _make_client("https://api.example.com/v1")
        c.client = MagicMock()
        c.client.chat.completions.create.return_value = _fake_completion('{"ok": 1}')

        out = c.chat("sys", "user", max_tokens=None, json_mode=False)
        kw = c.client.chat.completions.create.call_args.kwargs

        assert "max_tokens" not in kw, (
            "max_tokens=None 时应省略该参数（显式 None 会被部分端点拒绝——Bug② 回归）"
        )
        assert out == '{"ok": 1}'

    def test_explicit_max_tokens_passed(self):
        c = _make_client("https://api.example.com/v1")
        c.client = MagicMock()
        c.client.chat.completions.create.return_value = _fake_completion("ok")

        c.chat("sys", "user", json_mode=False, temperature=0.7, max_tokens=256)
        kw = c.client.chat.completions.create.call_args.kwargs

        assert kw["max_tokens"] == 256
        assert kw["temperature"] == 0.7

    def test_default_json_mode_sets_response_format(self):
        c = _make_client("https://api.example.com/v1")
        c.client = MagicMock()
        c.client.chat.completions.create.return_value = _fake_completion('{}')

        c.chat("sys", "user")
        kw = c.client.chat.completions.create.call_args.kwargs
        assert kw["response_format"] == {"type": "json_object"}


class TestChatWithSearchParams:
    """回归 Bug③：联网搜索分支不得丢失 temperature/max_tokens"""

    def test_responses_api_receives_params(self):
        """百炼 Responses API 分支：temperature/max_tokens 必须透传"""
        c = _make_client("https://dashscope.aliyuncs.com/compatible-mode/v1")
        c.client = MagicMock()
        resp = MagicMock()
        resp.output_text = "搜索增强结果"
        c.client.responses.create.return_value = resp

        out = c.chat("sys", "user", enable_search=True, json_mode=False,
                     temperature=0.7, max_tokens=256)
        kw = c.client.responses.create.call_args.kwargs

        assert kw["temperature"] == 0.7, "temperature 被搜索分支吞掉——Bug③ 回归"
        assert kw["max_output_tokens"] == 256, "max_tokens 被搜索分支吞掉——Bug③ 回归"
        assert out == "搜索增强结果"
        # Responses 分支成功时不应再走 Completions
        c.client.chat.completions.create.assert_not_called()

    def test_responses_api_default_max_output_tokens(self):
        """max_tokens=None 时 Responses 分支使用默认上限 16384"""
        c = _make_client("https://dashscope.aliyuncs.com/compatible-mode/v1")
        c.client = MagicMock()
        resp = MagicMock()
        resp.output_text = "ok"
        c.client.responses.create.return_value = resp

        c.chat("sys", "user", enable_search=True, json_mode=False)
        kw = c.client.responses.create.call_args.kwargs
        assert kw["max_output_tokens"] == 16384

    def test_completions_fallback_receives_params(self):
        """非百炼平台回退分支：temperature/max_tokens 必须透传"""
        c = _make_client("https://api.deepseek.com/v1")
        c.client = MagicMock()
        c.client.chat.completions.create.return_value = _fake_completion("答案")

        out = c.chat("sys", "user", enable_search=True,
                     temperature=0.55, max_tokens=128)
        kw = c.client.chat.completions.create.call_args.kwargs

        assert kw["temperature"] == 0.55, "回退分支 temperature 丢失——Bug③ 回归"
        assert kw["max_tokens"] == 128, "回退分支 max_tokens 丢失——Bug③ 回归"
        assert out == "答案"


# ===========================================================================
# Bug④: _fix_truncated_json 转义字符处理
# ===========================================================================

class TestFixTruncatedJsonEscapes:
    """回归 Bug④：第二次扫描必须与第一次一样跳过转义字符"""

    def test_truncated_array_after_escaped_quote(self):
        """字符串含转义引号后数组截断，修复结果必须可解析且保留原值"""
        text = '{"text": "he said \\"hi\\"", "items": [1, 2'
        result = LLMClient_fix_truncated(text)
        assert result is not None
        parsed = json.loads(result)
        assert parsed["text"] == 'he said "hi"'

    def test_truncated_inside_string_after_escaped_quote(self):
        """转义引号之后的另一个字符串内部截断"""
        text = '{"a": "say \\"ok\\"", "b": "partial val'
        result = LLMClient_fix_truncated(text)
        assert result is not None
        parsed = json.loads(result)
        assert parsed["a"] == 'say "ok"'

    def test_multiple_escaped_quotes_truncation(self):
        """多个转义引号 + 对象截断"""
        text = '{"q1": "\\"quoted\\"", "q2": "\\"also\\"", "tail": {"x'
        result = LLMClient_fix_truncated(text)
        assert result is not None
        parsed = json.loads(result)
        assert parsed["q1"] == '"quoted"'
        assert parsed["q2"] == '"also"'


def LLMClient_fix_truncated(text):
    from src.llm_client import LLMClient
    return LLMClient._fix_truncated_json(text)


# ===========================================================================
# Bug⑤: 阶段失败重跑成功后清除 error
# ===========================================================================

@pytest.fixture
def project_store(tmp_path):
    from src.workflow.project import ProjectStore
    return ProjectStore(base_dir=tmp_path / "projects")


class TestStageErrorClearing:
    """回归 Bug⑤：失败→重跑成功后 error 必须清除"""

    def test_error_cleared_on_awaiting_review(self, project_store):
        from src.schemas import StageStatus
        p = project_store.create(title="A", interest="议题A")

        failed = project_store.update_stage(
            p.id, 1, status=StageStatus.FAILED, error="LLM 超时"
        )
        assert failed.stages["1"].error == "LLM 超时"

        ok = project_store.update_stage(
            p.id, 1, status=StageStatus.AWAITING_REVIEW, output={"topic": "t"}
        )
        assert ok.stages["1"].error is None, (
            "重跑成功（awaiting_review）后 error 残留——Bug⑤ 回归"
        )
        assert ok.stages["1"].output == {"topic": "t"}

    def test_error_cleared_on_completed(self, project_store):
        from src.schemas import StageStatus
        p = project_store.create(title="A", interest="议题A")

        project_store.update_stage(p.id, 1, status=StageStatus.FAILED, error="boom")
        done = project_store.update_stage(p.id, 1, status=StageStatus.COMPLETED)
        assert done.stages["1"].error is None

    def test_error_preserved_while_failed(self, project_store):
        """失败状态下 error 正常保留（不能误清）"""
        from src.schemas import StageStatus
        p = project_store.create(title="A", interest="议题A")

        running = project_store.update_stage(p.id, 1, status=StageStatus.RUNNING)
        assert running.stages["1"].error is None
        failed = project_store.update_stage(
            p.id, 1, status=StageStatus.FAILED, error="再次失败"
        )
        assert failed.stages["1"].error == "再次失败"

    def test_error_cleared_after_persistence_roundtrip(self, project_store):
        """清除后的 error 必须落盘（重读项目文件后仍为 None）"""
        from src.schemas import StageStatus
        p = project_store.create(title="A", interest="议题A")
        project_store.update_stage(p.id, 1, status=StageStatus.FAILED, error="x")
        project_store.update_stage(p.id, 1, status=StageStatus.AWAITING_REVIEW,
                                   output={"topic": "t"})
        reloaded = project_store.get(p.id)
        assert reloaded.stages["1"].error is None


# ===========================================================================
# Bug⑥: task_id 路径穿越 / glob 注入
# ===========================================================================

class TestIsSafeTaskId:
    """is_safe_task_id 白名单校验"""

    @pytest.mark.parametrize("tid", [
        "task_20260101120000_a1b2c3",
        "parl_20260101120000",
        "out_research_plan_20260101",
        "proj_1234567890",
        "a" * 128,
    ])
    def test_valid_ids(self, tid):
        from api.routes.security import is_safe_task_id
        assert is_safe_task_id(tid) is True

    @pytest.mark.parametrize("tid", [
        "",                      # 空
        "../..",                 # 相对穿越
        "..\\..\\.env",          # Windows 穿越读 .env
        "../../.env",
        "task/../../etc",        # 分隔符
        "a*b",                   # glob 元字符
        "a?b",
        "a[b]",
        "a b",                   # 空格
        "a.b",                   # 点（扩展名注入）
        "a" * 129,               # 超长
    ])
    def test_invalid_ids(self, tid):
        from api.routes.security import is_safe_task_id
        assert is_safe_task_id(tid) is False


@pytest.fixture
def analyze_module(tmp_path):
    with patch("src.pipeline.Pipeline"):
        import api.routes.analyze as mod
        mod.pipeline_results.clear()
        mod.pipeline_status.clear()
        original_dir = mod.RESULTS_DIR
        mod.RESULTS_DIR = tmp_path  # 隔离：不读真实 data/results
        yield mod
        mod.RESULTS_DIR = original_dir
        mod.pipeline_results.clear()
        mod.pipeline_status.clear()


@pytest.fixture
def parliament_module():
    with patch("src.pipeline.CognitiveParliament"):
        import api.routes.parliament as mod
        mod.parliament_results.clear()
        mod.parliament_status.clear()
        yield mod
        mod.parliament_results.clear()
        mod.parliament_status.clear()


@pytest.fixture
def outputs_module():
    import api.routes.outputs as mod
    mod.outputs_results.clear()
    mod.outputs_status.clear()
    yield mod
    mod.outputs_results.clear()
    mod.outputs_status.clear()


class TestAnalyzeResultTraversal:
    """回归 Bug⑥：/api/analyze/result/{task_id} 路径穿越防护"""

    @pytest.mark.parametrize("bad_id", ["../../.env", "..\\..\\.env", "*", "a*b"])
    def test_malicious_task_id_rejected(self, analyze_module, bad_id):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as ei:
            asyncio.run(analyze_module.get_task_result(bad_id))
        assert ei.value.status_code == 400

    def test_valid_unknown_id_returns_404_not_400(self, analyze_module):
        """合法但未知的 task_id 应 404（不影响正常流）"""
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as ei:
            asyncio.run(analyze_module.get_task_result("task_20260101120000_abc123"))
        assert ei.value.status_code == 404


class TestParliamentResultTraversal:
    """回归 Bug⑥：/api/parliament/result/{task_id} 穿越/glob 注入防护"""

    @pytest.mark.parametrize("bad_id", ["../../.env", "..\\..\\.env", "*", "a?b"])
    def test_malicious_task_id_rejected(self, parliament_module, bad_id,
                                        tmp_path):
        from fastapi import HTTPException
        original_dir = parliament_module.RESULTS_DIR
        parliament_module.RESULTS_DIR = tmp_path
        try:
            with pytest.raises(HTTPException) as ei:
                asyncio.run(parliament_module.get_parliament_result(bad_id))
            assert ei.value.status_code == 400
        finally:
            parliament_module.RESULTS_DIR = original_dir

    def test_valid_unknown_id_returns_404(self, parliament_module, tmp_path):
        from fastapi import HTTPException
        original_dir = parliament_module.RESULTS_DIR
        parliament_module.RESULTS_DIR = tmp_path
        try:
            with pytest.raises(HTTPException) as ei:
                asyncio.run(parliament_module.get_parliament_result(
                    "parl_20260101120000"))
            assert ei.value.status_code == 404
        finally:
            parliament_module.RESULTS_DIR = original_dir


class TestOutputsHelpersTraversal:
    """回归 Bug⑥：outputs 磁盘加载辅助函数的穿越/glob 防护"""

    @pytest.mark.parametrize("bad_id", ["../../.env", "..\\..\\.env", "*", "a?b"])
    def test_load_source_material_rejects_malicious_id(self, outputs_module,
                                                       bad_id, tmp_path):
        original_dir = outputs_module.RESULTS_DIR
        outputs_module.RESULTS_DIR = tmp_path
        try:
            assert outputs_module._load_source_material(bad_id) == {}
        finally:
            outputs_module.RESULTS_DIR = original_dir

    @pytest.mark.parametrize("bad_id", ["../../.env", "..\\..\\.env", "*", "a?b"])
    def test_load_output_result_rejects_malicious_id(self, outputs_module,
                                                     bad_id, tmp_path):
        original_dir = outputs_module.RESULTS_DIR
        outputs_module.RESULTS_DIR = tmp_path
        try:
            assert outputs_module._load_output_result(bad_id) is None
        finally:
            outputs_module.RESULTS_DIR = original_dir

    def test_traversal_cannot_escape_results_dir(self, outputs_module,
                                                 tmp_path):
        """穿越 id 不得读取 RESULTS_DIR 之外的文件"""
        secret = tmp_path / "secret.json"
        secret.write_text('{"leaked": true}', encoding="utf-8")
        # results 目录在 tmp_path/results，secret 在其上一级
        results = tmp_path / "results"
        results.mkdir()
        original_dir = outputs_module.RESULTS_DIR
        outputs_module.RESULTS_DIR = results
        try:
            material = outputs_module._load_source_material("../secret")
            assert material == {}
            assert outputs_module._load_output_result("../secret") is None
        finally:
            outputs_module.RESULTS_DIR = original_dir


# ===========================================================================
# Bug⑦: chunk_text 死循环
# ===========================================================================

@pytest.fixture
def bare_vector_store():
    """跳过 __init__ 的 VectorStore（不创建真实 embedding 客户端）"""
    from src.knowledge.vector_store import VectorStore
    return object.__new__(VectorStore)


class TestChunkTextTermination:
    """回归 Bug⑦：overlap >= chunk_size 时必须能终止"""

    def test_overlap_equal_chunk_size_terminates(self, bare_vector_store):
        chunks = bare_vector_store.chunk_text("x" * 100, chunk_size=10, overlap=10)
        assert len(chunks) >= 10
        assert all(c["text"] for c in chunks)

    def test_overlap_greater_chunk_size_terminates(self, bare_vector_store):
        chunks = bare_vector_store.chunk_text("x" * 50, chunk_size=10, overlap=20)
        assert len(chunks) >= 5
        assert all(c["text"] for c in chunks)

    def test_zero_chunk_size_terminates(self, bare_vector_store):
        chunks = bare_vector_store.chunk_text("abcdef", chunk_size=0, overlap=0)
        assert len(chunks) >= 1

    def test_negative_overlap_treated_as_zero(self, bare_vector_store):
        """负 overlap 不应跳过文本（等效 overlap=0 平铺切块）"""
        chunks = bare_vector_store.chunk_text("x" * 30, chunk_size=10, overlap=-5)
        assert len(chunks) == 3
        assert chunks[0]["text"] == "x" * 10
        assert chunks[-1]["text"] == "x" * 10

    def test_normal_overlap_preserved(self, bare_vector_store):
        """正常参数下重叠语义不变：相邻块重叠 overlap 字符"""
        text = "abcdefghij" * 5  # 50 字符
        chunks = bare_vector_store.chunk_text(text, chunk_size=10, overlap=3)
        assert chunks[0]["text"] == "abcdefghij"
        for a, b in zip(chunks, chunks[1:]):
            assert a["text"][-3:] == b["text"][:3]
        assert chunks[-1]["text"].endswith("ij")

    def test_chunk_ids_sequential(self, bare_vector_store):
        chunks = bare_vector_store.chunk_text("x" * 25, chunk_size=10, overlap=2)
        assert [c["chunk_id"] for c in chunks] == list(range(len(chunks)))

    def test_metadata_passthrough(self, bare_vector_store):
        chunks = bare_vector_store.chunk_text("x" * 25, chunk_size=10, overlap=2,
                                              metadata={"source": "doc1"})
        assert all(c["metadata"] == {"source": "doc1"} for c in chunks)
