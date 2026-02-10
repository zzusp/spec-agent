---
name: spec-agent
description: Generate analysis/PRD/tech/acceptance/clarifications docs from user requirements and keep them in sync.
metadata:
  short-description: Spec documentation workflow with clarifications and checks
---

# spec-agent

Use this skill to help users generate and maintain a full documentation set for product requirements:
- 分析报告
- PRD
- 技术方案
- 验收清单
- 澄清文档

The docs are stored under `spec/YYYY-MM-DD/<requirement_name_en>/` and are Markdown files.

## When to use
Trigger this skill when the user asks to:
- 初始化需求文档
- 基于澄清内容更新文档
- 执行最终检查
- 指定/切换某个需求
- 复制内置开发规则到 `.cursor/rules/`

## Primary workflow
1. **初始化**
   - Collect: 需求英文名、中文标题（可选）、原始需求描述。
   - Run:
     - `python scripts/spec_agent.py init --name <name> --title "<title>" --desc "<raw_requirement>"`
   - This creates all docs and sets the active requirement.

2. **补充与更新**
   - User fills `00-clarifications.md` table (状态改为 `已确认` 并补充内容)。
   - Run:
     - `python scripts/spec_agent.py update` (or with `--name`/`--path`)
     - `python scripts/spec_agent.py update --strict` (阻止澄清未闭环时更新)
   - This syncs clarified items into the other documents and runs a final check.

3. **最终检查**
   - Run:
     - `python scripts/spec_agent.py final-check`
   - Any issues found will be appended to the clarification table.

4. **切换需求**
   - Run:
     - `python scripts/spec_agent.py set-active --name <name>`
   - Or use `--path` to pick a specific directory.

5. **复制规则**
   - Run:
     - `python scripts/spec_agent.py copy-rules`
   - This copies `.mdc` rules from `rules/` to `.cursor/rules/`.

6. **扫描候选模块**
   - Run:
     - `python scripts/spec_agent.py scan`
   - This scans the repo and writes a candidate module list into the analysis doc.

## Clarification table
The clarification table now includes:
- `优先级`
- `影响范围`
- `关联章节`

This helps review and update specific sections more precisely.

## Config (optional)
You can create `spec-agent.config.json` at repo root to override defaults:
- `spec_dir` (default: `spec`)
- `date_format` (default: `%Y-%m-%d`)
- `placeholders`
- `prd_tech_words`
- `clarify_columns`
- `rules_copy_allowlist`

## Authoring guidance
While drafting documents, follow the user requirements strictly:
- **分析报告**: 对照原始需求、代码与数据库现状，给出满足性分析与风险，包含需求覆盖矩阵。
- **PRD**: 不允许出现实现/技术细节；必须含需求范围、背景、完整流程、分支与异常、非功能性需求、待确认点、冲突与影响。
- **技术方案**: 给出架构思路与图、数据库设计（含可执行 SQL）、核心代码片段、单测、数据迁移与回滚策略、注意事项。
- **验收清单**: 覆盖所有流程与分支、受影响功能验证、数据库核对方式。
- **澄清文档**: 记录所有待确认点与解决方案；用户确认后标记为 `已确认`。

## Required behavior
- Always write Markdown files under `spec/YYYY-MM-DD/<name>/`.
- For multi-requirement work, ensure the correct requirement is active before updating.
- If any content is missing, use the clarification table instead of guessing.
- Avoid adding implementation details to PRD.

## Notes
- Use `rg` to inspect codebase when the user expects analysis against existing modules.
- If the user provides DB connection info in the clarifications, use it to verify tables.
