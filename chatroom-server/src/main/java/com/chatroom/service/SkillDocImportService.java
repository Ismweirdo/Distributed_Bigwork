package com.chatroom.service;

import com.chatroom.mapper.BotSkillMapper;
import com.chatroom.model.entity.BotSkill;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

@Slf4j
@Service
@RequiredArgsConstructor
public class SkillDocImportService {

    private static final Pattern FRONT_MATTER_LINE = Pattern.compile("^([a-zA-Z0-9_]+)\\s*:\\s*(.*)$");
    private static final Pattern SKILL_ID_NUMBER = Pattern.compile("(\\d+)");

    private final BotSkillMapper botSkillMapper;
    private final ObjectMapper objectMapper = new ObjectMapper();

    public BotSkill importSkillDoc(MultipartFile file) throws Exception {
        String content = new String(file.getBytes(), StandardCharsets.UTF_8);
        Map<String, String> frontMatter = parseFrontMatter(content);
        String skillId = frontMatter.get("skill_id");
        if (skillId == null || skillId.isBlank()) {
            throw new IllegalArgumentException("缺少 skill_id");
        }
        Long dbId = extractSkillDbId(skillId);
        if (dbId == null) {
            throw new IllegalArgumentException("skill_id 无法解析为数字: " + skillId);
        }
        BotSkill skill = botSkillMapper.selectById(dbId);
        if (skill == null) {
            throw new IllegalArgumentException("未找到对应技能: " + skillId);
        }

        Map<String, String> sections = parseSections(content);
        String systemPrompt = sections.getOrDefault("system_prompt", "").trim();
        Map<String, Object> emotionProfile = parseKeyValueSection(sections.get("emotion_profile"));
        Map<String, Object> languageStyle = parseKeyValueSection(sections.get("language_style"));
        Map<String, Object> toneSignature = parseKeyValueSection(sections.get("tone_signature"));
        Map<String, Object> rhythmProfile = parseKeyValueSection(sections.get("rhythm_profile"));
        Map<String, Object> discourseTactics = parseKeyValueSection(sections.get("discourse_tactics"));
        Map<String, Object> topicPreferences = parseKeyValueSection(sections.get("topic_preferences"));
        Map<String, Object> safetyBoundaries = parseKeyValueSection(sections.get("safety_boundaries"));
        Map<String, Object> repairStrategy = parseKeyValueSection(sections.get("repair_strategy"));
        Map<String, Object> exampleGuidelines = parseKeyValueSection(sections.get("example_guidelines"));
        List<Map<String, String>> fewShot = parseFewShotExamples(sections.get("few_shot_examples"));

        if (!toneSignature.isEmpty()) languageStyle.put("tone_signature", toneSignature);
        if (!rhythmProfile.isEmpty()) languageStyle.put("rhythm_profile", rhythmProfile);
        if (!discourseTactics.isEmpty()) languageStyle.put("discourse_tactics", discourseTactics);
        if (!topicPreferences.isEmpty()) languageStyle.put("topic_preferences", topicPreferences);
        if (!safetyBoundaries.isEmpty()) languageStyle.put("safety_boundaries", safetyBoundaries);
        if (!repairStrategy.isEmpty()) languageStyle.put("repair_strategy", repairStrategy);
        if (!exampleGuidelines.isEmpty()) languageStyle.put("example_guidelines", exampleGuidelines);

        skill.setSkillName(frontMatter.getOrDefault("name", skill.getSkillName()));
        if (!systemPrompt.isEmpty()) {
            skill.setSystemPrompt(systemPrompt);
        }
        if (!emotionProfile.isEmpty()) {
            Map<String, Object> distribution = new LinkedHashMap<>();
            for (String key : List.of("joy", "care", "sad", "surprise", "anger", "fear")) {
                if (emotionProfile.containsKey(key)) {
                    distribution.put(key, emotionProfile.get(key));
                }
            }
            if (!distribution.isEmpty()) {
                emotionProfile.putIfAbsent("distribution", distribution);
            }
            skill.setEmotionProfileJson(objectMapper.writeValueAsString(emotionProfile));
        }
        if (!languageStyle.isEmpty()) {
            skill.setLanguageStyleJson(objectMapper.writeValueAsString(languageStyle));
        }
        if (!fewShot.isEmpty()) {
            skill.setFewShotExamples(objectMapper.writeValueAsString(fewShot));
        }
        String model = frontMatter.get("model");
        if (model != null && !model.isBlank()) {
            skill.setModel(model);
        }
        String apiEndpoint = frontMatter.get("api_endpoint");
        if (apiEndpoint != null && !apiEndpoint.isBlank()) {
            skill.setApiEndpoint(apiEndpoint);
        }
        botSkillMapper.updateById(skill);
        log.info("Imported skill doc: {} -> botUserId={}", skillId, skill.getBotUserId());
        return skill;
    }

    private Map<String, String> parseFrontMatter(String content) {
        Map<String, String> map = new LinkedHashMap<>();
        String[] lines = content.split("\r?\n");
        int first = -1;
        int second = -1;
        for (int i = 0; i < lines.length; i++) {
            if (lines[i].trim().equals("---")) {
                if (first < 0) {
                    first = i;
                } else {
                    second = i;
                    break;
                }
            }
        }
        if (first < 0 || second < 0) {
            return map;
        }
        for (int i = first + 1; i < second; i++) {
            Matcher m = FRONT_MATTER_LINE.matcher(lines[i].trim());
            if (m.matches()) {
                map.put(m.group(1), m.group(2));
            }
        }
        return map;
    }

    private Map<String, String> parseSections(String content) {
        Map<String, String> sections = new LinkedHashMap<>();
        String[] lines = content.split("\r?\n");
        String current = null;
        StringBuilder buf = new StringBuilder();
        for (String line : lines) {
            if (line.startsWith("## ")) {
                if (current != null) {
                    sections.put(current, buf.toString().trim());
                }
                current = line.substring(3).trim();
                buf = new StringBuilder();
                continue;
            }
            if (current != null) {
                buf.append(line).append("\n");
            }
        }
        if (current != null) {
            sections.put(current, buf.toString().trim());
        }
        return sections;
    }

    private Long extractSkillDbId(String skillId) {
        Matcher matcher = SKILL_ID_NUMBER.matcher(skillId);
        if (matcher.find()) {
            return Long.parseLong(matcher.group(1));
        }
        return null;
    }

    private Map<String, Object> parseKeyValueSection(String content) {
        Map<String, Object> map = new LinkedHashMap<>();
        if (content == null || content.isBlank()) {
            return map;
        }
        String[] lines = content.split("\r?\n");
        for (String raw : lines) {
            String line = raw.trim();
            if (line.isEmpty() || !line.contains(":")) {
                continue;
            }
            String[] parts = line.split(":", 2);
            String key = parts[0].trim();
            String value = parts[1].trim();
            if (value.isEmpty()) {
                continue;
            }
            if (value.contains(",")) {
                List<String> list = Arrays.stream(value.split(","))
                        .map(String::trim)
                        .filter(s -> !s.isEmpty())
                        .toList();
                map.put(key, list);
                continue;
            }
            Object parsed = parseNumberOrString(value);
            map.put(key, parsed);
        }
        return map;
    }

    private Object parseNumberOrString(String value) {
        if (value.matches("-?\\d+")) {
            try {
                return Integer.parseInt(value);
            } catch (NumberFormatException ignored) {
            }
        }
        if (value.matches("-?\\d+\\.\\d+")) {
            try {
                return Double.parseDouble(value);
            } catch (NumberFormatException ignored) {
            }
        }
        return value;
    }

    private List<Map<String, String>> parseFewShotExamples(String content) {
        List<Map<String, String>> list = new ArrayList<>();
        if (content == null || content.isBlank()) {
            return list;
        }
        String[] lines = content.split("\r?\n");
        Map<String, String> current = null;
        String currentField = null;
        for (String raw : lines) {
            String line = raw.trim();
            if (line.startsWith("- user:")) {
                if (current != null && current.containsKey("user") && current.containsKey("assistant")) {
                    list.add(current);
                }
                current = new LinkedHashMap<>();
                current.put("user", line.substring("- user:".length()).trim());
                currentField = "user";
                continue;
            }
            if (line.startsWith("assistant:")) {
                if (current == null) {
                    current = new LinkedHashMap<>();
                }
                current.put("assistant", line.substring("assistant:".length()).trim());
                currentField = "assistant";
                continue;
            }
            if (current != null && currentField != null && !line.isBlank()) {
                current.put(currentField, current.get(currentField) + "\n" + line);
            }
        }
        if (current != null && current.containsKey("user") && current.containsKey("assistant")) {
            list.add(current);
        }
        return list;
    }
}
