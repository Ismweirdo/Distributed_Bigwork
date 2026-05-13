package com.chatroom.service;

import com.chatroom.model.dto.LoginDTO;
import com.chatroom.model.dto.RegisterDTO;
import com.chatroom.model.vo.LoginVO;
import com.chatroom.model.vo.UserVO;

public interface AuthService {
    LoginVO register(RegisterDTO dto);
    LoginVO login(LoginDTO dto);
    UserVO getCurrentUser(Long userId);
}
