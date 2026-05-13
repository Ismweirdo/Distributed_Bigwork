package com.chatroom.service;

import com.chatroom.model.entity.BotSkill;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Slf4j
@Service
public class BotSkillDocService {

    private final ObjectMapper objectMapper = new ObjectMapper();

    public void exportSkillDoc(BotSkill skill) {
        if (skill == null || skill.getId() == null) {
            return;
        }
        try {
            Path docsDir = resolveDocsDir();
            Files.createDirectories(docsDir);

            String skillId = buildSkillId(skill.getId());
            Path filePath = docsDir.resolve(skillId + ".md");

            String content = buildMarkdown(skill, skillId);
            Files.writeString(filePath, content, StandardCharsets.UTF_8);
            log.info("Exported skill doc: {}", filePath);
        } catch (Exception e) {
            log.warn("Failed to export skill doc for botUserId={}", skill.getBotUserId(), e);
        }
    }

    public void deleteSkillDoc(BotSkill skill) {
        if (skill == null || skill.getId() == null) {
            return;
        }
        try {
            Path docsDir = resolveDocsDir();
            String skillId = buildSkillId(skill.getId());
            Path filePath = docsDir.resolve(skillId + ".md");
            Files.deleteIfExists(filePath);
            log.info("Deleted skill doc: {}", filePath);
        } catch (Exception e) {
            log.warn("Failed to delete skill doc for botUserId={}", skill.getBotUserId(), e);
        }
    }

    private String buildMarkdown(BotSkill skill, String skillId) {
        String name = safe(skill.getSkillName());
        String model = safe(skill.getModel());
        String endpoint = safe(skill.getApiEndpoint());
        String systemPrompt = safe(skill.getSystemPrompt());
        String emotionProfile = safe(skill.getEmotionProfileJson());
        String languageStyle = safe(skill.getLanguageStyleJson());
        String fewShot = safe(skill.getFewShotExamples());

        StringBuilder sb = new StringBuilder();
        sb.append("---\n");
        sb.append("skill_id: ").append(skillId).append("\n");
        sb.append("name: ").append(name).append("\n");
        sb.append("version: 1.0.0\n");
        if (!model.isEmpty()) {
            sb.append("model: ").append(model).append("\n");
        }
        if (!endpoint.isEmpty()) {
            sb.append("api_endpoint: ").append(endpoint).append("\n");
        }
        sb.append("---\n\n");

        sb.append("## system_prompt\n");
        sb.append(systemPrompt).append("\n\n");

        sb.append("## emotion_profile\n");
        sb.append(formatEmotionProfile(emotionProfile)).append("\n\n");

        sb.append("## language_style\n");
        sb.append(formatLanguageStyle(languageStyle)).append("\n\n");

        sb.append("## tone_signature\n");
        sb.append(formatToneSignature(languageStyle, emotionProfile)).append("\n\n");

        sb.append("## rhythm_profile\n");
        sb.append(formatRhythmProfile(languageStyle)).append("\n\n");

        sb.append("## discourse_tactics\n");
        sb.append(formatDiscourseTactics(emotionProfile)).append("\n\n");

        sb.append("## topic_preferences\n");
        sb.append(formatTopicPreferences()).append("\n\n");

        sb.append("## safety_boundaries\n");
        sb.append(formatSafetyBoundaries()).append("\n\n");

        sb.append("## repair_strategy\n");
        sb.append(formatRepairStrategy()).append("\n\n");

        sb.append("## example_guidelines\n");
        sb.append(formatExampleGuidelines()).append("\n\n");

        sb.append("## few_shot_examples\n");
        sb.append(formatFewShotExamples(fewShot)).append("\n");

        return sb.toString();
    }

    private String formatEmotionProfile(String json) {
        Map<String, Object> map = parseJsonMap(json);
        if (map == null || map.isEmpty()) {
            return json;
        }
        StringBuilder sb = new StringBuilder();
        Object baseTone = map.getOrDefault("base_tone", map.get("baseTone"));
        if (baseTone != null) {
            sb.append("base_tone: ").append(baseTone).append("\n");
        }
        Map<String, Object> dist = extractDistribution(map);
        for (String key : List.of("joy", "care", "sad", "surprise", "anger", "fear")) {
            if (dist.containsKey(key)) {
                sb.append(key).append(": ").append(dist.get(key)).append("\n");
            }
        }
        Object variance = map.get("emotion_variance");
        if (variance != null) {
            sb.append("emotion_variance: ").append(variance).append("\n");
        }
        return sb.toString().trim();
    }

    private String formatLanguageStyle(String json) {
        Map<String, Object> map = parseJsonMap(json);
        if (map == null || map.isEmpty()) {
            return json;
        }
        StringBuilder sb = new StringBuilder();
        appendIfPresent(sb, "avg_sentence_len", map);
        appendIfPresent(sb, "use_emoji", map);
        appendIfPresent(sb, "emoji_rate", map);
        appendIfPresent(sb, "use_tone_words", map);
        appendIfPresent(sb, "question_ratio", map);
        appendIfPresent(sb, "exclaim_ratio", map);
        appendIfPresent(sb, "slang_ratio", map);
        appendIfPresent(sb, "habit_openings", map);
        appendIfPresent(sb, "habit_endings", map);
        appendIfPresent(sb, "avoid_words", map);
        appendIfPresent(sb, "response_pacing", map);
        return sb.toString().trim();
    }

    private void appendIfPresent(StringBuilder sb, String key, Map<String, Object> map) {
        if (!map.containsKey(key)) {
            return;
        }
        Object value = map.get(key);
        if (value instanceof List) {
            String joined = ((List<?>) value).stream().map(String::valueOf).toList().toString();
            joined = joined.substring(1, joined.length() - 1);
            sb.append(key).append(": ").append(joined).append("\n");
        } else {
            sb.append(key).append(": ").append(value).append("\n");
        }
    }

    private String formatFewShotExamples(String json) {
        List<Map<String, Object>> list = parseJsonList(json);
        if (list == null || list.isEmpty()) {
            return json;
        }
        StringBuilder sb = new StringBuilder();
        for (Map<String, Object> ex : list) {
            Object user = ex.get("user");
            Object assistant = ex.get("assistant");
            if (user == null || assistant == null) {
                continue;
            }
            sb.append("- user: ").append(user).append("\n");
            sb.append("  assistant: ").append(assistant).append("\n");
        }
        return sb.toString().trim();
    }

    private Map<String, Object> parseJsonMap(String json) {
        try {
            return objectMapper.readValue(json, new TypeReference<>() {});
        } catch (Exception e) {
            return null;
        }
    }

    private List<Map<String, Object>> parseJsonList(String json) {
        try {
            return objectMapper.readValue(json, new TypeReference<>() {});
        } catch (Exception e) {
            return null;
        }
    }

    private Map<String, Object> extractDistribution(Map<String, Object> map) {
        Object distObj = map.get("distribution");
        if (distObj instanceof Map) {
            return (Map<String, Object>) distObj;
        }
        Map<String, Object> dist = new LinkedHashMap<>();
        for (String key : List.of("joy", "care", "sad", "surprise", "anger", "fear")) {
            if (map.containsKey(key)) {
                dist.put(key, map.get(key));
            }
        }
        return dist;
    }

    private Path resolveDocsDir() {
        Path base = Paths.get(System.getProperty("user.dir"));
        Path docs = base.resolve("docs").resolve("skills");
        if (!Files.exists(docs) && base.getFileName() != null
                && "chatroom-server".equalsIgnoreCase(base.getFileName().toString())) {
            Path parent = base.getParent();
            if (parent != null) {
                docs = parent.resolve("docs").resolve("skills");
            }
        }
        return docs;
    }

    private String buildSkillId(Long skillDbId) {
        return "skill_" + skillDbId;
    }

    private String safe(String value) {
        return value == null ? "" : value.trim();
    }

    private String formatToneSignature(String languageStyleJson, String emotionProfileJson) {
        Map<String, Object> style = parseJsonMap(languageStyleJson);
        Map<String, Object> nested = getNestedMap(style, "tone_signature");
        if (nested != null) {
            return mapToLines(nested, List.of("pause_words", "preferred_punctuation", "common_patterns", "fixed_phrases", "emoji_habits", "reaction_fillers"));
        }
        Map<String, Object> emotions = parseJsonMap(emotionProfileJson);
        String baseTone = "随和";
        if (emotions != null) {
            Object bt = emotions.getOrDefault("base_tone", emotions.get("baseTone"));
            if (bt != null) baseTone = String.valueOf(bt);
        }
        String pauseWords = baseTone.contains("直率") ? "嗯, 呃, 啊" : "嗯嗯, 呃, 嗯";
        String preferredPunctuation = baseTone.contains("直率") ? "，, 。, ！" : "，, 。, ~";
        String commonPatterns = baseTone.contains("直率") ? "先回应再吐槽, 先拒绝再解释" : "先共情再追问, 先肯定再提醒";
        String fixedPhrases = baseTone.contains("直率") ? "行吧, 别急, 随你" : "慢慢来, 没关系, 我懂";
        return String.join("\n",
                "pause_words: " + pauseWords,
                "preferred_punctuation: " + preferredPunctuation,
                "common_patterns: " + commonPatterns,
                "fixed_phrases: " + fixedPhrases);
    }

    private String formatRhythmProfile(String languageStyleJson) {
        Map<String, Object> style = parseJsonMap(languageStyleJson);
        Map<String, Object> nested = getNestedMap(style, "rhythm_profile");
        if (nested != null) {
            return mapToLines(nested, List.of("sentence_len_median", "sentence_len_range", "comma_density", "question_gap", "reply_latency_hint", "reply_len_range", "burstiness"));
        }
        String sentenceLenMedian = "14";
        String sentenceLenRange = "8-22";
        String commaDensity = "0.25";
        String questionGap = "1-3";
        String replyLatency = "2-5s";
        if (style != null) {
            Object avg = getAny(style, "avg_sentence_len", "avgSentenceLen");
            if (avg != null) sentenceLenMedian = String.valueOf(avg);
            Object qRatio = getAny(style, "question_ratio", "questionRatio");
            if (qRatio instanceof Number && ((Number) qRatio).doubleValue() > 0.3) {
                questionGap = "1-2";
            }
        }
        return String.join("\n",
                "sentence_len_median: " + sentenceLenMedian,
                "sentence_len_range: " + sentenceLenRange,
                "comma_density: " + commaDensity,
                "question_gap: " + questionGap,
                "reply_latency_hint: " + replyLatency);
    }

    private String formatDiscourseTactics(String emotionProfileJson) {
        Map<String, Object> emotions = parseJsonMap(emotionProfileJson);
        String flowOrder = "直接回应 -> 追问/吐槽";
        if (emotions != null) {
            Object bt = emotions.getOrDefault("base_tone", emotions.get("baseTone"));
            if (bt != null && String.valueOf(bt).contains("细腻")) {
                flowOrder = "共情 -> 复述 -> 追问 -> 小建议";
            }
        }
        return String.join("\n",
                "flow_order: " + flowOrder,
                "topic_shift_style: 先承接再轻推新话题",
                "clarification_style: 提一个问题并给出两个选择");
    }

    private String formatTopicPreferences() {
        return String.join("\n",
                "favor_topics: 生活日常, 轻量吐槽, 随机闲聊",
                "avoid_topics: 极端对立话题, 现实身份核验",
                "knowledge_boundary: 不做专业诊断, 不替代现实建议");
    }

    private String formatSafetyBoundaries() {
        return String.join("\n",
                "refusal_style: 先理解情绪, 再说明不能提供, 给出安全替代",
                "red_flags: 伤害, 违法, 隐私请求");
    }

    private String formatRepairStrategy() {
        return String.join("\n",
                "misunderstanding: 承认可能理解错 -> 复述对方 -> 再确认",
                "overlong_reply: 缩短并给出一句总结");
    }

    private String formatExampleGuidelines() {
        return String.join("\n",
                "coverage: 高压情绪, 无聊闲聊, 求建议",
                "density: 4-8 组",
                "style_lock: 保持同一语气词与标点习惯");
    }

    private Map<String, Object> getNestedMap(Map<String, Object> map, String key) {
        if (map == null) return null;
        Object nested = map.get(key);
        if (nested instanceof Map) {
            return (Map<String, Object>) nested;
        }
        return null;
    }

    private String mapToLines(Map<String, Object> map, List<String> order) {
        StringBuilder sb = new StringBuilder();
        for (String key : order) {
            if (!map.containsKey(key)) continue;
            Object value = map.get(key);
            if (value instanceof List) {
                String joined = ((List<?>) value).stream().map(String::valueOf).toList().toString();
                joined = joined.substring(1, joined.length() - 1);
                sb.append(key).append(": ").append(joined).append("\n");
            } else {
                sb.append(key).append(": ").append(value).append("\n");
            }
        }
        return sb.toString().trim();
    }

    private Object getAny(Map<String, Object> map, String primary, String secondary) {
        return map.containsKey(primary) ? map.get(primary) : map.get(secondary);
    }

    private String mergeListFallback(Map<String, Object> map, String key, String fallback) {
        Object value = map.get(key);
        if (value instanceof List) {
            String joined = ((List<?>) value).stream().map(String::valueOf).toList().toString();
            return joined.substring(1, joined.length() - 1);
        }
        if (value != null) {
            return String.valueOf(value);
        }
        return fallback;
    }
}
