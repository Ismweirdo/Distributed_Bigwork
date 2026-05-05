package com.chatroom.config;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.chatroom.common.Constants;
import com.chatroom.mapper.MessageMapper;
import com.chatroom.model.entity.Message;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.time.LocalDateTime;

@Slf4j
@Component
@RequiredArgsConstructor
public class CleanupScheduler {

    private final MessageMapper messageMapper;

    // Run daily at 3:00 AM
    @Scheduled(cron = "0 0 3 * * ?")
    public void cleanExpiredMessages() {
        LocalDateTime cutoff = LocalDateTime.now().minusDays(Constants.HISTORY_RETENTION_DAYS);
        LambdaQueryWrapper<Message> wrapper = new LambdaQueryWrapper<>();
        wrapper.lt(Message::getCreatedAt, cutoff);
        long deleted = messageMapper.delete(wrapper);
        log.info("Cleaned {} messages older than {} days", deleted, Constants.HISTORY_RETENTION_DAYS);
    }
}
