package com.chatroom.controller;

import com.chatroom.common.Result;
import com.chatroom.model.dto.LoginDTO;
import com.chatroom.model.dto.RegisterDTO;
import com.chatroom.model.vo.LoginVO;
import com.chatroom.model.vo.UserVO;
import com.chatroom.service.AuthService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import com.chatroom.security.SecurityUtil;
import org.springframework.web.bind.annotation.*;

@Tag(name = "认证模块")
@RestController
@RequestMapping("/api/auth")
@RequiredArgsConstructor
public class AuthController {

    private final AuthService authService;

    @Operation(summary = "用户注册")
    @PostMapping("/register")
    public Result<LoginVO> register(@Valid @RequestBody RegisterDTO dto) {
        return Result.ok(authService.register(dto));
    }

    @Operation(summary = "用户登录")
    @PostMapping("/login")
    public Result<LoginVO> login(@Valid @RequestBody LoginDTO dto) {
        return Result.ok(authService.login(dto));
    }

    @Operation(summary = "获取当前用户信息")
    @GetMapping("/me")
    public Result<UserVO> me() {
        return Result.ok(authService.getCurrentUser(SecurityUtil.getCurrentUserId()));
    }
}
