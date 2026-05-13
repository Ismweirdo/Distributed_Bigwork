package com.chatroom.model.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.time.LocalDateTime;

@Data
@TableName("group_members")
public class GroupMember {
    @TableId(type = IdType.AUTO)
    private Long id;
    private Long groupId;
    private Long userId;
    private Integer role;
    private String nicknameInGroup;
    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime joinedAt;
}
