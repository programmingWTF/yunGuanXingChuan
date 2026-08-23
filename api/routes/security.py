"""路由共享安全工具

背景：/result/{task_id}、/export/{task_id} 等端点曾把 URL 中的 task_id
直接拼进磁盘路径（RESULTS_DIR / f"{task_id}.json"）或 glob 模式
（f"*{task_id[:8]}*"）。task_id 含 ../ 或 glob 元字符（* ? [ ]）时
可穿越读取 RESULTS_DIR 之外的 JSON 文件。

本项目合法 task_id 形如：
  task_20260101120000_a1b2c3 / parl_... / out_research_plan_... / proj_...
统一限制为 [A-Za-z0-9_-]，从根上消除穿越与模式注入。
"""
import re

# 合法 task_id 字符集：字母数字、下划线、连字符
_TASK_ID_RE = re.compile(r"^[A-Za-z0-9_\-]{1,128}$")


def is_safe_task_id(task_id: str) -> bool:
    """校验 task_id 是否只含安全字符（不含路径分隔符、点、glob 元字符）"""
    return bool(task_id) and bool(_TASK_ID_RE.match(task_id))
