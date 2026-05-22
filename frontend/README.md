# Afterglow（续温）前端

> 把曾经对你好的话，续成往后的陪伴。

基于 Vue 3 + Vite + TypeScript + TailwindCSS 的"时光信笺"风格聊天界面。

前端主要用于本地测试、调试和体验后端能力。Afterglow 的主体能力在 `backend/`：
导入、向量库、检索、persona、生活状态、联网能力和 OpenAI 兼容 API 都由后端负责。
第三方程序接入时应优先调用后端 API，而不是依赖前端状态。

## 快速开始

```bash
cd frontend
pnpm install        # 或 npm install
pnpm dev            # 开发服务器，默认 http://localhost:5173
                    # 会把 /v1, /memory, /debug, /info 等代理到后端

# 若后端跑在别处：
VITE_BACKEND_URL=http://127.0.0.1:9000 pnpm dev

# 生产构建
pnpm build
pnpm preview
```

## 设计

- **时光信笺**：米色信笺 (#F5F1E4) + 黛蓝墨痕 (#1A2F4B) + 思源宋体 + 暖光粒子背景
- **拟人化打字**：SSE chunk 进队列，按真人打字节奏（每字 22-60ms + 标点停顿）逐字渲染
- **记忆溯源**：朋友的每条回复可点开右下角波纹图标，看到这条回复的灵感来自哪段历史聊天
- **诗化占位符**：`[图片]` → 模糊的胶片框 + "这张图片已随时间斑驳"
- **暗色模式**：深墨绿背景（避开纯黑），适合夜里翻看
- **首次引导**：让用户填名字、关系
- **设置页**：API key、字号、主题、模板、回写暂停

## 项目结构

```
src/
├── api/             # 后端调用封装（fetch + SSE）
├── components/      # 业务组件
│   ├── chat/        # 聊天 UI
│   ├── common/      # 通用：空状态、占位符消息、错误条
│   ├── layout/      # AppShell + AmbientCanvas
│   ├── memory/      # 记忆溯源 / 锚点
│   └── onboarding/  # 首次引导
├── composables/     # 组合式函数（打字机、自动滚动、markdown 渲染）
├── router/          # vue-router 配置
├── stores/          # Pinia stores（settings / chat / memory）
├── styles/          # tailwind.css
├── types/           # 与后端对应的类型定义
└── views/           # 路由页面（HomeView / SettingsView）
```

## License

AGPL-3.0-or-later（继承仓库根 LICENSE）。
