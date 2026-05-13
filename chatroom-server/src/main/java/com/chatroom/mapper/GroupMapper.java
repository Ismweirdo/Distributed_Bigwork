package com.chatroom.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.chatroom.model.entity.Group;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface GroupMapper extends BaseMapper<Group> {
}
