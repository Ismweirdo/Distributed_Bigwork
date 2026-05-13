package com.chatroom.model.vo;

import lombok.Data;
import java.time.LocalDateTime;

@Data
public class MessageVO {
    private Long id;
    private Integer messageType;
    private Long senderId;
    private String senderName;
    private String senderAvatar;
    private Long targetId;
    private Long replyToId;
    private String replyToContent;
    private String replyToSenderName;
    private String content;
    private Integer contentType;
    private Integer status;
    private LocalDateTime createdAt;
}
