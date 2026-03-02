#!/usr/bin/env python
from __future__ import annotations

import hashlib
import json
import re
import sys


def _slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", str(text or "").strip().lower())
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s[:64].strip("-")


def _project_mode(text: str) -> str:
    t = str(text or "").lower()
    greenfield_hits = 0
    existing_hits = 0
    for kw in ["从零", "从 0", "0到1", "零到一", "全新项目", "新建项目", "greenfield", "from scratch"]:
        if kw in t:
            greenfield_hits += 1
    for kw in ["已有项目", "现有项目", "存量项目", "新增需求", "增量需求", "迭代", "existing", "brownfield"]:
        if kw in t:
            existing_hits += 1
    if greenfield_hits > existing_hits:
        return "greenfield"
    return "existing"


def _requirement_name(title: str, requirement_text: str) -> str:
    if _slugify(title):
        return _slugify(title)
    lines = [ln.strip() for ln in str(requirement_text or "").splitlines() if ln.strip()]
    if lines and _slugify(lines[0]):
        return _slugify(lines[0])
    digest = hashlib.md5(str(requirement_text or "requirement").encode("utf-8")).hexdigest()[:8]
    return f"req-{digest}"


def _clarification_targets(raw_doc: str) -> list[str]:
    text = str(raw_doc or "").strip().lower()
    out = set()
    if "global" in text or "全局" in text:
        out.add("global")
    if "analysis" in text or "分析" in text:
        out.add("analysis")
    if "prd" in text:
        out.add("prd")
    if "tech" in text or "技术" in text:
        out.add("tech")
    if "acceptance" in text or "验收" in text:
        out.add("acceptance")
    if not out:
        out.add("global")
    return sorted(out)


def _acceptance_testability(content: str) -> dict:
    block = str(content or "")
    step_action_keywords = ["触发", "执行", "调用", "提交", "输入", "点击", "查询", "请求", "发送", "读取", "检查", "核对", "观察", "记录", "验证"]
    step_observable_keywords = ["响应", "返回", "状态", "字段", "日志", "数据库", "表", "记录", "消息", "事件", "文件", "页面", "结果", "状态码", "code"]
    pass_assert_keywords = ["等于", "应为", "包含", "不包含", "存在", "不存在", "一致", "匹配", "状态码", "code", "返回", "字段", "日志", "数据库", "数量", "条"]
    pass_vague_keywords = ["正常", "良好", "友好", "稳定", "无异常", "符合预期"]

    steps_executable = any(k in block for k in step_action_keywords) and any(k in block for k in step_observable_keywords)
    pass_assertable = any(k in block for k in pass_assert_keywords) or bool(re.search(r"[=<>]|\d", block))
    pass_too_vague = bool(pass_assertable) and all(k in block for k in ["功能正常", "体验良好"])
    if any(k in block for k in pass_vague_keywords) and not any(k in block for k in pass_assert_keywords):
        pass_assertable = False
        pass_too_vague = True
    return {
        "steps_executable": bool(steps_executable),
        "pass_assertable": bool(pass_assertable),
        "pass_too_vague": bool(pass_too_vague),
        "reason": "",
    }


def _issue_stage(issue: dict) -> str:
    code = str(issue.get("code", "")).strip().lower()
    if code.startswith("analysis.") or code.startswith("global."):
        return "analysis"
    if code.startswith("prd."):
        return "prd"
    if code.startswith("tech."):
        return "tech"
    if code.startswith("acceptance."):
        return "acceptance"
    doc = str(issue.get("doc", "")).strip().lower()
    if doc in {"analysis", "prd", "tech", "acceptance"}:
        return doc
    q = str(issue.get("question", "")).strip()
    if any(k in q for k in ("验收", "A-")):
        return "acceptance"
    if any(k in q for k in ("技术方案", "SQL", "数据库设计", "回滚")):
        return "tech"
    if any(k in q for k in ("PRD", "产品功能", "非功能性需求")):
        return "prd"
    return "analysis"


def main():
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw or "{}")
    except Exception:
        print(json.dumps({"error": "invalid input json"}, ensure_ascii=False))
        sys.exit(2)

    task = str(payload.get("task", "")).strip()
    input_obj = payload.get("input", {}) if isinstance(payload.get("input", {}), dict) else {}

    if task == "project_mode":
        text = str(input_obj.get("requirement_text", ""))
        print(json.dumps({"project_mode": _project_mode(text)}, ensure_ascii=False))
        return
    if task == "requirement_name":
        title = str(input_obj.get("title", ""))
        req = str(input_obj.get("requirement_text", ""))
        print(json.dumps({"requirement_name": _requirement_name(title, req)}, ensure_ascii=False))
        return
    if task == "clarification_targets":
        raw_doc = str(input_obj.get("raw_doc", ""))
        print(json.dumps({"targets": _clarification_targets(raw_doc)}, ensure_ascii=False))
        return
    if task == "acceptance_testability":
        content = str(input_obj.get("content", ""))
        print(json.dumps(_acceptance_testability(content), ensure_ascii=False))
        return
    if task == "final_check_issue_stage":
        issue = input_obj.get("issue", {}) if isinstance(input_obj.get("issue", {}), dict) else {}
        print(json.dumps({"stage": _issue_stage(issue)}, ensure_ascii=False))
        return

    print(json.dumps({"error": f"unsupported task: {task}"}, ensure_ascii=False))
    sys.exit(3)


if __name__ == "__main__":
    main()
