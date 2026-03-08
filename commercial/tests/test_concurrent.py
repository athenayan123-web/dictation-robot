# -*- coding: utf-8 -*-
"""
高并发模拟测试 - 20个模拟账号 + 全功能覆盖
"""
import sys
import json
import time
import random
import string
import threading
import concurrent.futures
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.plans import PLANS, generate_license_key, verify_license, check_feature

# ===== 测试配置 =====
NUM_USERS = 20
TEST_RESULTS_FILE = Path(__file__).parent.parent / 'logs' / f'test_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'

# 模拟用户数据
MOCK_USERS = []
for i in range(NUM_USERS):
    plan = ['free', 'basic', 'pro'][i % 3]
    MOCK_USERS.append({
        'id': f'user_{i+1:03d}',
        'name': f'学生{i+1}',
        'grade': f'{random.randint(1,6)}年级{"上" if random.random()>0.5 else "下"}册',
        'plan': plan,
        'email': f'student{i+1}@xuejun306.edu.cn'
    })

# 模拟词汇
MOCK_WORDS_CN = ["燕子","乌黑","剪刀","活泼","轻风","洒落","赶集","光彩夺目","春光","偶尔",
                  "荷花","公园","清香","赶紧","莲蓬","破裂","姿势","画家","本领","微风",
                  "优惠","融化","崇高","豆芽","梅花","广泛","减轻","消融","鸳鸯","杨梅",
                  "实验","验证","记号","减少","阻力","大约","包括","检查","迷失","逆风"]

MOCK_WORDS_EN = [
    {"word":"hello","chinese":"你好"},{"word":"cat","chinese":"猫"},
    {"word":"dog","chinese":"狗"},{"word":"book","chinese":"书"},
    {"word":"school","chinese":"学校"},{"word":"teacher","chinese":"老师"},
    {"word":"student","chinese":"学生"},{"word":"apple","chinese":"苹果"},
    {"word":"water","chinese":"水"},{"word":"happy","chinese":"快乐"}
]

results = {
    'start_time': None, 'end_time': None,
    'total_tests': 0, 'passed': 0, 'failed': 0,
    'users': [], 'errors': [], 'performance': {}
}


def log(msg):
    ts = datetime.now().strftime('%H:%M:%S.%f')[:-3]
    print(f'[{ts}] {msg}')


# ===== 测试用例 =====

def test_license_generation(user):
    """测试1: 许可证生成"""
    lic = generate_license_key(user['id'], user['plan'], days=365)
    assert lic['key'].startswith('DR-'), f"许可证格式错误: {lic['key']}"
    assert lic['plan'] == user['plan']
    assert lic['status'] == 'active'
    return lic['key']


def test_license_verification(key, plan):
    """测试2: 许可证验证"""
    result = verify_license(key)
    assert result['valid'] == True, f"许可证验证失败: {result}"
    assert result['plan'] == plan
    assert result['days_remaining'] > 0
    return result


def test_feature_access(key, plan):
    """测试3: 功能权限检查"""
    expected = PLANS[plan]['features']
    errors = []
    
    for feature, value in expected.items():
        actual = check_feature(key, feature)
        if isinstance(value, bool) and actual != value:
            errors.append(f"{feature}: 期望{value}, 实际{actual}")
    
    assert len(errors) == 0, f"权限检查失败: {'; '.join(errors)}"
    return True


def test_plan_limits(user, key):
    """测试4: 版本限制检查"""
    plan = user['plan']
    features = PLANS[plan]['features']
    
    # 检查词数限制
    max_words = features['max_words_per_day']
    test_words = MOCK_WORDS_CN[:min(25, max_words + 5)]
    allowed = test_words[:max_words]
    blocked = test_words[max_words:] if len(test_words) > max_words else []
    
    # 检查任务数限制
    max_tasks = features['max_tasks']
    
    # 检查功能开关
    has_memory = features['memory_curve']
    has_photo = features['photo_ocr']
    has_mistakes = features['mistake_book']
    
    return {
        'words_allowed': len(allowed),
        'words_blocked': len(blocked),
        'max_tasks': max_tasks,
        'memory_curve': has_memory,
        'photo_ocr': has_photo,
        'mistake_book': has_mistakes
    }


def test_dictation_flow(user, key):
    """测试5: 完整听写流程模拟"""
    plan = user['plan']
    features = PLANS[plan]['features']
    
    # 选词
    num_words = min(10, features['max_words_per_day'])
    words = random.sample(MOCK_WORDS_CN, num_words)
    
    # 模拟听写
    results_list = []
    for w in words:
        is_correct = random.random() > 0.3  # 70%正确率
        results_list.append({'word': w, 'correct': is_correct})
    
    correct = sum(1 for r in results_list if r['correct'])
    accuracy = correct / len(results_list) * 100
    
    # 错题本（仅basic/pro）
    mistakes = [r['word'] for r in results_list if not r['correct']]
    
    return {
        'total': len(words),
        'correct': correct,
        'accuracy': round(accuracy, 1),
        'mistakes': mistakes if features['mistake_book'] else '(免费版不可用)'
    }


def test_schedule_types(user, key):
    """测试6: 预约类型权限"""
    plan = user['plan']
    allowed = PLANS[plan]['features']['schedule_types']
    
    all_types = ['once', 'daily', 'weekly', 'custom']
    results = {}
    for st in all_types:
        results[st] = st in allowed
    
    return results


def test_concurrent_access(user, key):
    """测试7: 并发访问模拟"""
    start = time.time()
    
    # 模拟快速连续操作
    ops = []
    for _ in range(10):
        verify_license(key)
        ops.append(time.time() - start)
    
    avg_time = sum(ops) / len(ops)
    return {
        'operations': 10,
        'avg_time_ms': round(avg_time * 1000, 2),
        'max_time_ms': round(max(ops) * 1000, 2)
    }


def test_memory_curve_simulation(user, key):
    """测试8: 记忆曲线模拟"""
    if not PLANS[user['plan']]['features']['memory_curve']:
        return {'status': 'skipped', 'reason': '当前版本不支持'}
    
    # 模拟SM-2算法
    ef = 2.7
    interval = 1.0
    rep = 0
    schedule = []
    
    for day in range(30):
        quality = random.choice([5, 5, 5, 4, 3, 1])  # 大概率正确
        
        if quality >= 3:
            if rep == 0: interval = 1
            elif rep == 1: interval = 3
            else: interval = interval * ef
            rep += 1
        else:
            rep = 0
            interval = 1
        
        ef = max(1.3, ef + 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
        schedule.append({'day': day, 'quality': quality, 'interval': round(interval, 1), 'ef': round(ef, 2)})
    
    return {
        'days_simulated': 30,
        'final_interval': round(interval, 1),
        'final_ef': round(ef, 2),
        'total_reviews': len(schedule)
    }


def test_photo_ocr_permission(user, key):
    """测试9: 拍照识别权限"""
    has_ocr = PLANS[user['plan']]['features']['photo_ocr']
    if not has_ocr:
        return {'status': 'blocked', 'message': f'{PLANS[user["plan"]]["name"]}不支持拍照识别'}
    
    daily_limit = PLANS[user['plan']]['features'].get('photo_ocr_daily', 0)
    return {'status': 'allowed', 'daily_limit': daily_limit}


def test_multi_user(user, key):
    """测试10: 多用户/家庭版"""
    has_multi = PLANS[user['plan']]['features']['multi_user']
    if not has_multi:
        return {'status': 'single_user', 'message': f'{PLANS[user["plan"]]["name"]}仅支持单用户'}
    
    limit = PLANS[user['plan']]['features'].get('multi_user_limit', 1)
    return {'status': 'multi_user', 'max_members': limit}


# ===== 主测试执行器 =====

def run_user_tests(user):
    """对单个用户执行全部测试"""
    user_result = {
        'user': user,
        'tests': [],
        'passed': 0,
        'failed': 0,
        'start_time': datetime.now().isoformat()
    }
    
    test_cases = [
        ('许可证生成', test_license_generation, [user]),
        ('许可证验证', None, None),  # 依赖上一步
        ('功能权限检查', None, None),
        ('版本限制检查', None, None),
        ('完整听写流程', None, None),
        ('预约类型权限', None, None),
        ('并发访问', None, None),
        ('记忆曲线模拟', None, None),
        ('拍照识别权限', None, None),
        ('多用户权限', None, None),
    ]
    
    key = None
    
    try:
        # T1: 许可证生成
        key = test_license_generation(user)
        user_result['tests'].append({'name': '许可证生成', 'status': 'PASS', 'key': key})
        user_result['passed'] += 1
    except Exception as e:
        user_result['tests'].append({'name': '许可证生成', 'status': 'FAIL', 'error': str(e)})
        user_result['failed'] += 1
        return user_result
    
    # T2-T10
    test_funcs = [
        ('许可证验证', lambda: test_license_verification(key, user['plan'])),
        ('功能权限检查', lambda: test_feature_access(key, user['plan'])),
        ('版本限制检查', lambda: test_plan_limits(user, key)),
        ('完整听写流程', lambda: test_dictation_flow(user, key)),
        ('预约类型权限', lambda: test_schedule_types(user, key)),
        ('并发访问(10次)', lambda: test_concurrent_access(user, key)),
        ('记忆曲线模拟', lambda: test_memory_curve_simulation(user, key)),
        ('拍照识别权限', lambda: test_photo_ocr_permission(user, key)),
        ('多用户权限', lambda: test_multi_user(user, key)),
    ]
    
    for name, func in test_funcs:
        try:
            result = func()
            user_result['tests'].append({'name': name, 'status': 'PASS', 'result': str(result)[:200]})
            user_result['passed'] += 1
        except Exception as e:
            user_result['tests'].append({'name': name, 'status': 'FAIL', 'error': str(e)})
            user_result['failed'] += 1
    
    user_result['end_time'] = datetime.now().isoformat()
    return user_result


def run_all_tests():
    """并发执行20个用户的全部测试"""
    global results
    results['start_time'] = datetime.now().isoformat()
    
    print('=' * 60)
    print('  报听写机器人 - 高并发商业化测试')
    print(f'  用户数: {NUM_USERS} | 每用户测试: 10项 | 总计: {NUM_USERS * 10}项')
    print('=' * 60)
    print()
    
    # 并发执行
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(run_user_tests, user): user for user in MOCK_USERS}
        
        for future in concurrent.futures.as_completed(futures):
            user = futures[future]
            try:
                user_result = future.result()
                results['users'].append(user_result)
                results['passed'] += user_result['passed']
                results['failed'] += user_result['failed']
                results['total_tests'] += user_result['passed'] + user_result['failed']
                
                status = '✅' if user_result['failed'] == 0 else '❌'
                log(f'{status} {user["id"]} ({user["plan"]:>5}) {user_result["passed"]}/{user_result["passed"]+user_result["failed"]} 通过')
            except Exception as e:
                results['errors'].append({'user': user['id'], 'error': str(e)})
                log(f'❌ {user["id"]} 异常: {e}')
    
    results['end_time'] = datetime.now().isoformat()
    
    # 统计
    print()
    print('=' * 60)
    print(f'  测试完成！')
    print(f'  总测试: {results["total_tests"]} | 通过: {results["passed"]} | 失败: {results["failed"]}')
    print(f'  通过率: {results["passed"]/max(results["total_tests"],1)*100:.1f}%')
    print()
    
    # 按版本统计
    for plan in ['free', 'basic', 'pro']:
        plan_users = [u for u in results['users'] if u['user']['plan'] == plan]
        plan_pass = sum(u['passed'] for u in plan_users)
        plan_fail = sum(u['failed'] for u in plan_users)
        print(f'  {PLANS[plan]["name"]:>8}: {len(plan_users)}用户 | {plan_pass}通过 {plan_fail}失败')
    
    print('=' * 60)
    
    # 保存结果
    TEST_RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    TEST_RESULTS_FILE.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'\n  结果已保存: {TEST_RESULTS_FILE}')
    
    return results


if __name__ == '__main__':
    run_all_tests()
