package com.chatroom.controller;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.chatroom.common.Result;
import com.chatroom.mapper.UserMapper;
import com.chatroom.model.entity.User;
import com.chatroom.model.vo.UserVO;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.BeanUtils;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.stream.Collectors;

@Tag(name = "用户模块")
@RestController
@RequestMapping("/api/users")
@RequiredArgsConstructor
public class UserController {

    private final UserMapper userMapper;

    @Operation(summary = "搜索用户")
    @GetMapping("/search")
    public Result<List<UserVO>> searchUsers(@RequestParam String keyword) {
        LambdaQueryWrapper<User> wrapper = new LambdaQueryWrapper<>();
        wrapper.like(User::getUsername, keyword).or().like(User::getNickname, keyword);
        List<User> users = userMapper.selectList(wrapper);
        List<UserVO> vos = users.stream().map(UserController::toUserVO).collect(Collectors.toList());
        return Result.ok(vos);
    }

    @Operation(summary = "获取用户详情")
    @GetMapping("/{id}")
    public Result<UserVO> getUser(@PathVariable Long id) {
        User user = userMapper.selectById(id);
        if (user == null) {
            return Result.notFound("用户不存在");
        }
        return Result.ok(toUserVO(user));
    }

    static UserVO toUserVO(User user) {
        UserVO vo = new UserVO();
        BeanUtils.copyProperties(user, vo);
        return vo;
    }
}
