# -*- coding: utf-8 -*-
"""
模拟数据测试 - 验证核心逻辑
"""
import sys
import json
import pytest
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent))

from backend.config import encrypt_secret, decrypt_secret, check_key_status, save_api_key, load_api_key, save_config, load_config, SECRETS_FILE, CONFIG_FILE, DATA_DIR
from backend.models.word import init_db, Word, UserRecord, DictationTask, Base
from backend.services.review_service import sm2_update, get_today_review_words, get_mistake_words, init_word_record, INITIAL_EF
from backend.services.dictation_service import get_daily_words, submit_result, calc_next_run


# ===== 测试用内存数据库 =====
@pytest.fixture
def db_session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    engine = create_engine('sqlite:///:memory:', echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    # 插入模拟数据：三年级下册第一单元
    test_words = [
        ("优惠", "三年级下册", 1, 1, "古诗三首"),
        ("惠及", "三年级下册", 1, 1, "古诗三首"),
        ("融化", "三年级下册", 1, 1, "古诗三首"),
        ("燕子", "三年级下册", 1, 2, "燕子"),
        ("乌黑", "三年级下册", 1, 2, "燕子"),
        ("剪刀", "三年级下册", 1, 2, "燕子"),
        ("活泼", "三年级下册", 1, 2, "燕子"),
        ("荷花", "三年级下册", 1, 3, "荷花"),
        ("公园", "三年级下册", 1, 3, "荷花"),
        ("清香", "三年级下册", 1, 3, "荷花"),
        ("匕首", "三年级下册", 1, 0, "语文园地一"),
        ("乙方", "三年级下册", 1, 0, "语文园地一"),
    ]
    for text, grade, unit, lesson, title in test_words:
        w = Word(text=text, grade=grade, unit=unit, lesson=lesson, lesson_title=title, subject='chinese')
        session.add(w)
    session.commit()
    
    yield session
    session.close()


# ===== 1. 密钥加解密测试 =====
class TestEncryption:
    def test_encrypt_decrypt(self):
        """加密后解密应还原"""
        original = "sk-test-key-1234567890abcdef"
        encrypted = encrypt_secret(original)
        decrypted = decrypt_secret(encrypted)
        assert decrypted == original
        assert encrypted != original  # 密文不等于明文
    
    def test_encrypt_chinese(self):
        """中文密钥也能正确加解密"""
        original = "测试密钥-abc123"
        assert decrypt_secret(encrypt_secret(original)) == original
    
    def test_different_inputs_different_outputs(self):
        """不同输入产生不同密文"""
        e1 = encrypt_secret("key1")
        e2 = encrypt_secret("key2")
        assert e1 != e2


# ===== 2. 密钥状态检查测试 =====
class TestKeyStatus:
    def setup_method(self):
        """每个测试前清理"""
        if SECRETS_FILE.exists():
            SECRETS_FILE.unlink()
        if CONFIG_FILE.exists():
            CONFIG_FILE.unlink()
    
    def test_first_run(self):
        """首次运行应要求输入密钥"""
        status = check_key_status()
        assert status['need_first_setup'] == True
        assert status['has_key'] == False
    
    def test_after_setup(self):
        """设置密钥后不再要求首次设置"""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        save_api_key("test-key-123")
        status = check_key_status()
        assert status['need_first_setup'] == False
        assert status['has_key'] == True
        assert status['days_remaining'] == 90
    
    def test_quarterly_refresh(self):
        """90天后应提醒刷新"""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        save_api_key("test-key-old")
        cfg = load_config()
        cfg['key_created_at'] = (datetime.now() - timedelta(days=91)).isoformat()
        save_config(cfg)
        status = check_key_status()
        assert status['need_refresh'] == True
        assert status['days_remaining'] == 0
    
    def teardown_method(self):
        if SECRETS_FILE.exists():
            SECRETS_FILE.unlink()
        if CONFIG_FILE.exists():
            CONFIG_FILE.unlink()


# ===== 3. SM-2 记忆曲线算法测试 =====
class TestSM2Algorithm:
    def test_correct_increases_interval(self):
        """答对应增加复习间隔"""
        record = UserRecord(ease_factor=INITIAL_EF, interval_days=1.0, repetition=0,
                           error_count=0, correct_count=0)
        record = sm2_update(record, quality=5)  # 完全正确
        assert record.interval_days == 1.0  # 首次=1天
        assert record.repetition == 1
        
        record = sm2_update(record, quality=5)
        assert record.interval_days == 3.0  # 第二次=3天
        assert record.repetition == 2
        
        record = sm2_update(record, quality=5)
        assert record.interval_days > 3.0  # 第三次 = 3 * EF > 3
        assert record.repetition == 3
    
    def test_wrong_resets_interval(self):
        """答错应重置间隔为1天"""
        record = UserRecord(ease_factor=INITIAL_EF, interval_days=10.0, repetition=5,
                           error_count=0, correct_count=0)
        record = sm2_update(record, quality=1)  # 错误
        assert record.interval_days == 1.0
        assert record.repetition == 0
        assert record.error_count == 1
    
    def test_ef_decreases_on_wrong(self):
        """连续答错应降低难度因子"""
        record = UserRecord(ease_factor=INITIAL_EF, interval_days=1.0, repetition=0,
                           error_count=0, correct_count=0)
        ef_before = record.ease_factor
        record = sm2_update(record, quality=1)
        assert record.ease_factor < ef_before
    
    def test_ef_minimum(self):
        """难度因子不应低于1.3"""
        record = UserRecord(ease_factor=1.3, interval_days=1.0, repetition=0,
                           error_count=0, correct_count=0)
        for _ in range(10):
            record = sm2_update(record, quality=0)
        assert record.ease_factor >= 1.3
    
    def test_next_review_set(self):
        """更新后应设置下次复习时间"""
        record = UserRecord(ease_factor=INITIAL_EF, interval_days=1.0, repetition=0,
                           error_count=0, correct_count=0)
        record = sm2_update(record, quality=5)
        assert record.next_review is not None
        assert record.last_review is not None
        assert record.next_review > record.last_review


# ===== 4. 听写词单生成测试 =====
class TestDictationService:
    def test_get_words_by_lesson(self, db_session):
        """按课文获取词汇"""
        words = get_daily_words(db_session, grade='三年级下册', unit=1, lesson=2)
        texts = [w['text'] for w in words]
        assert '燕子' in texts
        assert '乌黑' in texts
        assert '荷花' not in texts  # 不同课的不应出现
    
    def test_get_words_by_unit(self, db_session):
        """按单元获取全部词汇"""
        words = get_daily_words(db_session, grade='三年级下册', unit=1)
        texts = [w['text'] for w in words]
        assert len(texts) == 12  # 模拟数据共12个词
        assert '优惠' in texts
        assert '匕首' in texts
    
    def test_review_words_priority(self, db_session):
        """记忆曲线到期词应优先出现"""
        # 创建一个到期的复习记录
        record = UserRecord(
            user_id='default', word_id=1, word_text='优惠',
            error_count=2, ease_factor=2.5, interval_days=1,
            next_review=datetime.now() - timedelta(hours=1)
        )
        db_session.add(record)
        db_session.commit()
        
        words = get_daily_words(db_session, user_id='default', grade='三年级下册', unit=1)
        # 第一个应该是复习词
        assert words[0]['text'] == '优惠'
        assert words[0]['source'] == 'review'


# ===== 5. 提交结果测试 =====
class TestSubmitResult:
    def test_submit_correct(self, db_session):
        """提交正确结果"""
        result = submit_result(db_session, 'default', '燕子', 4, True)
        assert result['is_correct'] == True
        assert result['correct_count'] == 1
        assert result['next_review'] is not None
    
    def test_submit_wrong(self, db_session):
        """提交错误结果"""
        result = submit_result(db_session, 'default', '荷花', 8, False)
        assert result['is_correct'] == False
        assert result['error_count'] == 1
        assert result['interval_days'] == 1.0  # 重置为1天


# ===== 6. 定时调度测试 =====
class TestSchedule:
    def test_once_future(self):
        """单次任务（未来日期）"""
        future = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        result = calc_next_run('once', '07:30', schedule_date=future)
        assert result is not None
        assert result > datetime.now()
    
    def test_once_past(self):
        """单次任务（过去日期）应返回None"""
        past = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        result = calc_next_run('once', '07:30', schedule_date=past)
        assert result is None
    
    def test_daily(self):
        """每日任务应返回今天或明天"""
        result = calc_next_run('daily', '07:30')
        assert result is not None
        assert result >= datetime.now()
    
    def test_weekly(self):
        """每周任务"""
        result = calc_next_run('weekly', '07:30', schedule_days='1,2,3,4,5')
        assert result is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
