package com.chatroom.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.*;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

import java.util.*;

@Slf4j
@Service
public class QQChatExporterClient {

    private final RestTemplate restTemplate = new RestTemplate();
    private final ObjectMapper objectMapper = new ObjectMapper();

    @Value("${bot.qqce-url:http://localhost:40653}")
    private String qqceBaseUrl;

    private HttpHeaders buildHeaders(String token) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        if (token != null && !token.isEmpty()) {
            headers.set("Authorization", "Bearer " + token);
            log.debug("QQCE request with Authorization header (token len={})", token.length());
        } else {
            log.debug("QQCE request WITHOUT Authorization header (token is null or empty)");
        }
        return headers;
    }

    /** Check if QQCE is running and accessible */
    public Map<String, Object> healthCheck(String token) {
        try {
            HttpEntity<Void> request = new HttpEntity<>(buildHeaders(token));
            ResponseEntity<Map> resp = restTemplate.exchange(qqceBaseUrl + "/health", HttpMethod.GET, request, Map.class);
            Map<String, Object> result = new LinkedHashMap<>();
            result.put("connected", resp.getStatusCode().is2xxSuccessful());
            result.put("url", qqceBaseUrl);
            return result;
        } catch (Exception e) {
            Map<String, Object> result = new LinkedHashMap<>();
            result.put("connected", false);
            result.put("url", qqceBaseUrl);
            result.put("error", "无法连接到QQ Chat Exporter，请确保已启动并扫码登录: " + e.getMessage());
            return result;
        }
    }

    /** Get friend list from QQ */
    public List<Map<String, Object>> getFriends(String token) {
        try {
            HttpEntity<Void> request = new HttpEntity<>(buildHeaders(token));
            ResponseEntity<Map> resp = restTemplate.exchange(qqceBaseUrl + "/api/friends", HttpMethod.GET, request, Map.class);
            Map<String, Object> data = (Map<String, Object>) resp.getBody().get("data");
            if (data == null) data = resp.getBody();
            List<Map<String, Object>> friends = (List<Map<String, Object>>) data.get("friends");
            if (friends == null) friends = List.of();
            return friends;
        } catch (Exception e) {
            log.error("Failed to get QQ friends: {}", e.getMessage());
            throw new RuntimeException("获取QQ好友列表失败: " + e.getMessage());
        }
    }

    /** Get group list from QQ */
    public List<Map<String, Object>> getGroups(String token) {
        try {
            HttpEntity<Void> request = new HttpEntity<>(buildHeaders(token));
            ResponseEntity<Map> resp = restTemplate.exchange(qqceBaseUrl + "/api/groups", HttpMethod.GET, request, Map.class);
            Map<String, Object> data = (Map<String, Object>) resp.getBody().get("data");
            if (data == null) data = resp.getBody();
            List<Map<String, Object>> groups = (List<Map<String, Object>>) data.get("groups");
            if (groups == null) groups = List.of();
            return groups;
        } catch (Exception e) {
            log.error("Failed to get QQ groups: {}", e.getMessage());
            throw new RuntimeException("获取QQ群列表失败: " + e.getMessage());
        }
    }

    /** Fetch messages for a specific chat (friend or group) */
    public List<Map<String, Object>> fetchMessages(String chatType, String peerUid, int count, String token) {
        try {
            Map<String, Object> body = Map.of(
                "peer", Map.of("chatType", chatType.equals("group") ? 2 : 1, "peerUid", peerUid),
                "batchSize", count,
                "page", 1,
                "limit", Math.min(count, 5000)
            );

            HttpEntity<Map<String, Object>> request = new HttpEntity<>(body, buildHeaders(token));

            ResponseEntity<Map> resp = restTemplate.postForEntity(
                    qqceBaseUrl + "/api/messages/fetch", request, Map.class);

            log.debug("QQCE fetchMessages response status: {}", resp.getStatusCode());
            log.debug("QQCE fetchMessages response body keys: {}", resp.getBody() != null ? resp.getBody().keySet() : "null");
            log.debug("QQCE fetchMessages full response: {}", resp.getBody());

            Map<String, Object> data = (Map<String, Object>) resp.getBody().get("data");
            if (data == null) data = resp.getBody();

            log.debug("QQCE data keys: {}", data != null ? data.keySet() : "null");

            Object messagesObj = data.get("messages");
            if (messagesObj instanceof List) {
                log.info("QQCE fetched {} messages for {}", ((List) messagesObj).size(), peerUid);
                return (List<Map<String, Object>>) messagesObj;
            }
            log.warn("QQCE response has no 'messages' list. messagesObj type: {}, value: {}",
                    messagesObj != null ? messagesObj.getClass().getName() : "null",
                    messagesObj);
            return List.of();
        } catch (Exception e) {
            log.error("Failed to fetch messages for {}: {}", peerUid, e.getMessage());
            throw new RuntimeException("获取聊天记录失败: " + e.getMessage());
        }
    }
}
