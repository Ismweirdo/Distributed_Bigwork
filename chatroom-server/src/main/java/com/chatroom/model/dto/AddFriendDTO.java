package com.chatroom.model.dto;

import jakarta.validation.constraints.NotNull;
import lombok.Data;

@Data
public class AddFriendDTO {
    @NotNull(message = "好友ID不能为空")
    private Long friendId;
    private String message;
}
