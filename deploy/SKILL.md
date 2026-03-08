# 报听写机器人 - 微信小程序自动部署 Skill

## 概述
本 Skill 提供报听写机器人小程序的完整自动化部署方案，包含代码生成、CI 上传、审核辅助等全流程。

## 前置条件
1. 已注册微信小程序账号 (mp.weixin.qq.com)
2. 已获取 AppID
3. 已下载代码上传密钥 (private.key)

## 快速开始

### 1. 配置环境变量
```powershell
$env:WX_APPID="你的小程序AppID"
```

### 2. 一键部署
```powershell
cd E:\智能整理\dictation-robot\deploy
.\deploy_miniprogram.ps1
```

### 3. 自动完成的内容
- ✅ 生成小程序完整代码结构
- ✅ 自动配置 project.config.json
- ✅ 生成 TabBar 图标
- ✅ 上传代码到微信服务器
- ✅ 生成预览二维码

### 4. 需人工完成的步骤
- ⚠️ 登录微信公众平台提交审核
- ⚠️ 配置服务器域名 (request合法域名)
- ⚠️ 审核通过后点击"全量发布"

## API 对接说明

### 后端接口
```
GET  /api/subjects          # 获取科目列表
GET  /api/grades/:subject   # 获取年级列表
GET  /api/units/:subject/:grade    # 获取单元列表
GET  /api/lessons/:subject/:grade/:unit  # 获取课文列表
GET  /api/words/:subject/:grade/:unit/:lesson  # 获取词汇
POST /api/task/create       # 创建预约任务
GET  /api/tasks             # 获取任务列表
PUT  /api/task/:id          # 更新任务
DELETE /api/task/:id        # 删除任务
```

### 预约参数
```json
{
  "scheduleType": "daily",    // once | daily | weekly
  "scheduleTime": "07:30",    // HH:MM
  "scheduleDate": "2026-03-10",  // once模式必填
  "scheduleDays": [1,3,5],    // weekly模式：周一三五
  "scheduleEndDate": "2026-06-30"  // 可选截止日期
}
```

## 目录结构
```
miniprogram/
├── app.js              # 小程序入口
├── app.json            # 全局配置
├── app.wxss            # 全局样式
├── pages/
│   ├── index/          # 选课页面
│   ├── dictation/      # 听写播放页面
│   └── camera/         # 拍照识别页面
└── static/             # 图标资源
```

## 部署脚本说明

### deploy_miniprogram.ps1
主部署脚本，功能：
1. 检查环境 (AppID、密钥文件)
2. 生成小程序代码
3. 安装 miniprogram-ci
4. 执行代码上传
5. 输出后续操作指引

### upload.js
使用 miniprogram-ci 上传代码：
```javascript
const ci = require('miniprogram-ci');
const project = new ci.Project({
  appid: process.env.WX_APPID,
  type: 'miniProgram',
  projectPath: './miniprogram',
  privateKeyPath: './private.key'
});
ci.upload({ project, version: '1.0.0', desc: '报听写机器人' });
```

### preview.js
生成预览二维码，用于测试：
```javascript
ci.preview({
  project,
  qrcodeFormat: 'image',
  qrcodeOutputDest: '../preview_qrcode.jpg'
});
```

## 服务器配置
小程序需要配置以下合法域名：
- request合法域名: `https://你的服务器域名`
- socket合法域名: `wss://你的服务器域名`
- uploadFile合法域名: `https://你的服务器域名`

## 常见问题

### Q: 上传失败提示 "private key error"
A: 检查 private.key 文件是否正确放置，或重新下载密钥

### Q: 提示 "IP 不在白名单"
A: 在微信公众平台关闭 IP 白名单，或添加当前 IP

### Q: 小程序无法连接后端
A: 确保已配置服务器域名，且后端支持 HTTPS

## 版本历史
- v1.0.0 (2026-03-06): 初始版本，支持预约听写、拍照识别
