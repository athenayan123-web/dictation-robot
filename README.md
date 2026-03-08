# 📝 报听写机器人 Dictation Robot

> **中国浙江 · 杭州学军小学306班 出品**
> 
> Author: Karl \<athenayan123@gmail.com\>

智能听写机器人，基于人教版语文和英语教材，支持SM-2记忆曲线自动复习、LLM大模型拍照识别、预约定时听写。

## ✨ 功能特性

- **人教版全覆盖**：语文12册3198字 + 英语PEP 8册952词
- **智能听写**：每词3遍，间隔5秒，TTS语音合成
- **预约系统**：支持单次/每天/每周定时听写（默认每天7:30）
- **SM-2记忆曲线**：针对小学生优化（EF=2.7），自动安排复习日期
- **错题本**：自动记录错词，按遗忘曲线智能复习
- **拍照识别**：调用阶跃星辰/OpenAI视觉大模型，拍照自动导入词库
- **暂停/继续**：听写过程中可随时暂停
- **密钥安全**：加密存储API Key，每季度自动提醒刷新
- **多端支持**：Web网页 + 微信小程序

## 🚀 快速开始

### 方式一：网页端（推荐）

```bash
cd server
npm install
node src/app.js
# 访问 http://localhost:3800
```

### 方式二：SKILL后端（含记忆曲线+拍照识别）

```bash
conda create -n dictation_skill python=3.9 -y
conda activate dictation_skill
conda install flask sqlalchemy requests pillow pytest apscheduler pypinyin -c conda-forge -y
cd skill-project
python backend/app.py
# 访问 http://localhost:3801
```

### 方式三：双击启动

- `启动报听写机器人.bat` — 启动网页端
- `skill-project/启动SKILL.bat` — 启动SKILL后端

## 📁 项目结构

```
dictation-robot/
├── server/                    # Node.js 后端服务
│   ├── src/app.js            # 主服务（API + WebSocket + 定时调度）
│   └── data/                 # 人教版词汇数据库（JSON）
├── web/                      # Web前端（单文件HTML）
├── miniprogram/              # 微信小程序代码
├── skill-project/            # Python SKILL技能插件
│   ├── backend/              # Flask后端
│   │   ├── app.py           # 主应用（含密钥授权弹窗）
│   │   ├── config.py        # 密钥加密存储
│   │   ├── models/          # SQLAlchemy数据模型
│   │   └── services/        # 核心服务
│   │       ├── dictation_service.py   # 听写逻辑
│   │       ├── review_service.py      # SM-2记忆曲线
│   │       └── photo_service.py       # LLM视觉识别
│   ├── tests/               # 自动化测试（20项100%通过）
│   ├── skill/               # SKILL插件配置
│   └── SKILL.md             # 技能文档
├── deploy/                   # 部署脚本
├── copyright/                # 软著材料
└── 可分享网页版.html          # 单文件可分享版本
```

## 🧠 SM-2 记忆曲线算法

针对小学生语文词汇优化：

| 参数 | 值 | 说明 |
|------|-----|------|
| 初始EF | 2.7 | 高于通用值2.5，适配小学生遗忘速度 |
| 首次间隔 | 1天 | 次日复习 |
| 第二次间隔 | 3天 | 加快早期巩固 |
| 后续间隔 | interval × EF | 指数递增 |

答对 → 间隔递增，答错 → 重置为1天重新学习。

## 🔑 密钥管理

- 首次启动自动弹出授权对话框
- 支持阶跃星辰 Step API / OpenAI API
- 密钥基于机器特征加密存储，不上传
- 每90天自动弹窗提醒刷新

## 🧪 测试

```bash
cd skill-project
python -m pytest tests/ -v
# 20 passed ✅
```

测试覆盖：密钥加解密、SM-2算法、听写词单生成、提交结果、定时调度。

## 📋 API 接口

| 接口 | 说明 |
|------|------|
| `GET /api/subjects` | 科目列表 |
| `GET /api/grades/:subject` | 年级列表 |
| `POST /api/task/create` | 创建听写任务 |
| `POST /api/dictation/submit` | 提交对/错结果 |
| `GET /api/mistakes` | 错题本 |
| `POST /api/ocr/recognize` | LLM拍照识别 |
| `GET /api/auth/status` | 密钥状态检查 |
| `POST /api/auth/submit` | 提交密钥授权 |

## 👨‍🎓 关于

**中国浙江 · 杭州学军小学306班**

本项目旨在帮助小学生高效完成每日听写练习，通过科学的记忆曲线算法提升学习效果。

## 📄 License

MIT License
