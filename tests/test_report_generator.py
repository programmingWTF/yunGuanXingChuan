"""
云观星传 - 校验报告生成器单元测试
覆盖报告统计、问题清单、建议生成、迭代对比与落盘
"""
import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import MagicMock

for mod_name in ['faiss', 'httpx']:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()


def _make_result(status, claim="测试断言", confidence=0.8, notes=""):
    """构造 VerificationResult"""
    from src.schemas import VerificationResult, VerificationStatus
    return VerificationResult(
        claim=claim,
        status=VerificationStatus(status),
        confidence=confidence,
        notes=notes,
    )


@pytest.fixture
def generator():
    from src.verification.report_generator import ReportGenerator
    return ReportGenerator()


class TestGenerateVerificationReport:
    """校验报告生成测试"""

    def test_summary_statistics(self, generator):
        """统计各状态数量与验证率"""
        from src.schemas import VerificationStatus
        results = [
            _make_result("verified", "断言1", 0.9),
            _make_result("verified", "断言2", 0.85),
            _make_result("partial", "断言3", 0.6),
            _make_result("conflicting", "断言4", 0.3),
            _make_result("unverified", "断言5", 0.1),
        ]
        report = generator.generate_verification_report(results, topic="嫦娥六号", iteration_round=2)
        s = report["summary"]
        assert s["total_claims"] == 5
        assert s["verified"] == 2
        assert s["partially_verified"] == 1
        assert s["conflicting"] == 1
        assert s["unverified"] == 1
        # verification_rate = (verified + partial) / total
        assert abs(s["verification_rate"] - 3 / 5) < 1e-9
        # avg_confidence
        assert abs(s["avg_confidence"] - (0.9 + 0.85 + 0.6 + 0.3 + 0.1) / 5) < 1e-9
        assert report["topic"] == "嫦娥六号"
        assert report["iteration_round"] == 2
        assert report["timestamp"]

    def test_empty_results(self, generator):
        """空结果不应除零"""
        report = generator.generate_verification_report([])
        assert report["summary"]["total_claims"] == 0
        assert report["summary"]["verification_rate"] == 0
        assert report["summary"]["avg_confidence"] == 0

    def test_issues_only_problematic(self, generator):
        """issues 应只含 conflicting/unverified 断言"""
        results = [
            _make_result("verified", "好断言"),
            _make_result("unverified", "坏断言"),
            _make_result("conflicting", "冲突断言"),
        ]
        report = generator.generate_verification_report(results)
        issue_claims = [i["claim"] for i in report["issues"]]
        assert "好断言" not in issue_claims
        assert "坏断言" in issue_claims
        assert "冲突断言" in issue_claims

    def test_details_contain_all(self, generator):
        """details 应包含全部断言"""
        results = [
            _make_result("verified", "断言A"),
            _make_result("unverified", "断言B"),
        ]
        report = generator.generate_verification_report(results)
        assert len(report["details"]) == 2


class TestGenerateRecommendations:
    """改进建议生成测试"""

    def test_conflict_recommendation(self, generator):
        results = [_make_result("conflicting", "冲突断言")]
        recs = generator._generate_recommendations(results)
        assert any("冲突" in r for r in recs)

    def test_unverified_recommendation(self, generator):
        results = [_make_result("unverified", "无法验证断言")]
        recs = generator._generate_recommendations(results)
        assert any("无法验证" in r for r in recs)

    def test_low_confidence_recommendation(self, generator):
        """低置信（<0.5）应有专门建议"""
        results = [_make_result("verified", "低置信断言", confidence=0.3)]
        recs = generator._generate_recommendations(results)
        assert any("置信度较低" in r for r in recs)

    def test_all_good_recommendation(self, generator):
        """全部通过时应给出质量良好提示"""
        results = [
            _make_result("verified", "断言1", 0.95),
            _make_result("verified", "断言2", 0.9),
        ]
        recs = generator._generate_recommendations(results)
        assert any("质量良好" in r for r in recs)
        assert len(recs) == 1


class TestIterationComparison:
    """迭代对比报告测试"""

    def test_empty_history(self, generator):
        assert generator.generate_iteration_comparison([]) == {"message": "没有迭代历史"}

    def test_single_round(self, generator):
        history = [{"round": 1, "scores": {"factual": 80}, "weighted_total": 80, "passed": False}]
        cmp = generator.generate_iteration_comparison(history)
        assert cmp["total_rounds"] == 1
        assert cmp["rounds"][0]["round"] == 1
        assert cmp["improvement"] == {}

    def test_improvement_calculation(self, generator):
        """多轮时应计算首尾差值"""
        history = [
            {"round": 1, "scores": {"factual": 70, "fluency": 75}, "weighted_total": 71},
            {"round": 2, "scores": {"factual": 85, "fluency": 75}, "weighted_total": 84},
        ]
        cmp = generator.generate_iteration_comparison(history)
        assert cmp["improvement"]["factual"] == 15
        assert cmp["improvement"]["fluency"] == 0
        assert cmp["total_rounds"] == 2

    def test_missing_scores_default(self, generator):
        """缺 round 字段时按索引补默认"""
        history = [{"scores": {}, "weighted_total": 50}]
        cmp = generator.generate_iteration_comparison(history)
        assert cmp["rounds"][0]["round"] == 1
        assert cmp["rounds"][0]["passed"] is False


class TestSaveReport:
    """报告落盘测试"""

    def test_save_to_custom_path(self, generator, tmp_path):
        """应保存 JSON 到指定路径（自动建目录）"""
        report = {"topic": "测试", "summary": {"total_claims": 0}}
        out = tmp_path / "nested" / "dir" / "report.json"
        generator.save_report(report, output_path=out)
        assert out.exists()
        loaded = json.loads(out.read_text(encoding="utf-8"))
        assert loaded["topic"] == "测试"

    def test_save_default_path(self, generator):
        """不传路径时应写到模块默认位置 data/kg/verification_report.json（git 未跟踪的运行产物）"""
        from src.verification.report_generator import ReportGenerator
        default_path = Path(ReportGenerator.save_report.__code__.co_filename).parent.parent.parent / "data" / "kg" / "verification_report.json"
        marker = f"默认路径测试-{id(generator)}"
        generator.save_report({"topic": marker})
        assert default_path.exists()
        loaded = json.loads(default_path.read_text(encoding="utf-8"))
        assert loaded["topic"] == marker
