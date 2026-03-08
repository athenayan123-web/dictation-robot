<#
  报听写机器人 - 微信小程序自动部署脚本
  功能：检查环境 → 生成代码 → 上传小程序 → 输出指引
#>

$ErrorActionPreference = "Stop"
$ProjectRoot = "E:\智能整理\dictation-robot"
$DeployDir = Join-Path $ProjectRoot "deploy"
$MiniDir = Join-Path $ProjectRoot "miniprogram"

Write-Host ""
Write-Host "═══════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  报听写机器人 - 微信小程序自动部署" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# ===== 步骤1: 检查环境 =====
Write-Host "[1/5] 检查环境配置..." -ForegroundColor Yellow

$AppId = $env:WX_APPID
$KeyPath = Join-Path $DeployDir "private.key"

if (-not $AppId) {
    Write-Host "  ❌ 未设置 WX_APPID 环境变量" -ForegroundColor Red
    Write-Host "  请运行: `$env:WX_APPID='你的小程序AppID'" -ForegroundColor White
    exit 1
}

if (-not (Test-Path $KeyPath)) {
    Write-Host "  ❌ 未找到代码上传密钥: $KeyPath" -ForegroundColor Red
    Write-Host "  请前往 mp.weixin.qq.com → 开发 → 开发设置 → 下载代码上传密钥" -ForegroundColor White
    exit 1
}

Write-Host "  ✅ AppID: $AppId" -ForegroundColor Green
Write-Host "  ✅ 密钥文件已找到" -ForegroundColor Green

# ===== 步骤2: 生成小程序代码 =====
Write-Host "`n[2/5] 生成小程序代码..." -ForegroundColor Yellow

# 确保目录存在
$dirs = @("pages\index", "pages\dictation", "pages\camera", "static")
foreach ($d in $dirs) {
    $p = Join-Path $MiniDir $d
    if (-not (Test-Path $p)) { New-Item -ItemType Directory -Path $p -Force | Out-Null }
}

# 生成图标
& node (Join-Path $MiniDir "generate_icons.js") 2>$null
Write-Host "  ✅ TabBar图标已生成" -ForegroundColor Green

# 更新 project.config.json 中的 appid
$projConfig = Join-Path $MiniDir "project.config.json"
if (Test-Path $projConfig) {
    $cfg = Get-Content $projConfig -Raw | ConvertFrom-Json
    $cfg.appid = $AppId
    $cfg | ConvertTo-Json -Depth 10 | Set-Content $projConfig -Encoding UTF8
    Write-Host "  ✅ 已更新 AppID 配置" -ForegroundColor Green
}

# ===== 步骤3: 安装 miniprogram-ci =====
Write-Host "`n[3/5] 检查 CI 工具..." -ForegroundColor Yellow

Set-Location $DeployDir
if (-not (Test-Path (Join-Path $DeployDir "node_modules\miniprogram-ci"))) {
    Write-Host "  正在安装 miniprogram-ci..." -ForegroundColor White
    npm install miniprogram-ci --registry=https://registry.npmmirror.com 2>&1 | Out-Null
}
Write-Host "  ✅ miniprogram-ci 已就绪" -ForegroundColor Green

# ===== 步骤4: 上传代码 =====
Write-Host "`n[4/5] 上传小程序代码..." -ForegroundColor Yellow
Write-Host "  版本: 1.0.0" -ForegroundColor Gray
Write-Host "  描述: 报听写机器人 - 预约听写/拍照识别" -ForegroundColor Gray
Write-Host ""

$env:WX_APPID = $AppId
node (Join-Path $DeployDir "upload.js")

if ($LASTEXITCODE -ne 0) {
    Write-Host "`n  ❌ 上传失败，请检查错误信息" -ForegroundColor Red
    exit 1
}

# ===== 步骤5: 输出指引 =====
Write-Host ""
Write-Host "═══════════════════════════════════════════════════" -ForegroundColor Green
Write-Host "  ✅ 小程序代码上传成功！" -ForegroundColor Green
Write-Host "═══════════════════════════════════════════════════" -ForegroundColor Green
Write-Host ""
Write-Host "  接下来需要人工操作：" -ForegroundColor Yellow
Write-Host ""
Write-Host "  1. 登录 mp.weixin.qq.com" -ForegroundColor White
Write-Host "  2. 进入「管理」→「版本管理」" -ForegroundColor White
Write-Host "  3. 在「开发版本」中找到 V1.0.0" -ForegroundColor White
Write-Host "  4. 点击「提交审核」" -ForegroundColor White
Write-Host "  5. 填写审核信息（类目选：教育-在线教育）" -ForegroundColor White
Write-Host "  6. 审核通过后点击「全量发布」" -ForegroundColor White
Write-Host ""
Write-Host "  服务器域名配置：" -ForegroundColor Yellow
Write-Host "    request合法域名: https://你的服务器地址" -ForegroundColor White
Write-Host "    socket合法域名: wss://你的服务器地址" -ForegroundColor White
Write-Host ""
Write-Host "  预览二维码生成：" -ForegroundColor Yellow
Write-Host "    cd $DeployDir" -ForegroundColor Gray
Write-Host "    node preview.js" -ForegroundColor Gray
Write-Host ""

Set-Location $ProjectRoot
