# -*- coding: utf-8 -*-
"""
记忆曲线服务 - SM-2算法实现
针对小学生语文词汇优化：初始EF=2.7（遗忘速度略慢于通用值2.5）
"""
from datetime import datetime, timedelta
from backend.models.word import UserRecord


# SM-2 算法参数（针对小学生优化）
INITIAL_EF = 2.7          # 初始难度因子（通用2.5，小学生词汇调高）
MIN_EF = 1.3              # 最小难度因子
INITIAL_INTERVAL = 1.0    # 首次间隔1天
SECOND_INTERVAL = 3.0     # 第二次间隔3天


def sm2_update(record: UserRecord, quality: int) -> UserRecord:
    """
    SM-2算法更新记忆参数
    
    quality: 0-5 评分
      5 = 完全正确，毫不犹豫
      4 = 正确，略有迟疑
      3 = 正确，但费力
      2 = 错误，但看到答案后想起来了
      1 = 错误，看到答案有印象
      0 = 完全不记得
    
    简化映射：听写对=5，错=1
    """
    now = datetime.now()
    
    if quality >= 3:
        # 正确
        record.correct_count += 1
        if record.repetition == 0:
            record.interval_days = INITIAL_INTERVAL
        elif record.repetition == 1:
            record.interval_days = SECOND_INTERVAL
        else:
            record.interval_days = record.interval_days * record.ease_factor
        record.repetition += 1
    else:
        # 错误 → 重置间隔
        record.error_count += 1
        record.repetition = 0
        record.interval_days = INITIAL_INTERVAL
    
    # 更新难度因子
    record.ease_factor = max(
        MIN_EF,
        record.ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    )
    
    record.last_review = now
    record.next_review = now + timedelta(days=record.interval_days)
    record.updated_at = now
    
    return record


def get_today_review_words(session, user_id='default'):
    """获取今日需要复习的词汇（next_review <= 今天）"""
    now = datetime.now()
    records = session.query(UserRecord).filter(
        UserRecord.user_id == user_id,
        UserRecord.next_review <= now,
        UserRecord.error_count > 0
    ).order_by(UserRecord.next_review.asc()).all()
    return records


def get_mistake_words(session, user_id='default', limit=50):
    """获取错题本（按错误次数降序）"""
    records = session.query(UserRecord).filter(
        UserRecord.user_id == user_id,
        UserRecord.error_count > 0
    ).order_by(UserRecord.error_count.desc()).limit(limit).all()
    return records


def init_word_record(session, user_id, word_id, word_text):
    """为新词创建初始记忆记录"""
    existing = session.query(UserRecord).filter_by(
        user_id=user_id, word_id=word_id
    ).first()
    if existing:
        return existing
    
    record = UserRecord(
        user_id=user_id,
        word_id=word_id,
        word_text=word_text,
        ease_factor=INITIAL_EF,
        interval_days=INITIAL_INTERVAL,
        repetition=0,
        next_review=datetime.now()
    )
    session.add(record)
    session.commit()
    return record
