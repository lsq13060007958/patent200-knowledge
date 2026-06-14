#!/usr/bin/env python3
"""
专利法200 + 相关法200 知识点 VLM逐页提取脚本
- MiMo V2.5 vision
- 去水印(扫描全能王)
- 保留颜色标记(蓝/红)
- 表格结构保留
- 增量保存+进度跟踪
"""

import os, sys, json, base64, time, re, traceback
import requests
import fitz  # PyMuPDF

# ==================== 配置 ====================
API_BASE = "https://token-plan-sgp.xiaomimimo.com/v1/chat/completions"
MODEL = "mimo-v2.5"
DPI = 200
MAX_TOKENS = 4000
BATCH_SIZE = 20  # 每20页保存一次+质量检查

# 文件路径
BASE_DIR = "/mnt/h/onedrive/hermes/专利法200知识点_20260614"
EXTRACT_DIR = os.path.join(BASE_DIR, "extracted")
PROGRESS_FILE = os.path.join(BASE_DIR, "progress.json")

PDFS = {
    "专利法": "/mnt/h/微信聊天文件/xwechat_files/lsq837781787_aa17/msg/file/2026-06/临时处理文件夹/专利法200知识点.pdf",
    "相关法": "/mnt/h/微信聊天文件/xwechat_files/lsq837781787_aa17/msg/file/2026-06/临时处理文件夹/相关法200知识点.pdf"
}

# 水印关键词(提取时忽略)
WATERMARK_KEYWORDS = ["扫描全能王", "CS扫描", "3亿人都在用", "CamScanner"]

# ==================== API Key ====================
def get_api_key():
    with open(os.path.expanduser("~/.hermes/.env")) as f:
        for line in f:
            if line.startswith("XIAOMI_API_KEY="):
                return line.strip().split("=", 1)[1]
    raise ValueError("XIAOMI_API_KEY not found")

API_KEY = get_api_key()

# ==================== 工具函数 ====================
def page_to_base64(page, dpi=DPI):
    """PDF页面转base64 PNG"""
    pix = page.get_pixmap(dpi=dpi)
    return base64.b64encode(pix.tobytes("png")).decode()

def update_progress(subject, page, total, status="running", note=""):
    """更新进度文件"""
    progress = {}
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE) as f:
            progress = json.load(f)
    
    progress[subject] = {
        "page": page,
        "total": total,
        "status": status,
        "note": note,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "percent": round(page / total * 100, 1) if total > 0 else 0
    }
    progress["last_update"] = time.strftime("%Y-%m-%d %H:%M:%S")
    
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)

def call_mimo_vision(img_b64, prompt, max_retries=3):
    """调用MiMo V2.5 vision API"""
    headers = {
        "Content-Type": "application/json",
        "api-key": API_KEY
    }
    payload = {
        "model": MODEL,
        "max_tokens": MAX_TOKENS,
        "messages": [{
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{img_b64}"}
                },
                {"type": "text", "text": prompt}
            ]
        }]
    }
    
    for attempt in range(max_retries):
        try:
            resp = requests.post(API_BASE, headers=headers, json=payload, timeout=120)
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                return content
            elif resp.status_code == 429:
                wait = 30 * (attempt + 1)
                print(f"  [限流] 等待{wait}秒后重试...")
                time.sleep(wait)
            else:
                print(f"  [错误] HTTP {resp.status_code}: {resp.text[:200]}")
                time.sleep(10)
        except Exception as e:
            print(f"  [异常] {e}")
            time.sleep(10)
    
    return None

# ==================== 提取Prompt ====================
EXTRACT_PROMPT = """你是专利法考试知识点提取专家。请仔细扫描这一页图片，提取所有内容。

要求：
1. 提取所有知识点的编号、标题和完整正文
2. 保留保留①②③等分点编号和层级结构
3. 【重要】识别彩色标记的文字：
   - 蓝色文字标记的重点，用 [BLUE]...[/BLUE] 包裹
   - 红色文字标记的重点，用 [RED]...[/RED] 包裹
   - 其他颜色用 [COLOR:颜色名]...[/COLOR] 包裹
4. 表格内容用Markdown表格格式输出
5. 忽略页面底部的"扫描全能王"水印和页码
6. 如果是目录页，按原格式列出

输出格式(严格JSON)：
```json
{
  "page_type": "content|cover|toc|blank",
  "title": "章节大标题(如有)",
  "points": [
    {
      "id": "知识点编号(如1、2、3或(1)、(2))",
      "title": "知识点标题",
      "content": "完整正文内容，保留颜色标记标签",
      "sub_points": ["①xxx", "②xxx"]
    }
  ],
  "tables": [
    {
      "headers": ["列1", "列2"],
      "rows": [["值1", "值2"]]
    }
  ],
  "raw_text": "页面完整文字(备用)"
}
```

只输出JSON，不要其他文字。"""

# ==================== 主提取逻辑 ====================
def extract_subject(subject_name, pdf_path):
    """提取单个科目的所有页面"""
    doc = fitz.open(pdf_path)
    total = len(doc)
    print(f"\n{'='*60}")
    print(f"开始提取: {subject_name} ({total}页)")
    print(f"{'='*60}")
    
    all_pages = []
    output_file = os.path.join(EXTRACT_DIR, f"{subject_name}_raw.json")
    
    # 检查已有进度
    start_page = 0
    if os.path.exists(output_file):
        with open(output_file) as f:
            all_pages = json.load(f)
        start_page = len(all_pages)
        print(f"已有{start_page}页数据，从第{start_page+1}页继续")
    
    batch_start = time.time()
    
    for i in range(start_page, total):
        page = doc[i]
        page_num = i + 1
        
        print(f"\n[{subject_name}] 第{page_num}/{total}页 ({round(page_num/total*100,1)}%)", end="", flush=True)
        
        # 转图片
        img_b64 = page_to_base64(page)
        
        # 调用VLM
        t0 = time.time()
        result = call_mimo_vision(img_b64, EXTRACT_PROMPT)
        elapsed = time.time() - t0
        
        if result:
            # 尝试解析JSON
            try:
                # 提取JSON部分(可能被markdown包裹)
                json_match = re.search(r'\{[\s\S]*\}', result)
                if json_match:
                    page_data = json.loads(json_match.group())
                    page_data["page_num"] = page_num
                    page_data["extract_time"] = elapsed
                    all_pages.append(page_data)
                    print(f" ✓ {elapsed:.1f}s", end="")
                    
                    # 统计内容
                    pts = len(page_data.get("points", []))
                    tbls = len(page_data.get("tables", []))
                    print(f" | {pts}个知识点, {tbls}个表格", end="")
                else:
                    # JSON解析失败，保存原始文本
                    all_pages.append({
                        "page_num": page_num,
                        "page_type": "parse_error",
                        "raw_text": result,
                        "extract_time": elapsed
                    })
                    print(f" ⚠ JSON解析失败，保存原始文本", end="")
            except json.JSONDecodeError as e:
                all_pages.append({
                    "page_num": page_num,
                    "page_type": "parse_error",
                    "raw_text": result,
                    "extract_time": elapsed
                })
                print(f" ⚠ JSON解析错误: {str(e)[:50]}", end="")
        else:
            all_pages.append({
                "page_num": page_num,
                "page_type": "api_error",
                "raw_text": "",
                "extract_time": 0
            })
            print(f" ✗ API调用失败", end="")
        
        # 更新进度
        update_progress(subject_name, page_num, total)
        
        # 每BATCH_SIZE页保存+检查
        if page_num % BATCH_SIZE == 0:
            # 保存中间结果
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(all_pages, f, ensure_ascii=False, indent=2)
            
            batch_elapsed = time.time() - batch_start
            print(f"\n  --- 已保存{page_num}页 (本批耗时{batch_elapsed:.0f}s) ---")
            batch_start = time.time()
        
        # 限速: 避免API过载
        time.sleep(1)
    
    # 最终保存
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_pages, f, ensure_ascii=False, indent=2)
    
    doc.close()
    
    # 统计
    success = sum(1 for p in all_pages if p.get("page_type") not in ("api_error", "parse_error"))
    errors = len(all_pages) - success
    
    update_progress(subject_name, total, total, status="completed", 
                   note=f"完成! 成功{success}页, 失败{errors}页")
    
    print(f"\n\n{subject_name}提取完成:")
    print(f"  总页数: {total}")
    print(f"  成功: {success}")
    print(f"  失败: {errors}")
    print(f"  输出: {output_file}")
    
    return all_pages

# ==================== 主程序 ====================
if __name__ == "__main__":
    os.makedirs(EXTRACT_DIR, exist_ok=True)
    
    # 初始化进度
    update_progress("专利法", 0, 105, status="pending")
    update_progress("相关法", 0, 104, status="pending")
    
    subject = sys.argv[1] if len(sys.argv) > 1 else "all"
    
    if subject in ("专利法", "all"):
        extract_subject("专利法", PDFS["专利法"])
    
    if subject in ("相关法", "all"):
        extract_subject("相关法", PDFS["相关法"])
    
    print("\n\n全部提取完成!")
