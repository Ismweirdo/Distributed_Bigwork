package com.chatroom.model.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.time.LocalDateTime;

@Data
@TableName("`groups`")
public class Group {
    @TableId(type = IdType.AUTO)
    private Long id;
    private String name;
    private String avatar;
    private Long ownerId;
    private String announcement;
    private Integer maxMembers;
    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;
}
