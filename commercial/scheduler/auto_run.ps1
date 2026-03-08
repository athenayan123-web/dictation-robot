# -*- coding: utf-8 -*-
"""
自动化调度器 - 一周内自动执行商业化任务
每日开机自动运行，生成进度报告
"""
import json
import time
import random
from datetime import datetime, timedelta
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from dashboard.progress import generate_daily_report, print_report

COMMERCIAL_DIR = Path(__file__).parent.parent
LOGS_DIR = COMMERCIAL_DIR / 'logs'
SCHEDULER_DIR = Path(__file__).parent
STATUS_FILE = SCHEDULER_DIR / 'scheduler_status.json'


def check_should_run():
    """检查今天是否应该运行"""
    if not STATUS_FILE.exists():
        return True
    
    status = json.loads(STATUS_FILE.read_text(encoding='utf-8'))
    last_run = datetime.fromisoformat(status.get('last_run', '2000-01-01'))
    
    # 每天只运行一次
    if last_run.date() == datetime.now().date():
        print(f'[{datetime.now().strftime("%H:%M")}] 今日已运行，跳过')
        return False
    
    return True


def update_status(report):
    """更新调度器状态"""
    status = {
        'last_run': datetime.now().isoformat(),
        'day': report['day'],
        'overall_progress': report['overall_progress'],
        'today_progress': report['today_progress']
    }
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATUS_FILE.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding='utf-8')


def show_popup_notification(report):
    """Windows弹窗通知"""
    try:
        import ctypes
        title = f"报听写机器人商业化 - Day {report['day']}/7"
        message = f"今日进度: {report['today_progress']}%\n整体进度: {report['overall_progress']}%\n{report['title']}"
        ctypes.windll.user32.MessageBoxW(0, message, title, 0x40 | 0x0)
    except:
        pass


def main():
    """主调度循环"""
    print('=' * 60)
    print('  🤖 报听写机器人商业化自动调度器')
    print(f'  ⏰ 启动时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print('=' * 60)
    print()
    
    if not check_should_run():
        # 显示今日已完成的报告
        today_file = LOGS_DIR / f'daily_report_{datetime.now().strftime("%Y%m%d")}.json'
        if today_file.exists():
            report = json.loads(today_file.read_text(encoding='utf-8'))
            print_report(report)
        return
    
    # 生成并显示报告
    report = generate_daily_report()
    print_report(report)
    
    # 更新状态
    update_status(report)
    
    # 弹窗通知
    show_popup_notification(report)
    
    print()
    print('✅ 今日任务调度完成')
    print(f'📄 报告已保存: {LOGS_DIR}')
    print()
    
    # 如果是最后一天，提示项目完成
    if report['day'] >= 7:
        print('🎉🎉🎉 商业化项目全部完成！准备发布！🎉🎉🎉')


if __name__ == '__main__':
    main()
    input('按Enter键退出...')
