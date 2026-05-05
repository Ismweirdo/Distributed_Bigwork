package com.chatroom.model.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.Size;
import lombok.Data;
import java.util.List;

@Data
public class CreateGroupDTO {
    @NotBlank(message = "群名称不能为空")
    @Size(max = 100, message = "群名称最长100个字符")
    private String name;
    @NotEmpty(message = "至少邀请一个成员")
    private List<Long> memberIds;
}
