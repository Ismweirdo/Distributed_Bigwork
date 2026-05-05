package com.chatroom.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.chatroom.model.entity.Friend;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface FriendMapper extends BaseMapper<Friend> {
}
