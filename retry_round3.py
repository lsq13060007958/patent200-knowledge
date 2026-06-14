#!/usr/bin/env python3
"""第三轮重试 - 最大努力模式"""
import os, sys, json, base64, time, re
import requests, fitz

API_BASE = "https://token-plan-sgp.xiaomimimo.com/v1/chat/completions"
MODEL = "mimo-v2.5"
DPI = 200
MAX_TOKENS = 4000
BASE_DIR = "/mnt/h/onedrive/hermes/专利法200知识点_20260614"
EXTRACT_DIR = os.path.join(BASE_DIR, "extracted")

PDFS = {
    "专利法": "/mnt/h/微信聊天文件/xwechat_files/lsq837781787_aa17/msg/file/2026-06/临时处理文件夹/专利法200知识点.pdf",
    "相关法": "/mnt/h/微信聊天文件/xwechat_files/lsq837781787_aa17/msg/file/2026-06/临时处理文件夹/相关法200知识点.pdf"
}

def get_api_key():
    with open(os.path.expanduser("~/.hermes/.env")) as f:
        for line in f:
            if line.startswith("XIAOMI_API_KEY="):
                return line.strip().split("=", 1)[1]
API_KEY = get_api_key()

# 最简prompt - 只要求输出纯文本知识点
SIMPLE_PROMPT = """请提取此页面的所有文字内容。要求：
1. 忽略"扫描全能王"水印和页码
2. 保留原文的编号层级(如1. 2. ①②③)
3. 蓝色标记的文字加[BLUE]前缀，红色标记加[RED]前缀
4. 表格用 | 分隔
5. 直接输出文字内容，不要JSON，不要其他说明"""

def call_mimo(img_b64, prompt, max_retries=5):
    headers = {"Content-Type": "application/json", "api-key": API_KEY}
    payload = {
        "model": MODEL, "max_tokens": MAX_TOKENS,
        "messages": [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
            {"type": "text", "text": prompt}
        ]}]
    }
    for attempt in range(max_retries):
        try:
            resp = requests.post(API_BASE, headers=headers, json=payload, timeout=180)
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"]
            elif resp.status_code == 429:
                time.sleep(90 * (attempt + 1))
            else:
                time.sleep(20)
        except:
            time.sleep(20)
    return None

def retry_subject(subject):
    raw_file = os.path.join(EXTRACT_DIR, f"{subject}_raw.json")
    with open(raw_file) as f:
        pages = json.load(f)
    
    failed_indices = [i for i, p in enumerate(pages) if p.get("page_type") in ("api_error", "parse_error")]
    if not failed_indices:
        print(f"{subject}: 全部成功!")
        return
    
    print(f"\n{'='*50}")
    print(f"第三轮重试 {subject}: {len(failed_indices)}页")
    print(f"{'='*50}")
    
    doc = fitz.open(PDFS[subject])
    fixed = 0
    
    for idx in failed_indices:
        page_num = pages[idx]["page_num"]
        print(f"  第{page_num}页", end="", flush=True)
        
        page = doc[page_num - 1]
        pix = page.get_pixmap(dpi=DPI)
        img_b64 = base64.b64encode(pix.tobytes("png")).decode()
        
        t0 = time.time()
        result = call_mimo(img_b64, SIMPLE_PROMPT)
        elapsed = time.time() - t0
        
        if result and len(result.strip()) > 20:
            # 保存为raw_text类型的content页
            pages[idx] = {
                "page_num": page_num,
                "page_type": "content",
                "title": "",
                "points": [{
                    "id": str(page_num),
                    "title": f"第{page_num}页内容(纯文本提取)",
                    "content": result.replace("\n", "<br>"),
                    "sub_points": []
                }],
                "tables": [],
                "raw_text": result,
                "extract_time": elapsed,
                "note": "round3_simple_extract"
            }
            fixed += 1
            print(f" ✓ {elapsed:.1f}s ({len(result)}字)", flush=True)
        else:
            print(f" ✗", flush=True)
        
        time.sleep(3)
    
    doc.close()
    
    with open(raw_file, "w", encoding="utf-8") as f:
        json.dump(pages, f, ensure_ascii=False, indent=2)
    
    remaining = sum(1 for p in pages if p.get("page_type") in ("api_error", "parse_error"))
    print(f"\n{subject}: 修复{fixed}页, 仍失败{remaining}页")

if __name__ == "__main__":
    subject = sys.argv[1] if len(sys.argv) > 1 else "all"
    if subject in ("专利法", "all"): retry_subject("专利法")
    if subject in ("相关法", "all"): retry_subject("相关法")
    print("\n完成!")
