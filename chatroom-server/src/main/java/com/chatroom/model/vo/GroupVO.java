package com.chatroom.model.vo;

import lombok.Data;
import java.time.LocalDateTime;
import java.util.List;

@Data
public class GroupVO {
    private Long id;
    private String name;
    private String avatar;
    private Long ownerId;
    private String ownerName;
    private String announcement;
    private Integer maxMembers;
    private Integer memberCount;
    private List<MemberVO> members;
    private LocalDateTime createdAt;

    @Data
    public static class MemberVO {
        private Long userId;
        private String username;
        private String nickname;
        private String avatar;
        private Integer role;
        private String nicknameInGroup;
        private LocalDateTime joinedAt;
    }
}
