# 项目设计规范 — Auto Content Platform

## 设计方向

### 界面类型

**产品型界面**（后台管理控制台/工具），设计服务于效率和信任。

### 设计风格

深色工业风（Dark Industrial），追求暖色调工具感。

## 颜色 Token

```css
:root {
  /* 背景层级 */
  --bg-primary:   #0f1117;   /* 主背景 */
  --bg-secondary: #161822;   /* 面板/卡片背景 */
  --bg-tertiary:  #1e2030;   /* 悬停/激活态 */
  --bg-elevated:  #252840;   /* 弹窗/浮层 */

  /* 文字 */
  --text-primary:   #e4e6ed; /* 主文字 */
  --text-secondary: #8b8fa3; /* 辅助文字 */
  --text-disabled:  #55596e; /* 禁用文字 */

  /* 强调色 */
  --accent-primary: #e8c547; /* 暖金（按钮/链接/高亮） */
  --accent-hover:   #f0d868; /* 悬停加亮 */
  --accent-active:  #c9a830; /* 按下加深 */

  /* 状态色 */
  --color-success: #4caf50;
  --color-warning: #ff9800;
  --color-error:   #f44336;
  --color-info:    #2196f3;

  /* 边框 */
  --border-color:  #2a2d3a;
  --border-hover:  #3a3d4a;
}
```

## 字体 Token

```css
--font-mono:   'JetBrains Mono', 'Cascadia Code', Consolas, monospace;
--font-body:   -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
--font-heading: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
```

## 间距

- 基准：4px 网格
- 内边距：16px / 24px / 32px
- 卡片圆角：6px
- 按钮圆角：4px

## 组件规范

### 侧边栏
- 深色背景 #161822
- 折叠支持（响应式）
- 菜单排序：文档分析首位，系统设置末位
- 图标 + 文字标签

### 卡片
- 背景 #1e2030
- 边框 #2a2d3a
- 悬停：边框变亮 #3a3d4a

### 按钮
- 主按钮：`#e8c547` 背景，`#0f1117` 文字
- 次按钮：透明背景，`#e8c547` 边框
- 危险按钮：`#f44336` 背景

### 数据表格
- Element Plus 深色主题覆盖
- 行悬停 #1e2030
- 列头背景 #161822

### 表单控件
- Input：背景 #161822，边框 #2a2d3a
- Select：同上
- 聚焦：边框 #e8c547

## 反参考

以下风格明确禁用于本项目：

- 紫蓝渐变
- 玻璃拟态
- 白色/浅色主题
- 三列卡片布局
- 泛 AI 科技感装饰元素
- 米色/沙色/咖啡色调

## 响应式

- 侧边栏：移动端折叠为汉堡菜单
- 表格：小屏横向滚动
- 卡片：单列 → 双列 → 三列自适应

## 动效

- 侧边栏展开/折叠：200ms ease
- 页面切换：不设动效
- 按钮 hover：150ms 颜色过渡
