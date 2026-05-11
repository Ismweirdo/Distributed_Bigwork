# Skill Markdown 管理

本目录用于存放 Skill 的 Markdown 源文件，作为“真源”，系统导入后写入数据库表 `bot_skills`。

## 目录约定
- 一个 Skill 对应一个 `.md` 文件
- 文件名建议与 `skill_id` 一致，便于检索

## 基础结构
- YAML Front Matter: `skill_id`、`name`、`version`、`model`、`api_endpoint`
- 正文分区: `system_prompt`、`emotion_profile`、`language_style`、`few_shot_examples`

## 示例
- 参考 `skill-template.md`

