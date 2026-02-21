# What Should I Eat Today 🍽️

UW-Madison 食堂菜单分析器 - 根据你的口味偏好，推荐今天去哪个食堂吃饭。

## 功能

- 📊 **智能排名** - 根据你的评分，对食堂进行排名
- ⭐ **半星评分** - 1-10分制，支持半星（0.5-5星显示）
- 📱 **Telegram Bot** - 每日自动推送推荐
- 💾 **Preset 系统** - 保存和切换不同的评分配置
- 🔄 **菜单缓存** - Parquet 格式高效存储

## 本地运行

```bash
# 安装依赖
uv sync

# 启动后端
uv run uvicorn src.api:app --reload

# 启动前端（另一个终端）
cd web && npm install && npm run dev
```

访问 http://localhost:5173

## 部署到 Railway

1. Fork 这个仓库
2. 在 [railway.app](https://railway.app) 创建新项目
3. 选择 "Deploy from GitHub repo"
4. 配置环境变量（可选）：
   - `TELEGRAM_BOT_TOKEN` - Telegram Bot Token
   - `TELEGRAM_CHAT_ID` - 推送目标 Chat ID

## 技术栈

- **后端**: FastAPI + Polars + Pydantic
- **前端**: Vue 3 + TypeScript + Vite
- **数据**: JSON (ratings) + Parquet (cache)
- **Bot**: python-telegram-bot

## API

| 端点 | 描述 |
|------|------|
| `GET /api/recommend/{date}` | 获取推荐排名 |
| `GET /api/menu/{hall}/{date}` | 获取菜单 |
| `POST /api/ratings` | 保存评分 |
| `GET /api/presets` | 获取预设列表 |
| `POST /api/cache/refresh` | 刷新缓存 |

## License

MIT
