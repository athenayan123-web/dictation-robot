const express = require('express');
const cors = require('cors');
const cron = require('node-cron');
const multer = require('multer');
const { WebSocketServer } = require('ws');
const http = require('http');
const https = require('https');
const path = require('path');
const fs = require('fs');
const { v4: uuidv4 } = require('uuid');

// ===== LLM 视觉识别配置 =====
// 支持阶跃星辰 Step API / OpenAI / 任何兼容 OpenAI 格式的大模型
const LLM_CONFIG = {
  apiKey: process.env.STEP_API_KEY || process.env.OPENAI_API_KEY || '',
  baseUrl: process.env.LLM_BASE_URL || 'https://api.stepfun.com/v1',
  model: process.env.LLM_MODEL || 'step-1v-8k',  // 阶跃视觉模型
};

async function callVisionLLM(base64Image, mimeType, prompt) {
  const url = `${LLM_CONFIG.baseUrl}/chat/completions`;
  const body = JSON.stringify({
    model: LLM_CONFIG.model,
    messages: [
      {
        role: 'system',
        content: '你是一个专业的OCR文字识别助手。你需要精确识别图片中的所有文字内容，特别是中文汉字和英文单词。请按行输出识别到的文字，保持原始排版。如果图片中包含听写词汇、生字表、词语表等教材内容，请逐词提取，每个词语单独一行输出。不要添加任何额外解释。'
      },
      {
        role: 'user',
        content: [
          { type: 'text', text: prompt || '请精确识别这张图片中的所有文字内容，逐词逐行输出。如果是词语表/生字表，每个词语单独一行。' },
          { type: 'image_url', image_url: { url: `data:${mimeType};base64,${base64Image}` } }
        ]
      }
    ],
    temperature: 0.1,
    max_tokens: 4096
  });

  return new Promise((resolve, reject) => {
    const urlObj = new URL(url);
    const options = {
      hostname: urlObj.hostname,
      port: urlObj.port || 443,
      path: urlObj.pathname,
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${LLM_CONFIG.apiKey}`,
        'Content-Length': Buffer.byteLength(body)
      }
    };
    const req = https.request(options, res => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          const json = JSON.parse(data);
          if (json.error) reject(new Error(json.error.message || JSON.stringify(json.error)));
          else resolve(json.choices?.[0]?.message?.content || '');
        } catch (e) { reject(new Error('LLM响应解析失败: ' + data.substring(0, 200))); }
      });
    });
    req.on('error', reject);
    req.setTimeout(60000, () => { req.destroy(); reject(new Error('LLM请求超时')); });
    req.write(body);
    req.end();
  });
}

const app = express();
const server = http.createServer(app);
const wss = new WebSocketServer({ server });

app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname, '..', 'web-dist')));
app.use('/uploads', express.static(path.join(__dirname, '..', 'uploads')));

// 数据文件
const DATA_DIR = path.join(__dirname, '..', 'user-data');
if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true });

const chineseData = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'data', 'chinese_textbook.json'), 'utf-8'));
const englishData = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'data', 'english_textbook.json'), 'utf-8'));

// 用户数据持久化
const TASK_FILE = path.join(DATA_DIR, 'tasks.json');
const MISTAKE_FILE = path.join(DATA_DIR, 'mistakes.json');
const CUSTOM_DB_FILE = path.join(DATA_DIR, 'custom_words.json');
const PAUSE_STATE_FILE = path.join(DATA_DIR, 'pause_state.json');

let tasks = {}, mistakes = {}, customWords = {}, pauseState = {};
if (fs.existsSync(TASK_FILE)) tasks = JSON.parse(fs.readFileSync(TASK_FILE, 'utf-8'));
if (fs.existsSync(MISTAKE_FILE)) mistakes = JSON.parse(fs.readFileSync(MISTAKE_FILE, 'utf-8'));
if (fs.existsSync(CUSTOM_DB_FILE)) customWords = JSON.parse(fs.readFileSync(CUSTOM_DB_FILE, 'utf-8'));
if (fs.existsSync(PAUSE_STATE_FILE)) pauseState = JSON.parse(fs.readFileSync(PAUSE_STATE_FILE, 'utf-8'));

function saveTasks() { fs.writeFileSync(TASK_FILE, JSON.stringify(tasks, null, 2), 'utf-8'); }
function saveMistakes() { fs.writeFileSync(MISTAKE_FILE, JSON.stringify(mistakes, null, 2), 'utf-8'); }
function saveCustomWords() { fs.writeFileSync(CUSTOM_DB_FILE, JSON.stringify(customWords, null, 2), 'utf-8'); }
function savePauseState() { fs.writeFileSync(PAUSE_STATE_FILE, JSON.stringify(pauseState, null, 2), 'utf-8'); }

// WebSocket
const clients = new Map();
wss.on('connection', ws => {
  const id = uuidv4();
  clients.set(id, ws);
  ws.send(JSON.stringify({ type: 'connected', clientId: id }));
  ws.on('close', () => clients.delete(id));
  ws.on('message', data => handleClientMessage(ws, JSON.parse(data)));
});

function broadcast(data) {
  const msg = JSON.stringify(data);
  clients.forEach(ws => { if (ws.readyState === 1) ws.send(msg); });
}

function handleClientMessage(ws, data) {
  if (data.type === 'pause') {
    pauseState[data.taskId] = { paused: true, pausedAt: new Date().toISOString(), wordIndex: data.wordIndex, repeatIndex: data.repeatIndex };
    savePauseState();
    broadcast({ type: 'dictation_paused', taskId: data.taskId });
  }
  if (data.type === 'resume') {
    delete pauseState[data.taskId];
    savePauseState();
    broadcast({ type: 'dictation_resumed', taskId: data.taskId, resumeFrom: data.resumeFrom });
  }
  if (data.type === 'mistake') {
    recordMistake(data.taskId, data.word, data.isCorrect);
  }
}

// ===== 错题记录 =====
function recordMistake(taskId, word, isCorrect) {
  const task = tasks[taskId];
  if (!task) return;
  const key = `${task.subject}_${task.name}`;
  if (!mistakes[key]) mistakes[key] = { subject: task.subject, name: task.name, wrongWords: [], createdAt: new Date().toISOString() };
  
  if (!isCorrect) {
    const existing = mistakes[key].wrongWords.find(w => w.word === (word.word || word));
    if (existing) {
      existing.count++;
      existing.lastWrongAt = new Date().toISOString();
    } else {
      mistakes[key].wrongWords.push({ word: word.word || word, chinese: word.chinese || '', count: 1, firstWrongAt: new Date().toISOString(), lastWrongAt: new Date().toISOString() });
    }
  }
  saveMistakes();
}

// 艾宾浩斯遗忘曲线间隔（分钟）：5, 30, 12h, 1d, 2d, 4d, 7d, 15d
const EBBINGHAUS_INTERVALS = [5, 30, 720, 1440, 2880, 5760, 10080, 21600];

function calcMemoryCurveSchedule(baseTime, reviewCount = 0) {
  const intervals = EBBINGHAUS_INTERVALS.slice(reviewCount);
  return intervals.map((mins, idx) => {
    const t = new Date(baseTime);
    t.setMinutes(t.getMinutes() + mins);
    return { time: t.toISOString(), reviewNumber: reviewCount + idx + 1 };
  });
}

// ===== 课程API =====
app.get('/api/subjects', (_, res) => res.json({ subjects: [
  { id: 'chinese', name: '语文', publisher: '人教版' },
  { id: 'english', name: '英语', publisher: '人教版PEP' }
]}));

app.get('/api/grades/:subject', (req, res) => {
  const d = req.params.subject === 'chinese' ? chineseData : englishData;
  res.json({ grades: d.grades.map((g, i) => ({ id: i, name: g.grade })) });
});

app.get('/api/units/:subject/:gid', (req, res) => {
  const d = req.params.subject === 'chinese' ? chineseData : englishData;
  const g = d.grades[+req.params.gid];
  if (!g) return res.status(404).json({ error: '年级不存在' });
  const isEn = req.params.subject === 'english';
  res.json({ grade: g.grade, units: g.units.map((u, i) => ({
    id: i, unit: u.unit, title: u.title,
    lessonCount: isEn ? 1 : (u.lessons?.length || 0),
    wordCount: isEn ? u.words.length : undefined, hasLessons: !isEn
  }))});
});

app.get('/api/lessons/:subject/:gid/:uid', (req, res) => {
  const d = req.params.subject === 'chinese' ? chineseData : englishData;
  const g = d.grades[+req.params.gid];
  const u = g?.units[+req.params.uid];
  if (!u) return res.status(404).json({ error: '不存在' });
  if (req.params.subject === 'english') {
    return res.json({ grade: g.grade, unit: u.title, lessons: [{ id: 0, lesson: u.unit, title: u.title, wordCount: u.words.length, words: u.words }] });
  }
  res.json({ grade: g.grade, unit: u.title, lessons: u.lessons.map((l, i) => ({ id: i, lesson: l.lesson, title: l.title, wordCount: l.words.length, words: l.words })) });
});

app.get('/api/words/:subject/:gid/:uid/:lid', (req, res) => {
  const d = req.params.subject === 'chinese' ? chineseData : englishData;
  const g = d.grades[+req.params.gid];
  const u = g?.units[+req.params.uid];
  if (!u) return res.status(404).json({ error: '不存在' });
  if (req.params.subject === 'english') {
    return res.json({ subject: 'english', grade: g.grade, unit: u.title, lesson: u.title, words: u.words });
  }
  const l = u.lessons?.[+req.params.lid];
  if (!l) return res.status(404).json({ error: '不存在' });
  res.json({ subject: 'chinese', grade: g.grade, unit: u.title, lesson: l.title, words: l.words });
});

// ===== 拍照上传 → LLM视觉识别 =====
const upload = multer({
  dest: path.join(__dirname, '..', 'uploads'),
  limits: { fileSize: 10 * 1024 * 1024 },
  fileFilter: (req, file, cb) => {
    if (file.mimetype.startsWith('image/')) cb(null, true);
    else cb(new Error('仅支持图片文件'));
  }
});

app.post('/api/ocr/upload', upload.single('image'), async (req, res) => {
  if (!req.file) return res.status(400).json({ error: '请上传图片' });

  const filePath = req.file.path;
  const mimeType = req.file.mimetype || 'image/jpeg';

  try {
    // 读取图片转base64
    const imgBuffer = fs.readFileSync(filePath);
    const base64Image = imgBuffer.toString('base64');
    const prompt = req.body.prompt || '请精确识别图片中的所有文字。如果是词语表、生字表或听写内容，请每个词语单独一行输出，不要加序号和标点。';

    let rawText = '';
    let usedLLM = false;

    if (LLM_CONFIG.apiKey) {
      // 有API Key，调用LLM大模型识别
      console.log(`[OCR] 调用 ${LLM_CONFIG.model} 识别图片...`);
      rawText = await callVisionLLM(base64Image, mimeType, prompt);
      usedLLM = true;
      console.log(`[OCR] 识别完成，长度: ${rawText.length}`);
    } else {
      // 无API Key，返回base64让前端处理
      return res.json({
        success: false,
        error: 'no_api_key',
        message: '未配置LLM API Key，请在前端使用浏览器OCR或手动输入',
        imageBase64: base64Image,
        mimeType
      });
    }

    // 解析词汇：按行分割，清洗
    const words = rawText
      .split(/[\n\r]+/)
      .map(w => w.replace(/^[\d.、\-\s]+/, '').trim())  // 去序号
      .filter(w => w.length > 0 && w.length < 30 && !/^[#\-=*]/.test(w));  // 去无效行

    // 保存识别图片（保留原文件，重命名为有意义的名字）
    const ext = mimeType.split('/')[1] || 'jpg';
    const savedName = `ocr_${Date.now()}.${ext}`;
    const savedPath = path.join(__dirname, '..', 'uploads', savedName);
    fs.renameSync(filePath, savedPath);

    res.json({
      success: true,
      usedLLM,
      model: LLM_CONFIG.model,
      rawText,
      words,
      wordCount: words.length,
      imagePath: `/uploads/${savedName}`
    });
  } catch (err) {
    console.error('[OCR] 识别失败:', err.message);
    // 失败时也返回图片base64，让前端可以展示
    try {
      const imgBuffer = fs.readFileSync(filePath);
      res.json({
        success: false,
        error: err.message,
        message: 'LLM识别失败，请手动输入',
        imageBase64: imgBuffer.toString('base64'),
        mimeType
      });
    } catch (e) {
      res.status(500).json({ error: 'OCR识别失败: ' + err.message });
    }
  }
});

// 二次识别：对已上传图片用不同prompt重新识别
app.post('/api/ocr/re-recognize', async (req, res) => {
  const { imageBase64, mimeType, prompt } = req.body;
  if (!imageBase64) return res.status(400).json({ error: '缺少图片数据' });
  if (!LLM_CONFIG.apiKey) return res.status(400).json({ error: '未配置API Key' });

  try {
    const rawText = await callVisionLLM(imageBase64, mimeType || 'image/jpeg', prompt);
    const words = rawText
      .split(/[\n\r]+/)
      .map(w => w.replace(/^[\d.、\-\s]+/, '').trim())
      .filter(w => w.length > 0 && w.length < 30 && !/^[#\-=*]/.test(w));

    res.json({ success: true, rawText, words, wordCount: words.length });
  } catch (err) {
    res.status(500).json({ error: 'LLM识别失败: ' + err.message });
  }
});

// LLM配置状态
app.get('/api/llm/status', (_, res) => {
  res.json({
    configured: !!LLM_CONFIG.apiKey,
    model: LLM_CONFIG.model,
    baseUrl: LLM_CONFIG.baseUrl.replace(/\/v1$/, ''),
    hint: LLM_CONFIG.apiKey ? '已配置' : '请设置环境变量 STEP_API_KEY 或 OPENAI_API_KEY'
  });
});

// 动态设置API Key（运行时）
app.post('/api/llm/config', (req, res) => {
  const { apiKey, model, baseUrl } = req.body;
  if (apiKey) LLM_CONFIG.apiKey = apiKey;
  if (model) LLM_CONFIG.model = model;
  if (baseUrl) LLM_CONFIG.baseUrl = baseUrl;
  res.json({ success: true, configured: !!LLM_CONFIG.apiKey, model: LLM_CONFIG.model });
});

// 将拍照内容添加到自定义数据库
app.post('/api/custom-words/add', (req, res) => {
  const { name, subject, words, sourceImage } = req.body;
  const id = uuidv4();
  customWords[id] = {
    id, name, subject, words, sourceImage,
    createdAt: new Date().toISOString(),
    reviewSchedule: calcMemoryCurveSchedule(new Date())
  };
  saveCustomWords();
  res.json({ success: true, id, message: '已添加到自定义听写库' });
});

app.get('/api/custom-words', (req, res) => {
  res.json({ words: Object.values(customWords) });
});

app.delete('/api/custom-words/:id', (req, res) => {
  delete customWords[req.params.id];
  saveCustomWords();
  res.json({ success: true });
});

// ===== 错题本API =====
app.get('/api/mistakes', (req, res) => {
  const list = Object.values(mistakes).map(m => ({
    ...m,
    totalWrong: m.wrongWords.reduce((sum, w) => sum + w.count, 0),
    uniqueWrong: m.wrongWords.length
  }));
  res.json({ mistakes: list });
});

app.get('/api/mistakes/:key', (req, res) => {
  const m = mistakes[req.params.key];
  if (!m) return res.status(404).json({ error: '未找到' });
  res.json(m);
});

// 基于错题生成记忆曲线复习任务
app.post('/api/mistakes/review-task', (req, res) => {
  const { mistakeKey } = req.body;
  const m = mistakes[mistakeKey];
  if (!m || !m.wrongWords.length) return res.status(400).json({ error: '没有错字' });
  
  const words = m.wrongWords.sort((a, b) => b.count - a.count).slice(0, 20); // 取错误最多的20个
  const id = uuidv4();
  const now = new Date();
  
  // 使用记忆曲线生成复习计划
  const schedule = calcMemoryCurveSchedule(now);
  
  tasks[id] = {
    id, name: `错题复习: ${m.name}`, subject: m.subject, words,
    repeatCount: 3, interval: 5,
    schedule: { type: 'memory-curve', times: schedule.map(s => s.time) },
    enabled: true, status: 'pending',
    createdAt: now.toISOString(),
    nextRunAt: schedule[0].time,
    isMistakeReview: true,
    mistakeKey
  };
  saveTasks();
  res.json({ taskId: id, task: tasks[id], schedule });
});

// 标记错字已掌握
app.post('/api/mistakes/master', (req, res) => {
  const { mistakeKey, word } = req.body;
  if (mistakes[mistakeKey]) {
    mistakes[mistakeKey].wrongWords = mistakes[mistakeKey].wrongWords.filter(w => w.word !== word);
    saveMistakes();
  }
  res.json({ success: true });
});

// 实时记录对/错
app.post('/api/mistakes/record', (req, res) => {
  const { taskId, subject, word, hint, isCorrect, wordIndex } = req.body;
  const key = taskId || 'default';
  if (!mistakes[key]) {
    const t = tasks[taskId];
    mistakes[key] = {
      key,
      name: t ? t.name : '听写记录',
      subject: subject || 'chinese',
      wrongWords: [],
      correctWords: [],
      createdAt: new Date().toISOString()
    };
  }
  const m = mistakes[key];
  if (isCorrect) {
    if (!m.correctWords) m.correctWords = [];
    if (!m.correctWords.includes(word)) m.correctWords.push(word);
    // 如果之前标记过错，移除
    m.wrongWords = m.wrongWords.filter(w => w.word !== word);
  } else {
    const existing = m.wrongWords.find(w => w.word === word);
    if (existing) {
      existing.count++;
      existing.lastWrongAt = new Date().toISOString();
    } else {
      m.wrongWords.push({ word, hint: hint || '', count: 1, firstWrongAt: new Date().toISOString(), lastWrongAt: new Date().toISOString() });
    }
  }
  saveMistakes();
  res.json({ success: true, isCorrect, word });
});

// ===== 任务API（含记忆曲线）=====
app.post('/api/task/create', (req, res) => {
  const { subject, gradeId, unitId, lessonId, customWords: cw,
    repeatCount = 3, interval = 5,
    scheduleType = 'once',
    scheduleTime = '07:30',
    scheduleDate = '',
    scheduleDays = [],
    scheduleEndDate = '',
    useMemoryCurve = false,  // 新增：是否使用记忆曲线
    enabled = true
  } = req.body;

  let words = cw || [];
  let taskName = '自定义听写';

  if (!cw && subject != null) {
    const d = subject === 'chinese' ? chineseData : englishData;
    const g = d.grades[+gradeId]; const u = g?.units[+unitId];
    if (subject === 'english') {
      if (!u) return res.status(400).json({ error: '单元不存在' });
      words = u.words; taskName = `${g.grade} Unit${u.unit} ${u.title}`;
    } else {
      const l = u?.lessons?.[+lessonId];
      if (!l) return res.status(400).json({ error: '课文不存在' });
      words = l.words; taskName = `${g.grade} 第${l.lesson}课 ${l.title}`;
    }
  }

  const id = uuidv4();
  const now = new Date();
  
  let schedule, nextRunAt;
  
  if (useMemoryCurve) {
    // 使用艾宾浩斯记忆曲线
    const curveSchedule = calcMemoryCurveSchedule(now);
    schedule = { type: 'memory-curve', times: curveSchedule.map(s => s.time) };
    nextRunAt = curveSchedule[0].time;
  } else {
    schedule = { type: scheduleType, time: scheduleTime, date: scheduleDate, days: scheduleDays, endDate: scheduleEndDate };
    nextRunAt = calcNextRun(schedule);
  }

  tasks[id] = {
    id, name: taskName, subject: subject || 'custom', words,
    repeatCount, interval,
    schedule,
    enabled, status: 'pending',
    createdAt: now.toISOString(),
    lastRunAt: null,
    nextRunAt,
    useMemoryCurve: !!useMemoryCurve,
    reviewCount: 0  // 记忆曲线复习次数
  };
  saveTasks();
  res.json({ taskId: id, task: tasks[id] });
});

app.put('/api/task/:id', (req, res) => {
  const t = tasks[req.params.id];
  if (!t) return res.status(404).json({ error: '任务不存在' });
  const { scheduleType, scheduleTime, scheduleDate, scheduleDays, scheduleEndDate, enabled, repeatCount, interval } = req.body;
  if (scheduleType !== undefined) t.schedule.type = scheduleType;
  if (scheduleTime !== undefined) t.schedule.time = scheduleTime;
  if (scheduleDate !== undefined) t.schedule.date = scheduleDate;
  if (scheduleDays !== undefined) t.schedule.days = scheduleDays;
  if (scheduleEndDate !== undefined) t.schedule.endDate = scheduleEndDate;
  if (enabled !== undefined) t.enabled = enabled;
  if (repeatCount !== undefined) t.repeatCount = repeatCount;
  if (interval !== undefined) t.interval = interval;
  t.nextRunAt = calcNextRun(t.schedule);
  saveTasks();
  res.json({ task: t });
});

app.get('/api/tasks', (_, res) => {
  Object.values(tasks).forEach(t => { if (t.enabled && !t.useMemoryCurve) t.nextRunAt = calcNextRun(t.schedule); });
  res.json({ tasks: Object.values(tasks) });
});

app.delete('/api/task/:id', (req, res) => { delete tasks[req.params.id]; saveTasks(); res.json({ ok: true }); });

app.post('/api/task/start/:id', (req, res) => {
  const t = tasks[req.params.id];
  if (!t) return res.status(404).json({ error: '任务不存在' });
  executeDictation(t);
  res.json({ ok: true });
});

app.get('/api/dictation/sequence/:id', (req, res) => {
  const t = tasks[req.params.id];
  if (!t) return res.status(404).json({ error: '任务不存在' });
  res.json({ task: t, pauseState: pauseState[req.params.id] || null });
});

// ===== 计算下次运行时间 =====
function calcNextRun(schedule) {
  const now = new Date();
  const [h, m] = (schedule.time || '07:30').split(':').map(Number);

  if (schedule.type === 'once') {
    if (!schedule.date) return null;
    const d = new Date(schedule.date + 'T' + schedule.time + ':00');
    return d > now ? d.toISOString() : null;
  }
  if (schedule.type === 'daily') {
    const today = new Date(now); today.setHours(h, m, 0, 0);
    if (today > now) return today.toISOString();
    today.setDate(today.getDate() + 1);
    return today.toISOString();
  }
  if (schedule.type === 'weekly' && schedule.days?.length) {
    for (let offset = 0; offset < 8; offset++) {
      const d = new Date(now); d.setDate(d.getDate() + offset); d.setHours(h, m, 0, 0);
      const dow = d.getDay() || 7;
      if (schedule.days.includes(dow) && d > now) {
        if (schedule.endDate && d > new Date(schedule.endDate + 'T23:59:59')) return null;
        return d.toISOString();
      }
    }
  }
  return null;
}

// ===== 定时调度器 =====
cron.schedule('* * * * *', () => {
  const now = new Date();
  Object.values(tasks).forEach(t => {
    if (!t.enabled || !t.nextRunAt) return;
    const next = new Date(t.nextRunAt);
    if (now >= next && now - next < 60000) {
      console.log(`[调度] 执行: ${t.name}`);
      executeDictation(t);
      t.lastRunAt = now.toISOString();
      
      if (t.useMemoryCurve && t.schedule.type === 'memory-curve') {
        // 记忆曲线：更新到下一个复习点
        t.reviewCount++;
        if (t.reviewCount < t.schedule.times.length) {
          t.nextRunAt = t.schedule.times[t.reviewCount];
        } else {
          t.enabled = false;
          t.status = 'completed';
        }
      } else if (t.schedule.type === 'once') {
        t.enabled = false;
        t.status = 'completed';
      } else {
        t.nextRunAt = calcNextRun(t.schedule);
      }
      saveTasks();
    }
  });
});

// ===== 执行听写（支持暂停）=====
const runningDictations = new Map();

function executeDictation(task) {
  task.status = 'running'; saveTasks();
  const isEn = task.subject === 'english';
  
  // 检查是否有暂停状态
  const paused = pauseState[task.id];
  let startIndex = 0;
  if (paused && paused.paused) {
    startIndex = paused.wordIndex || 0;
    delete pauseState[task.id];
    savePauseState();
  }
  
  broadcast({ 
    type: 'dictation_start', 
    taskId: task.id, 
    taskName: task.name, 
    totalWords: task.words.length,
    startIndex,
    message: `听写开始！${task.name}，共${task.words.length}个${isEn?'单词':'字词'}` 
  });

  let idx = startIndex;
  const totalDelay = (task.repeatCount * 2 + task.interval * task.repeatCount + 5) * 1000;
  
  runningDictations.set(task.id, { task, isEn, interval: task.interval, repeatCount: task.repeatCount, paused: false });
  
  function readNextWord() {
    const state = runningDictations.get(task.id);
    if (!state || state.paused) return;
    
    if (idx >= task.words.length) {
      finishDictation(task);
      return;
    }

    const word = task.words[idx];
    const text = isEn ? (word.word || word) : word;
    const hint = isEn && word.chinese ? word.chinese : '';
    let repeatIdx = 0;

    speakWithDelay(`第${idx + 1}个`, 'zh-CN', 0);

    setTimeout(() => doRepeat(), 2000);

    function doRepeat() {
      const s = runningDictations.get(task.id);
      if (!s || s.paused) return;
      if (repeatIdx >= task.repeatCount) {
        idx++;
        broadcast({ type: 'dictation_word_complete', taskId: task.id, wordIndex: idx - 1 });
        setTimeout(readNextWord, (task.interval + 2) * 1000);
        return;
      }

      repeatIdx++;
      broadcast({
        type: 'dictation_word',
        taskId: task.id,
        wordIndex: idx,
        repeat: repeatIdx,
        totalRepeat: task.repeatCount,
        text,
        hint,
        lang: isEn ? 'en-US' : 'zh-CN',
        totalWords: task.words.length
      });

      speakWithDelay(text, isEn ? 'en-US' : 'zh-CN', 0);
      setTimeout(doRepeat, task.interval * 1000);
    }
  }

  setTimeout(readNextWord, 3000);
}

function speakWithDelay(text, lang, delay) {
  // 实际TTS由前端处理，这里只是触发
}

function finishDictation(task) {
  runningDictations.delete(task.id);
  broadcast({ type: 'dictation_end', taskId: task.id, message: '听写结束！' });
  task.status = task.useMemoryCurve ? 'pending' : 'completed';
  if (!task.useMemoryCurve && task.schedule.type !== 'once') task.status = 'pending';
  saveTasks();
}

// 暂停/恢复API
app.post('/api/dictation/:id/pause', (req, res) => {
  const state = runningDictations.get(req.params.id);
  if (state) {
    state.paused = true;
    pauseState[req.params.id] = { paused: true, pausedAt: new Date().toISOString(), ...req.body };
    savePauseState();
    broadcast({ type: 'dictation_paused', taskId: req.params.id });
  }
  res.json({ ok: true });
});

app.post('/api/dictation/:id/resume', (req, res) => {
  const state = runningDictations.get(req.params.id);
  if (state) {
    state.paused = false;
    delete pauseState[req.params.id];
    savePauseState();
    broadcast({ type: 'dictation_resumed', taskId: req.params.id });
  }
  res.json({ ok: true });
});

app.get('/api/dictation/:id/status', (req, res) => {
  const state = runningDictations.get(req.params.id);
  res.json({ 
    running: !!state, 
    paused: state?.paused || false,
    pauseState: pauseState[req.params.id] || null
  });
});

app.get('*', (_, res) => {
  const p = path.join(__dirname, '..', 'web-dist', 'index.html');
  if (fs.existsSync(p)) res.sendFile(p);
  else res.send('报听写机器人服务已启动');
});

const PORT = process.env.PORT || 3800;
server.listen(PORT, () => console.log(`\n  报听写机器人 http://localhost:${PORT}\n  功能：预约/记忆曲线/错题本/暂停\n`));
