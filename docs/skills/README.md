# Skill Markdown 管理

本目录用于存放 Skill  Markdown 源文件，作为“真源”，系统导入后写入数据库表 `bot_skills`。

## 目录约定
- 一个 Skill 对应一个 `.md` 文件
- 文件名建议与 `skill_id` 一致，便于检索

## 基础结构
- YAML Front Matter: `skill_id`、`name`、`version`、`model`、`api_endpoint`
- 正文分区: `system_prompt`、`emotion_profile`、`language_style`、`few_shot_examples`

## 高级字段（可选，解析器未识别时也应忽略）
- `tone_signature`: 口癖、固定句式、常见停顿词、标点偏好、表情使用、反应填充词
- `rhythm_profile`: 句长分布、断句方式、回复节奏、追问密度、爆发感
- `discourse_tactics`: 共情-复述-建议的顺序、承接 vs 转移话题、追问习惯
- `topic_preferences`: 话题偏好/回避、知识边界、价值倾向、幽默类型
- `safety_boundaries`: 触发拒绝的场景与更自然的拒绝话术、隐私底线
- `repair_strategy`: 误解时的自我修正方式、追问策略、语气回拉
- `example_guidelines`: few-shot 采样原则（高频场景覆盖）、采样优先级

## 设计目标
- 人设清晰、可被一句话概括，但又有可持续展开的细节
- 语言更“人”：有节奏、有习惯、有主观偏好、有边界
- 以聊天记录蒸馏数据为基准，避免人为美化或过度礼貌化
- 能在不同话题里保持一致的性格，不“风格漂移”

## 人设框架（建议写进 system_prompt）
- 身份与背景: 年龄段、职业/兴趣、生活场景、价值观
- 目标与动机: 想从聊天中获得什么，擅长什么话题
- 性格与习惯: 口癖、情绪起伏、表达偏好、幽默类型
- 边界与禁区: 不聊什么、拒绝的方式、隐私与安全表述
- 对话策略: 先共情还是先建议、是否喜欢追问、是否会复述
- 关系定位: 朋友/前辈/同龄人/“吐槽搭子”等

## 从聊天记录提取（接近口吻一致）
- 统计高频起句/收句/转折词，写入 `tone_signature`
- 统计句长中位数与波动区间，写入 `rhythm_profile`
- 记录常用“回应套路”，写入 `discourse_tactics`
- 优先抽取高频场景对话作为 few-shot 示例

## 写作清单（完成度检查）
- 能用 1 句话描述人设，并与示例对话一致
- 至少 2 个“可被识别”的口头习惯（开头/结尾/口癖）
- 至少 2 个稳定偏好（话题、价值观、幽默方式、表达长度）
- 至少 1 个明确边界（拒绝方式要自然，不生硬）
- few-shot 中体现“真实口吻”，必要时可以更直接或带情绪

## 差异度评估（导入前快速检查）
- 与已有 Skill 相比，是否存在“同义人设”或同质化语气
- 在三类问题上回复是否稳定: 求安慰 / 求建议 / 闲聊
- 读一段对话，能否 3 句内猜出是谁在说话

## 示例
- 参考 `skill-template.md`

## 从 Markdown 导入
- 接口: `POST /api/bots/skills/import`
- 说明: 上传 `docs/skills/*.md` 后解析并更新对应 `bot_skills` 记录
- 识别方式: 读取 `skill_id`（如 `skill_42`）并更新同 ID 的技能
