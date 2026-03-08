# -*- coding: utf-8 -*-
"""数据模型 - SQLAlchemy ORM"""
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, Text
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

Base = declarative_base()


class Word(Base):
    """词汇表"""
    __tablename__ = 'words'
    id = Column(Integer, primary_key=True, autoincrement=True)
    text = Column(String(50), nullable=False, index=True)
    pinyin = Column(String(100), default='')
    grade = Column(String(20), default='')       # 三年级下册
    unit = Column(Integer, default=0)             # 单元
    lesson = Column(Integer, default=0)           # 课
    lesson_title = Column(String(50), default='')
    subject = Column(String(10), default='chinese')  # chinese / english
    source = Column(String(20), default='textbook')  # textbook / photo / manual
    created_at = Column(DateTime, default=datetime.now)


class UserRecord(Base):
    """用户听写记录（含记忆曲线）"""
    __tablename__ = 'user_records'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(50), default='default', index=True)
    word_id = Column(Integer, index=True)
    word_text = Column(String(50), default='')
    is_correct = Column(Boolean, default=None)
    error_count = Column(Integer, default=0)
    correct_count = Column(Integer, default=0)
    # SM-2 记忆曲线参数
    ease_factor = Column(Float, default=2.5)      # 难度因子
    interval_days = Column(Float, default=1.0)    # 当前间隔（天）
    repetition = Column(Integer, default=0)       # 复习次数
    last_review = Column(DateTime, default=None)
    next_review = Column(DateTime, default=None)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class DictationTask(Base):
    """听写任务"""
    __tablename__ = 'dictation_tasks'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), default='')
    subject = Column(String(10), default='chinese')
    words_json = Column(Text, default='[]')       # JSON序列化的词汇列表
    repeat_count = Column(Integer, default=3)
    interval_sec = Column(Integer, default=5)
    schedule_type = Column(String(20), default='once')  # once/daily/weekly
    schedule_time = Column(String(10), default='07:30')
    schedule_days = Column(String(50), default='')      # 1,3,5
    schedule_date = Column(String(20), default='')
    enabled = Column(Boolean, default=True)
    use_memory_curve = Column(Boolean, default=False)
    status = Column(String(20), default='pending')
    last_run_at = Column(DateTime, default=None)
    next_run_at = Column(DateTime, default=None)
    created_at = Column(DateTime, default=datetime.now)


class PhotoRecord(Base):
    """拍照识别记录"""
    __tablename__ = 'photo_records'
    id = Column(Integer, primary_key=True, autoincrement=True)
    image_path = Column(String(200), default='')
    raw_text = Column(Text, default='')
    words_json = Column(Text, default='[]')
    model_used = Column(String(50), default='')
    created_at = Column(DateTime, default=datetime.now)


def init_db(db_path: str):
    """初始化数据库"""
    engine = create_engine(f'sqlite:///{db_path}', echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return engine, Session
