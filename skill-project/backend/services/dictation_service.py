# -*- coding: utf-8 -*-
"""
听写核心服务
"""
import json
from datetime import datetime, timedelta
from backend.models.word import Word, DictationTask, UserRecord
from backend.services.review_service import sm2_update, get_today_review_words, init_word_record


def get_daily_words(session, user_id='default', grade=None, unit=None, lesson=None):
    """
    获取今日听写词单
    优先级：1.记忆曲线到期词 → 2.指定课文词 → 3.错题词
    """
    words = []
    
    # 1. 记忆曲线到期的复习词
    review_records = get_today_review_words(session, user_id)
    for r in review_records:
        words.append({'text': r.word_text, 'source': 'review', 'record_id': r.id})
    
    # 2. 指定课文的新词
    if grade or unit is not None or lesson is not None:
        query = session.query(Word)
        if grade:
            query = query.filter(Word.grade == grade)
        if unit is not None:
            query = query.filter(Word.unit == unit)
        if lesson is not None:
            query = query.filter(Word.lesson == lesson)
        
        db_words = query.all()
        existing_texts = {w['text'] for w in words}
        for w in db_words:
            if w.text not in existing_texts:
                words.append({'text': w.text, 'source': 'textbook', 'word_id': w.id})
                existing_texts.add(w.text)
    
    return words


def submit_result(session, user_id, word_text, word_id, is_correct):
    """
    提交听写结果，更新SM-2记忆曲线
    """
    # 确保有记录
    record = session.query(UserRecord).filter_by(
        user_id=user_id, word_id=word_id
    ).first()
    
    if not record:
        record = init_word_record(session, user_id, word_id, word_text)
    
    # SM-2 评分：对=5，错=1
    quality = 5 if is_correct else 1
    record = sm2_update(record, quality)
    record.is_correct = is_correct
    
    session.commit()
    
    return {
        'word': word_text,
        'is_correct': is_correct,
        'next_review': record.next_review.isoformat() if record.next_review else None,
        'interval_days': round(record.interval_days, 1),
        'ease_factor': round(record.ease_factor, 2),
        'error_count': record.error_count,
        'correct_count': record.correct_count
    }


def create_task(session, name, subject, words, repeat_count=3, interval_sec=5,
                schedule_type='once', schedule_time='07:30', schedule_date='',
                schedule_days='', use_memory_curve=False):
    """创建听写任务"""
    task = DictationTask(
        name=name,
        subject=subject,
        words_json=json.dumps(words, ensure_ascii=False),
        repeat_count=repeat_count,
        interval_sec=interval_sec,
        schedule_type=schedule_type,
        schedule_time=schedule_time,
        schedule_date=schedule_date,
        schedule_days=schedule_days,
        use_memory_curve=use_memory_curve,
        enabled=True,
        status='pending',
        next_run_at=calc_next_run(schedule_type, schedule_time, schedule_date, schedule_days)
    )
    session.add(task)
    session.commit()
    return task


def calc_next_run(schedule_type, schedule_time, schedule_date='', schedule_days=''):
    """计算下次运行时间"""
    now = datetime.now()
    h, m = map(int, (schedule_time or '07:30').split(':'))
    
    if schedule_type == 'once' and schedule_date:
        d = datetime.strptime(f'{schedule_date} {schedule_time}', '%Y-%m-%d %H:%M')
        return d if d > now else None
    
    if schedule_type == 'daily':
        today = now.replace(hour=h, minute=m, second=0, microsecond=0)
        return today if today > now else today + timedelta(days=1)
    
    if schedule_type == 'weekly' and schedule_days:
        days = [int(d) for d in schedule_days.split(',') if d.strip()]
        for offset in range(8):
            d = now + timedelta(days=offset)
            d = d.replace(hour=h, minute=m, second=0, microsecond=0)
            dow = d.isoweekday()
            if dow in days and d > now:
                return d
    
    return None
