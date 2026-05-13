package com.chatroom.model.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.Data;

@Data
public class ChatMessageDTO {
    @NotBlank(message = "消息内容不能为空")
    private String content;
    @NotNull(message = "消息类型不能为空")
    private Integer messageType;  // 0=private, 1=group
    @NotNull(message = "目标ID不能为空")
    private Long targetId;
    private Long replyToId;
    private Integer contentType = 0;
    private String clientMessageId;  // client-generated UUID for dedup
}
