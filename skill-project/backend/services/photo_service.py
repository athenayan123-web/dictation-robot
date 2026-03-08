# -*- coding: utf-8 -*-
"""
拍照识别服务 - 调用LLM视觉大模型
"""
import json
import base64
import requests
from pathlib import Path
from backend.config import load_api_key, load_config


def recognize_image(image_path: str = None, image_base64: str = None, 
                    mime_type: str = 'image/jpeg', prompt: str = None) -> dict:
    """
    调用LLM视觉模型识别图片中的文字
    
    Returns:
        {success, raw_text, words, word_count, model}
    """
    api_key = load_api_key()
    if not api_key:
        return {'success': False, 'error': 'no_api_key', 'message': '未配置API Key'}
    
    cfg = load_config()
    base_url = cfg.get('llm_base_url', 'https://api.stepfun.com/v1')
    model = cfg.get('llm_model', 'step-1v-8k')
    
    # 读取图片
    if image_path and not image_base64:
        with open(image_path, 'rb') as f:
            image_base64 = base64.b64encode(f.read()).decode('ascii')
    
    if not image_base64:
        return {'success': False, 'error': '缺少图片数据'}
    
    # 构建请求
    default_prompt = (
        '请精确识别图片中的所有中文词语。'
        '如果是词语表、生字表或听写内容，请每个词语单独一行输出。'
        '不要加序号、标点和额外解释。只输出词语本身。'
    )
    
    payload = {
        'model': model,
        'messages': [
            {
                'role': 'system',
                'content': '你是专业的OCR文字识别助手，精确识别图片中的汉字和词语。'
            },
            {
                'role': 'user',
                'content': [
                    {'type': 'text', 'text': prompt or default_prompt},
                    {'type': 'image_url', 'image_url': {
                        'url': f'data:{mime_type};base64,{image_base64}'
                    }}
                ]
            }
        ],
        'temperature': 0.1,
        'max_tokens': 4096
    }
    
    try:
        resp = requests.post(
            f'{base_url}/chat/completions',
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {api_key}'
            },
            json=payload,
            timeout=60
        )
        resp.raise_for_status()
        data = resp.json()
        
        raw_text = data.get('choices', [{}])[0].get('message', {}).get('content', '')
        
        # 解析词汇
        words = [
            w.strip().lstrip('0123456789.、-） ')
            for w in raw_text.split('\n')
            if w.strip() and len(w.strip()) < 30 and not w.strip().startswith('#')
        ]
        words = [w for w in words if w]  # 去空
        
        return {
            'success': True,
            'raw_text': raw_text,
            'words': words,
            'word_count': len(words),
            'model': model
        }
    
    except requests.exceptions.Timeout:
        return {'success': False, 'error': 'LLM请求超时（60秒）'}
    except requests.exceptions.RequestException as e:
        return {'success': False, 'error': f'LLM请求失败: {str(e)}'}
    except Exception as e:
        return {'success': False, 'error': f'识别失败: {str(e)}'}
