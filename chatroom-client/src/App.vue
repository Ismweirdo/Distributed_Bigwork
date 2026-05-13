<template>
  <router-view />
</template>

<script setup>
</script>

<style>
:root {
  --primary-color: #6366f1;
  --primary-light: #818cf8;
  --primary-dark: #4f46e5;
  --secondary-color: #8b5cf6;
  --accent-color: #ec4899;
  --success-color: #22c55e;
  --warning-color: #f59e0b;
  --error-color: #ef4444;
  --info-color: #3b82f6;
  
  --bg-primary: #ffffff;
  --bg-secondary: #f8fafc;
  --bg-tertiary: #f1f5f9;
  --bg-hover: #e2e8f0;
  
  --text-primary: #1e293b;
  --text-secondary: #64748b;
  --text-muted: #94a3b8;
  
  --border-color: #e2e8f0;
  --border-light: #f1f5f9;
  
  --shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.05);
  --shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
  --shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1);
  --shadow-xl: 0 20px 25px -5px rgb(0 0 0 / 0.1), 0 8px 10px -6px rgb(0 0 0 / 0.1);
  
  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-lg: 16px;
  --radius-full: 9999px;
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html, body, #app {
  height: 100%;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, 'Noto Sans', sans-serif, 'Apple Color Emoji', 'Segoe UI Emoji', 'Segoe UI Symbol', 'Noto Color Emoji';
  background-color: var(--bg-secondary);
  color: var(--text-primary);
  scroll-behavior: smooth;
}

::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

::-webkit-scrollbar-track {
  background: transparent;
}

::-webkit-scrollbar-thumb {
  background: var(--text-muted);
  border-radius: var(--radius-full);
}

::-webkit-scrollbar-thumb:hover {
  background: var(--text-secondary);
}

.el-button--primary {
  background: linear-gradient(135deg, var(--primary-color), var(--secondary-color));
  border: none;
  box-shadow: var(--shadow-md);
  transition: all 0.3s ease;
}

.el-button--primary:hover {
  background: linear-gradient(135deg, var(--primary-light), var(--secondary-color));
  transform: translateY(-1px);
  box-shadow: var(--shadow-lg);
}

.el-button--primary:active {
  transform: translateY(0);
}

.el-input__wrapper {
  border-radius: var(--radius-md);
  border-color: var(--border-color);
  transition: all 0.3s ease;
}

.el-input__wrapper:hover {
  border-color: var(--primary-light);
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
}

.el-input__wrapper.is-focus {
  border-color: var(--primary-color);
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.2);
}

.el-card {
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  border: none;
}

.el-dialog {
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-xl);
}

.el-dialog__header {
  background: var(--bg-secondary);
  border-bottom: 1px solid var(--border-light);
  border-radius: var(--radius-lg) var(--radius-lg) 0 0;
}

.el-dialog__body {
  padding: 24px;
}

.el-tabs__nav-wrap::after {
  display: none;
}

.el-tabs__item {
  color: var(--text-secondary);
  transition: all 0.3s ease;
}

.el-tabs__item:hover {
  color: var(--primary-color);
}

.el-tabs__item.is-active {
  color: var(--primary-color);
  font-weight: 600;
}

.el-tabs__active-bar {
  background: linear-gradient(90deg, var(--primary-color), var(--secondary-color));
  height: 3px;
  border-radius: var(--radius-full);
}

.el-avatar {
  font-weight: 600;
  background: linear-gradient(135deg, var(--primary-color), var(--secondary-color));
}

.el-badge__content {
  background: var(--error-color);
  border: 2px solid #fff;
}

.el-dropdown-menu__item {
  transition: all 0.2s ease;
}

.el-dropdown-menu__item:hover {
  background: var(--bg-hover);
  color: var(--primary-color);
}
</style>
