package com.chatroom.websocket;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.chatroom.common.Constants;
import com.chatroom.mapper.FriendMapper;
import com.chatroom.mapper.MessageMapper;
import com.chatroom.mapper.UserMapper;
import com.chatroom.model.dto.ChatMessageDTO;
import com.chatroom.model.entity.Friend;
import com.chatroom.model.entity.Message;
import com.chatroom.model.entity.User;
import com.chatroom.model.vo.MessageVO;
import com.chatroom.service.MessageService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.event.EventListener;
import org.springframework.messaging.handler.annotation.MessageMapping;
import org.springframework.messaging.handler.annotation.Payload;
import org.springframework.messaging.simp.SimpMessagingTemplate;
import org.springframework.messaging.simp.stomp.StompHeaderAccessor;
import org.springframework.stereotype.Controller;
import org.springframework.web.socket.messaging.SessionConnectEvent;
import org.springframework.web.socket.messaging.SessionDisconnectEvent;

import java.security.Principal;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

@Slf4j
@Controller
@RequiredArgsConstructor
public class ChatWebSocketHandler {

    private final SimpMessagingTemplate messagingTemplate;
    private final MessageService messageService;
    private final MessageMapper messageMapper;
    private final UserMapper userMapper;
    private final FriendMapper friendMapper;
    private final OnlineStatusManager onlineStatusManager;

    // sessionId -> userId
    private final ConcurrentHashMap<String, Long> sessionUserMap = new ConcurrentHashMap<>();

    @EventListener
    public void handleConnectEvent(SessionConnectEvent event) {
        StompHeaderAccessor accessor = StompHeaderAccessor.wrap(event.getMessage());
        Principal principal = accessor.getUser();
        if (principal != null) {
            Long userId = Long.valueOf(principal.getName());
            String sessionId = accessor.getSessionId();
            sessionUserMap.put(sessionId, userId);
            onlineStatusManager.userOnline(userId, sessionId);

            // Update user status in DB
            User user = userMapper.selectById(userId);
            if (user != null) {
                user.setStatus(Constants.USER_STATUS_ONLINE);
                userMapper.updateById(user);
            }

            // Broadcast online status to friends
            broadcastPresence(userId, true);

            log.info("User {} connected, session: {}", userId, sessionId);
        }
    }

    @EventListener
    public void handleDisconnectEvent(SessionDisconnectEvent event) {
        StompHeaderAccessor accessor = StompHeaderAccessor.wrap(event.getMessage());
        String sessionId = accessor.getSessionId();
        Long userId = sessionUserMap.remove(sessionId);
        if (userId != null) {
            onlineStatusManager.userOffline(userId);

            // Update user status in DB
            User user = userMapper.selectById(userId);
            if (user != null) {
                user.setStatus(Constants.USER_STATUS_OFFLINE);
                userMapper.updateById(user);
            }

            // Broadcast offline status to friends
            broadcastPresence(userId, false);

            log.info("User {} disconnected, session: {}", userId, sessionId);
        }
    }

    private void broadcastPresence(Long userId, boolean online) {
        // Find all friends of this user
        LambdaQueryWrapper<Friend> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(Friend::getStatus, Constants.FRIEND_STATUS_ACCEPTED)
                .and(w -> w.eq(Friend::getUserId, userId).or().eq(Friend::getFriendId, userId));
        List<Friend> friends = friendMapper.selectList(wrapper);

        Map<String, Object> presence = new HashMap<>();
        presence.put("type", "PRESENCE");
        presence.put("userId", userId);
        presence.put("status", online ? "ONLINE" : "OFFLINE");

        for (Friend f : friends) {
            Long friendId = f.getUserId().equals(userId) ? f.getFriendId() : f.getUserId();
            messagingTemplate.convertAndSendToUser(
                    String.valueOf(friendId), "/queue/private/presence", presence);
        }
    }

    @MessageMapping("/chat.send")
    public void handleChatMessage(@Payload ChatMessageDTO dto, Principal principal) {
        Long senderId = Long.valueOf(principal.getName());
        log.info("Chat message from {} to {} (type={})", senderId, dto.getTargetId(), dto.getMessageType());

        MessageVO messageVO = messageService.sendAndSaveMessage(senderId, dto);
        Map<String, Object> payload = buildWsPayload(messageVO);

        if (dto.getMessageType() == Constants.MSG_TYPE_PRIVATE) {
            messagingTemplate.convertAndSendToUser(
                    String.valueOf(senderId), "/queue/private/chat", payload);
            messagingTemplate.convertAndSendToUser(
                    String.valueOf(dto.getTargetId()), "/queue/private/chat", payload);
        } else if (dto.getMessageType() == Constants.MSG_TYPE_GROUP) {
            messagingTemplate.convertAndSend(
                    "/topic/group/" + dto.getTargetId(), payload);
        }
    }

    @MessageMapping("/chat.ack")
    public void handleAck(@Payload Map<String, Object> ack, Principal principal) {
        Long messageId = Long.valueOf(ack.get("messageId").toString());
        Message msg = messageMapper.selectById(messageId);
        if (msg != null && msg.getStatus() != Constants.MSG_STATUS_READ) {
            msg.setStatus(Constants.MSG_STATUS_READ);
            messageMapper.updateById(msg);
        }
    }

    private Map<String, Object> buildWsPayload(MessageVO vo) {
        Map<String, Object> map = new HashMap<>();
        map.put("type", "CHAT");
        map.put("messageId", vo.getId());
        map.put("messageType", vo.getMessageType());
        map.put("senderId", vo.getSenderId());
        map.put("senderName", vo.getSenderName());
        map.put("senderAvatar", vo.getSenderAvatar());
        map.put("targetId", vo.getTargetId());
        map.put("replyToId", vo.getReplyToId());
        map.put("replyToContent", vo.getReplyToContent());
        map.put("replyToSenderName", vo.getReplyToSenderName());
        map.put("content", vo.getContent());
        map.put("contentType", vo.getContentType());
        map.put("status", vo.getStatus());
        map.put("createdAt", vo.getCreatedAt() != null ? vo.getCreatedAt().toString() : null);
        return map;
    }
}
