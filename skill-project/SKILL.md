# 报听写机器人 - SKILL 技能文档

## 1. 技能概述

| 项目 | 说明 |
|------|------|
| 技能名称 | 智能听写机器人 |
| 版本 | 2.0.0 |
| 适用平台 | 微信小程序 / Web网页 / 桌面端 |
| 技术栈 | Python 3.9 + Flask + SQLAlchemy + Node.js |
| 数据覆盖 | 人教版语文12册3198字 + 英语PEP 8册952词 |
| 核心算法 | SM-2记忆曲线（针对小学生优化EF=2.7） |
| AI能力 | 阶跃星辰step-1v视觉大模型 / OpenAI GPT-4o |

## 2. 最优化逻辑路径

### 2.1 系统启动流程

```
启动 → 检查密钥状态
  ├─ 首次运行 → 弹出授权对话框 → 用户输入API Key → 加密存储 → 进入主界面
  ├─ 密钥过期(>90天) → 弹出刷新提醒 → 用户更新/跳过 → 进入主界面
  └─ 密钥正常 → 直接进入主界面
```

**密钥安全机制：**
- 基于机器特征的XOR对称加密，密钥不以明文存储
- 每90天（季度）自动弹窗提醒刷新
- 跳过后延长30天再次提醒
- 支持运行时通过API动态更新

### 2.2 听写核心流程

```
选择课程 → 生成词单 → 预约时间 → 定时触发
                                      ↓
                              播放引擎启动
                                      ↓
                        ┌─ 读词（TTS语音合成）
                        │     ↓ 等待5秒
                        │  读词（第2遍）
                        │     ↓ 等待5秒
                        │  读词（第3遍）
                        │     ↓ 等待5秒
                        │  用户标记 ✓对 / ✗错
                        │     ↓
                        │  SM-2算法更新记忆参数
                        │     ↓
                        └─ 下一个词 ──→ 全部完成
```

**词单生成优先级：**
1. 记忆曲线到期词（`next_review <= now`，最紧迫优先）
2. 指定课文新词
3. 错题本高频错词

### 2.3 SM-2 记忆曲线算法

**参数设定（针对小学生语文优化）：**

| 参数 | 通用值 | 优化值 | 说明 |
|------|--------|--------|------|
| 初始EF | 2.5 | **2.7** | 小学生词汇遗忘速度略慢 |
| 最小EF | 1.3 | 1.3 | 防止间隔过短 |
| 首次间隔 | 1天 | 1天 | 次日复习 |
| 第二次间隔 | 6天 | **3天** | 加快早期巩固 |

**更新公式：**
```python
if quality >= 3:  # 正确
    if repetition == 0: interval = 1天
    elif repetition == 1: interval = 3天
    else: interval = interval × EF
    repetition += 1
else:  # 错误
    interval = 1天  # 重置
    repetition = 0

EF = max(1.3, EF + 0.1 - (5-q)×(0.08 + (5-q)×0.02))
next_review = now + interval
```

**质量评分映射：** 听写对 → q=5，听写错 → q=1

### 2.4 拍照识别流程

```
用户拍照/上传 → 图片转Base64
                    ↓
        检查API Key是否配置
          ├─ 未配置 → 弹出授权对话框
          └─ 已配置 → 调用LLM视觉模型
                          ↓
                  Prompt: "精确识别图片中所有词语，
                          每个词语单独一行输出"
                          ↓
                  解析返回文本 → 按行分割
                          ↓
                  去序号/标点 → 去空行 → 去重
                          ↓
                  展示识别结果 → 用户确认/编辑
                          ↓
                  导入词库 → 生成SM-2初始记录
```

**容错策略：**
- LLM超时(60s) → 提示重试
- 识别结果为空 → 提供"词语模式"/"单字模式"重新识别
- API Key失效 → 自动弹出授权对话框

### 2.5 预约调度流程

```
用户设置预约规则
  ├─ 单次: 指定日期+时间
  ├─ 每天: 指定时间（如07:30）
  └─ 每周: 指定周几+时间

调度器（每分钟检查）
  ↓
  遍历所有enabled任务
  ↓
  if now >= next_run_at:
    执行听写 → 更新last_run_at
    ├─ 单次任务 → 标记completed
    └─ 周期任务 → 计算下次next_run_at
```

## 3. 数据模型

### 3.1 数据库表结构

```
words (词汇表)
├── id, text, pinyin, grade, unit, lesson
├── lesson_title, subject, source
└── created_at

user_records (用户记录 + SM-2参数)
├── id, user_id, word_id, word_text
├── is_correct, error_count, correct_count
├── ease_factor, interval_days, repetition
├── last_review, next_review
└── created_at, updated_at

dictation_tasks (听写任务)
├── id, name, subject, words_json
├── repeat_count, interval_sec
├── schedule_type, schedule_time, schedule_days
├── enabled, status, use_memory_curve
└── next_run_at, last_run_at, created_at

photo_records (拍照记录)
├── id, image_path, raw_text, words_json
├── model_used
└── created_at
```

## 4. API 接口清单

### 4.1 授权接口
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/auth/status` | 检查密钥状态（首次/过期/正常） |
| POST | `/api/auth/submit` | 提交密钥授权 |

### 4.2 课程接口
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/subjects` | 科目列表 |
| GET | `/api/grades/:subject` | 年级列表 |
| GET | `/api/words/search?q=` | 搜索词汇 |

### 4.3 听写接口
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/task/create` | 创建任务 |
| GET | `/api/task/list` | 任务列表 |
| POST | `/api/dictation/submit` | 提交对/错结果 |

### 4.4 错题本接口
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/mistakes` | 错题列表（按错误次数降序） |

### 4.5 拍照识别接口
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/ocr/recognize` | LLM视觉识别 |
| POST | `/api/ocr/import` | 导入识别结果到词库 |

## 5. 测试覆盖

| 测试模块 | 用例数 | 通过率 | 覆盖内容 |
|----------|--------|--------|----------|
| 密钥加解密 | 3 | 100% | 中英文加密、不同输入不同密文 |
| 密钥状态 | 3 | 100% | 首次运行、设置后、90天过期 |
| SM-2算法 | 5 | 100% | 间隔递增、错误重置、EF下限、复习时间 |
| 听写服务 | 3 | 100% | 按课/按单元取词、复习优先级 |
| 提交结果 | 2 | 100% | 正确/错误提交 |
| 定时调度 | 4 | 100% | 单次/每天/每周/过期任务 |
| **总计** | **20** | **100%** | |

## 6. 部署与运行

### 6.1 环境要求
```bash
conda create -n dictation_skill python=3.9
conda activate dictation_skill
conda install flask sqlalchemy requests pillow pytest apscheduler pypinyin
```

### 6.2 启动命令
```bash
cd skill-project
python backend/app.py
# 服务启动于 http://localhost:3801
# 首次访问自动弹出API Key授权对话框
```

### 6.3 密钥配置方式
1. **网页弹窗**：首次启动自动弹出，输入后加密存储
2. **环境变量**：`set STEP_API_KEY=你的密钥`
3. **API调用**：`POST /api/auth/submit`

### 6.4 季度刷新机制
- 密钥创建90天后自动弹窗提醒
- 用户可选择更新密钥或跳过（延长30天）
- 跳过后下次提醒间隔递增，不会频繁打扰

## 7. 文件结构

```
skill-project/
├── backend/
│   ├── app.py                    # Flask主应用（含授权API）
│   ├── config.py                 # 配置+密钥加密存储
│   ├── models/word.py            # SQLAlchemy数据模型
│   └── services/
│       ├── dictation_service.py  # 听写核心逻辑
│       ├── review_service.py     # SM-2记忆曲线
│       └── photo_service.py      # LLM视觉识别
├── tests/test_all.py             # 20个自动化测试
├── skill/                        # SKILL插件目录
│   ├── skill.json                # 插件配置
│   └── web/index.html            # 前端页面
├── data/                         # 数据存储
│   ├── dictation.db              # SQLite数据库
│   ├── config.json               # 运行配置
│   └── .secrets.enc              # 加密密钥文件
└── SKILL.md                      # 本文档
```

## 8. 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0.0 | 2026-03-06 | 初始版本：基础听写+预约 |
| 2.0.0 | 2026-03-08 | 新增：SM-2记忆曲线、LLM拍照识别、密钥授权弹窗、季度刷新、20项自动化测试 |
