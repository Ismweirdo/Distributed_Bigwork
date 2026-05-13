package com.chatroom.service;

import com.chatroom.model.dto.ChatMessageDTO;
import com.chatroom.model.entity.Message;
import com.chatroom.model.vo.MessageVO;
import java.util.List;

public interface MessageService {
    MessageVO sendAndSaveMessage(Long senderId, ChatMessageDTO dto);
    List<MessageVO> getPrivateHistory(Long userId, Long friendId, int page, int size);
    List<MessageVO> getGroupHistory(Long groupId, int page, int size);
    void recallMessage(Long messageId, Long userId);
    MessageVO getMessageContext(Long messageId);
    Message getById(Long messageId);
}
