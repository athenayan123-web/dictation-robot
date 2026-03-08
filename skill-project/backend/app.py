# -*- coding: utf-8 -*-
"""
报听写机器人 - Flask主应用
含：首次密钥授权弹窗 + 季度刷新提醒 + 全部API
"""
import os
import sys
import json
from pathlib import Path
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory

# 添加项目根目录到path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.config import (
    load_config, save_config, save_api_key, load_api_key,
    check_key_status, DB_PATH, DATA_DIR
)
from backend.models.word import init_db, Word, DictationTask, UserRecord, PhotoRecord
from backend.services.dictation_service import get_daily_words, submit_result, create_task
from backend.services.review_service import sm2_update, get_mistake_words, init_word_record
from backend.services.photo_service import recognize_image

app = Flask(__name__, static_folder=str(Path(__file__).parent.parent / 'skill' / 'web'))

# 初始化数据库
DATA_DIR.mkdir(parents=True, exist_ok=True)
engine, Session = init_db(str(DB_PATH))


# ============================================================
#  密钥授权 API（首次弹窗 + 季度刷新）
# ============================================================

@app.route('/api/auth/status', methods=['GET'])
def auth_status():
    """
    前端启动时调用，判断是否需要弹出授权对话框
    返回：need_first_setup / need_refresh / ok
    """
    status = check_key_status()
    
    if status['need_first_setup']:
        return jsonify({
            'action': 'show_dialog',
            'reason': 'first_setup',
            'title': '首次使用 - 请输入API密钥',
            'message': '报听写机器人需要AI大模型API密钥来识别照片中的文字。\n\n支持：阶跃星辰 / OpenAI\n\n密钥将加密存储在本地，不会上传。',
            'fields': [
                {'key': 'api_key', 'label': 'API Key', 'type': 'password', 'required': True,
                 'placeholder': '输入阶跃星辰或OpenAI的API Key'},
                {'key': 'model', 'label': '模型', 'type': 'select',
                 'options': ['step-1v-8k', 'step-1v-32k', 'step-2v-mini', 'gpt-4o-mini', 'gpt-4o']},
                {'key': 'base_url', 'label': 'API地址', 'type': 'select',
                 'options': ['https://api.stepfun.com/v1', 'https://api.openai.com/v1']}
            ]
        })
    
    if status['need_refresh']:
        return jsonify({
            'action': 'show_dialog',
            'reason': 'quarterly_refresh',
            'title': '季度安全提醒 - 请刷新API密钥',
            'message': f'您的API密钥已使用超过{status["refresh_cycle_days"]}天。\n为保障安全，建议更换新密钥。\n\n您也可以选择"稍后提醒"跳过本次。',
            'fields': [
                {'key': 'api_key', 'label': '新API Key', 'type': 'password', 'required': False,
                 'placeholder': '输入新密钥（留空则保留旧密钥）'}
            ],
            'allow_skip': True,
            'days_overdue': abs(status['days_remaining'])
        })
    
    return jsonify({
        'action': 'ok',
        'has_key': status['has_key'],
        'days_remaining': status['days_remaining'],
        'next_refresh': f'{status["days_remaining"]}天后'
    })


@app.route('/api/auth/submit', methods=['POST'])
def auth_submit():
    """提交密钥授权"""
    data = request.json or {}
    api_key = data.get('api_key', '').strip()
    model = data.get('model', 'step-1v-8k')
    base_url = data.get('base_url', 'https://api.stepfun.com/v1')
    
    if not api_key:
        # 跳过（季度刷新时允许）
        cfg = load_config()
        cfg['key_last_reminded'] = datetime.now().isoformat()
        # 延长30天再提醒
        if cfg.get('key_created_at'):
            cfg['key_refresh_days'] = cfg.get('key_refresh_days', 90) + 30
        save_config(cfg)
        return jsonify({'success': True, 'action': 'skipped', 'message': '已跳过，30天后再次提醒'})
    
    # 验证密钥有效性（仅警告，不阻止保存）
    key_valid = None
    import requests as req
    try:
        resp = req.get(
            f'{base_url}/models',
            headers={'Authorization': f'Bearer {api_key}'},
            timeout=10
        )
        if resp.status_code == 401:
            key_valid = False
        else:
            key_valid = True
    except Exception:
        key_valid = None  # 网络问题，不阻止保存
    
    # 保存
    save_api_key(api_key)
    cfg = load_config()
    cfg['llm_model'] = model
    cfg['llm_base_url'] = base_url
    cfg['key_refresh_days'] = 90  # 重置为90天
    save_config(cfg)
    
    return jsonify({
        'success': True,
        'message': '密钥已加密保存，90天后提醒刷新' + ('' if key_valid is not False else '（注意：密钥验证未通过，请确认是否正确）'),
        'key_valid': key_valid
    })


# ============================================================
#  课程数据 API
# ============================================================

@app.route('/api/subjects', methods=['GET'])
def get_subjects():
    return jsonify({'subjects': [
        {'id': 'chinese', 'name': '语文', 'publisher': '人教版'},
        {'id': 'english', 'name': '英语', 'publisher': '人教版PEP'}
    ]})


@app.route('/api/grades/<subject>', methods=['GET'])
def get_grades(subject):
    session = Session()
    grades = session.query(Word.grade).filter(Word.subject == subject).distinct().all()
    session.close()
    return jsonify({'grades': [{'id': i, 'name': g[0]} for i, g in enumerate(grades)]})


@app.route('/api/words/search', methods=['GET'])
def search_words():
    """搜索词汇"""
    q = request.args.get('q', '')
    subject = request.args.get('subject', 'chinese')
    session = Session()
    words = session.query(Word).filter(
        Word.subject == subject,
        Word.text.contains(q)
    ).limit(100).all()
    session.close()
    return jsonify({'words': [{'id': w.id, 'text': w.text, 'grade': w.grade,
                               'unit': w.unit, 'lesson_title': w.lesson_title} for w in words]})


# ============================================================
#  听写任务 API
# ============================================================

@app.route('/api/task/create', methods=['POST'])
def api_create_task():
    data = request.json
    session = Session()
    task = create_task(
        session,
        name=data.get('name', '听写任务'),
        subject=data.get('subject', 'chinese'),
        words=data.get('words', []),
        repeat_count=data.get('repeatCount', 3),
        interval_sec=data.get('interval', 5),
        schedule_type=data.get('scheduleType', 'once'),
        schedule_time=data.get('scheduleTime', '07:30'),
        schedule_date=data.get('scheduleDate', ''),
        schedule_days=data.get('scheduleDays', ''),
        use_memory_curve=data.get('useMemoryCurve', False)
    )
    session.close()
    return jsonify({'success': True, 'taskId': task.id})


@app.route('/api/task/list', methods=['GET'])
def api_list_tasks():
    session = Session()
    tasks = session.query(DictationTask).order_by(DictationTask.created_at.desc()).all()
    result = []
    for t in tasks:
        result.append({
            'id': t.id, 'name': t.name, 'subject': t.subject,
            'words': json.loads(t.words_json),
            'repeatCount': t.repeat_count, 'interval': t.interval_sec,
            'scheduleType': t.schedule_type, 'scheduleTime': t.schedule_time,
            'enabled': t.enabled, 'status': t.status,
            'nextRunAt': t.next_run_at.isoformat() if t.next_run_at else None
        })
    session.close()
    return jsonify({'tasks': result})


@app.route('/api/dictation/submit', methods=['POST'])
def api_submit_result():
    """提交听写对/错"""
    data = request.json
    session = Session()
    result = submit_result(
        session,
        user_id=data.get('userId', 'default'),
        word_text=data.get('word', ''),
        word_id=data.get('wordId', 0),
        is_correct=data.get('isCorrect', True)
    )
    session.close()
    return jsonify(result)


# ============================================================
#  错题本 API
# ============================================================

@app.route('/api/mistakes', methods=['GET'])
def api_mistakes():
    session = Session()
    records = get_mistake_words(session)
    result = [{
        'word': r.word_text, 'errorCount': r.error_count,
        'correctCount': r.correct_count,
        'nextReview': r.next_review.isoformat() if r.next_review else None,
        'easeFactor': round(r.ease_factor, 2)
    } for r in records]
    session.close()
    return jsonify({'mistakes': result})


# ============================================================
#  拍照识别 API
# ============================================================

@app.route('/api/ocr/recognize', methods=['POST'])
def api_ocr():
    """接收base64图片，调用LLM识别"""
    data = request.json or {}
    result = recognize_image(
        image_base64=data.get('imageBase64'),
        mime_type=data.get('mimeType', 'image/jpeg'),
        prompt=data.get('prompt')
    )
    
    if result['success']:
        # 保存识别记录
        session = Session()
        record = PhotoRecord(
            raw_text=result.get('raw_text', ''),
            words_json=json.dumps(result.get('words', []), ensure_ascii=False),
            model_used=result.get('model', '')
        )
        session.add(record)
        session.commit()
        session.close()
    
    return jsonify(result)


@app.route('/api/ocr/import', methods=['POST'])
def api_ocr_import():
    """将识别结果导入词库"""
    data = request.json
    words = data.get('words', [])
    grade = data.get('grade', '')
    unit = data.get('unit', 0)
    subject = data.get('subject', 'chinese')
    
    session = Session()
    imported = 0
    for w_text in words:
        existing = session.query(Word).filter_by(text=w_text, grade=grade, unit=unit).first()
        if not existing:
            word = Word(text=w_text, grade=grade, unit=unit, subject=subject, source='photo')
            session.add(word)
            imported += 1
    session.commit()
    session.close()
    
    return jsonify({'success': True, 'imported': imported, 'total': len(words)})


# ============================================================
#  静态文件（前端网页）
# ============================================================

@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')


# ============================================================
#  启动
# ============================================================

if __name__ == '__main__':
    cfg = load_config()
    port = cfg.get('server_port', 3801)
    print(f'\n  报听写机器人 SKILL后端')
    print(f'  http://localhost:{port}')
    print(f'  数据库: {DB_PATH}')
    status = check_key_status()
    if status['need_first_setup']:
        print(f'  ⚠️  首次运行，请在网页中输入API密钥')
    elif status['need_refresh']:
        print(f'  ⚠️  密钥已过期，请刷新')
    else:
        print(f'  ✅ 密钥状态正常，{status["days_remaining"]}天后提醒刷新')
    print()
    app.run(host='0.0.0.0', port=port, debug=True)
