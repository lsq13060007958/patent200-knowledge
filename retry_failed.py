#!/usr/bin/env python3
"""
重试失败页面提取 - 更健壮的JSON解析+更长等待
"""
import os, sys, json, base64, time, re
import requests
import fitz

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
    raise ValueError("XIAOMI_API_KEY not found")

API_KEY = get_api_key()

# 更简洁的prompt，减少JSON格式错误
RETRY_PROMPT = """提取此页所有知识点。忽略水印和页码。

对蓝色标记文字用[BLUE]...[/BLUE]，红色标记用[RED]...[/RED]。
表格用Markdown格式。

严格输出以下JSON(不要多余文字):
{"page_type":"content","title":"大标题","points":[{"id":"1","title":"标题","content":"正文","sub_points":["①xxx"]}],"tables":[{"headers":["列"],"rows":["值"]}]}

注意: 
- 字符串内的双引号用转义\"
- 确保JSON格式正确
- 如果没有表格: "tables":[]
- 如果没有子点: "sub_points":[]"""

def call_mimo(img_b64, prompt, max_retries=5):
    headers = {"Content-Type": "application/json", "api-key": API_KEY}
    payload = {
        "model": MODEL,
        "max_tokens": MAX_TOKENS,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
                {"type": "text", "text": prompt}
            ]
        }]
    }
    
    for attempt in range(max_retries):
        try:
            resp = requests.post(API_BASE, headers=headers, json=payload, timeout=180)
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"]
            elif resp.status_code == 429:
                wait = 60 * (attempt + 1)
                print(f"    [限流] 等待{wait}s...", flush=True)
                time.sleep(wait)
            else:
                print(f"    [HTTP {resp.status_code}]", flush=True)
                time.sleep(15)
        except Exception as e:
            print(f"    [异常] {str(e)[:60]}", flush=True)
            time.sleep(15)
    return None

def parse_json_robust(text):
    """更健壮的JSON解析"""
    if not text:
        return None
    
    # 提取JSON块
    json_match = re.search(r'\{[\s\S]*\}', text)
    if not json_match:
        return None
    
    raw = json_match.group()
    
    # 尝试直接解析
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    
    # 修复常见问题
    fixed = raw
    # 修复未转义的引号
    fixed = re.sub(r'(?<!\\)"(?=[^:,\[\]{}\s])', '\\"', fixed)
    # 修复尾部逗号
    fixed = re.sub(r',\s*([}\]])', r'\1', fixed)
    # 修复单引号
    fixed = fixed.replace("'", '"')
    
    try:
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass
    
    # 最后手段: 用eval(不安全但作为fallback)
    try:
        import ast
        return ast.literal_eval(raw)
    except:
        pass
    
    return None

def retry_subject(subject):
    raw_file = os.path.join(EXTRACT_DIR, f"{subject}_raw.json")
    with open(raw_file) as f:
        pages = json.load(f)
    
    failed_indices = [i for i, p in enumerate(pages) 
                      if p.get("page_type") in ("api_error", "parse_error")]
    
    if not failed_indices:
        print(f"{subject}: 没有失败页面!")
        return
    
    print(f"\n{'='*50}")
    print(f"重试 {subject}: {len(failed_indices)}个失败页面")
    print(f"页面: {[pages[i]['page_num'] for i in failed_indices]}")
    print(f"{'='*50}")
    
    doc = fitz.open(PDFS[subject])
    retried = 0
    fixed = 0
    
    for idx in failed_indices:
        page_num = pages[idx]["page_num"]
        page_idx = page_num - 1
        
        print(f"\n  [{subject}] 重试第{page_num}页 ({retried+1}/{len(failed_indices)})", end="", flush=True)
        
        page = doc[page_idx]
        pix = page.get_pixmap(dpi=DPI)
        img_b64 = base64.b64encode(pix.tobytes("png")).decode()
        
        t0 = time.time()
        result = call_mimo(img_b64, RETRY_PROMPT)
        elapsed = time.time() - t0
        
        if result:
            parsed = parse_json_robust(result)
            if parsed:
                parsed["page_num"] = page_num
                parsed["extract_time"] = elapsed
                pages[idx] = parsed
                fixed += 1
                pts = len(parsed.get("points") or [])
                tbls = len(parsed.get("tables") or [])
                print(f" ✓ {elapsed:.1f}s | {pts}个知识点, {tbls}个表格", end="")
            else:
                # 保存原始文本
                pages[idx] = {
                    "page_num": page_num,
                    "page_type": "parse_error",
                    "raw_text": result,
                    "extract_time": elapsed
                }
                print(f" ⚠ 解析仍失败", end="")
        else:
            print(f" ✗ API仍失败", end="")
        
        retried += 1
        
        # 每10页保存
        if retried % 10 == 0:
            with open(raw_file, "w", encoding="utf-8") as f:
                json.dump(pages, f, ensure_ascii=False, indent=2)
            print(f"\n  --- 已保存 ---", end="")
        
        time.sleep(2)
    
    doc.close()
    
    # 最终保存
    with open(raw_file, "w", encoding="utf-8") as f:
        json.dump(pages, f, ensure_ascii=False, indent=2)
    
    # 统计
    remaining = sum(1 for p in pages if p.get("page_type") in ("api_error", "parse_error"))
    print(f"\n\n{subject}重试完成:")
    print(f"  重试: {retried}页")
    print(f"  修复: {fixed}页")
    print(f"  仍失败: {remaining}页")

if __name__ == "__main__":
    subject = sys.argv[1] if len(sys.argv) > 1 else "all"
    
    if subject in ("专利法", "all"):
        retry_subject("专利法")
    if subject in ("相关法", "all"):
        retry_subject("相关法")
    
    print("\n\n重试全部完成!")
