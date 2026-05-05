package com.chatroom.common;

public class Constants {

    // Message types
    public static final int MSG_TYPE_PRIVATE = 0;
    public static final int MSG_TYPE_GROUP = 1;

    // Content types
    public static final int CONTENT_TYPE_TEXT = 0;
    public static final int CONTENT_TYPE_IMAGE = 1;
    public static final int CONTENT_TYPE_FILE = 2;

    // Message status
    public static final int MSG_STATUS_SENT = 0;
    public static final int MSG_STATUS_DELIVERED = 1;
    public static final int MSG_STATUS_READ = 2;

    // Friend status
    public static final int FRIEND_STATUS_PENDING = 0;
    public static final int FRIEND_STATUS_ACCEPTED = 1;
    public static final int FRIEND_STATUS_REJECTED = 2;
    public static final int FRIEND_STATUS_BLOCKED = 3;

    // Group member roles
    public static final int GROUP_ROLE_MEMBER = 0;
    public static final int GROUP_ROLE_ADMIN = 1;
    public static final int GROUP_ROLE_OWNER = 2;

    // User status
    public static final int USER_STATUS_OFFLINE = 0;
    public static final int USER_STATUS_ONLINE = 1;
    public static final int USER_STATUS_BUSY = 2;

    // Message recall window (2 minutes in milliseconds)
    public static final long RECALL_WINDOW_MS = 2 * 60 * 1000;

    // Chat history retention (30 days)
    public static final int HISTORY_RETENTION_DAYS = 30;

    // Page defaults
    public static final int DEFAULT_PAGE_SIZE = 20;
    public static final int MAX_PAGE_SIZE = 100;
}
