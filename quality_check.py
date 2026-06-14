#!/usr/bin/env python3
"""
质量检查脚本 - 每20页用LLM检查语言问题
运行方式: python3 quality_check.py [专利法|相关法]
"""

import os, sys, json, re, time
import requests

BASE_DIR = "/mnt/h/onedrive/hermes/专利法200知识点_20260614"
EXTRACT_DIR = os.path.join(BASE_DIR, "extracted")
CHECK_DIR = os.path.join(BASE_DIR, "quality_checks")

# MiMo API配置
def get_api_key():
    with open(os.path.expanduser("~/.hermes/.env")) as f:
        for line in f:
            if line.startswith("XIAOMI_API_KEY="):
                return line.strip().split("=", 1)[1]
    raise ValueError("XIAOMI_API_KEY not found")

API_KEY = get_api_key()
API_BASE = "https://token-plan-sgp.xiaomimimo.com/v1/chat/completions"
MODEL = "mimo-v2.5"

CHECK_PROMPT = """你是专利法考试知识点质量检查专家。请检查以下提取的知识点内容，找出问题：

检查项：
1. 语言不通顺、断句不合理
2. 法律术语错误或不规范
3. 编号/层级混乱
4. 内容重复或遗漏
5. 颜色标记标签([BLUE][/BLUE]等)是否合理
6. 表格格式是否正确

对每个问题，请给出：
- 问题类型
- 问题描述
- 原文位置
- 建议修改

如果没有问题，返回"未发现质量问题"。

请用JSON格式输出：
```json
{
  "batch": "第X-Y页",
  "total_checked": N,
  "issues": [
    {
      "page": 页码,
      "type": "问题类型",
      "description": "问题描述",
      "location": "原文位置",
      "suggestion": "建议修改"
    }
  ],
  "summary": "总体评价"
}
```"""

def call_mimo_text(prompt, max_tokens=2000):
    """调用MiMo文本API"""
    headers = {"Content-Type": "application/json", "api-key": API_KEY}
    payload = {
        "model": MODEL,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}]
    }
    try:
        resp = requests.post(API_BASE, headers=headers, json=payload, timeout=120)
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"  API错误: {e}")
    return None

def check_batch(subject, pages, batch_start, batch_end):
    """检查一批页面"""
    # 构建检查内容
    content_parts = []
    for p in pages:
        if p.get("page_type") in ("content",):
            page_text = f"--- 第{p['page_num']}页 ---\n"
            for pt in p.get("points", []):
                page_text += f"{pt.get('id', '')} {pt.get('title', '')}\n"
                page_text += f"{pt.get('content', '')}\n"
                for sp in pt.get("sub_points", []):
                    page_text += f"  {sp}\n"
            for tbl in p.get("tables", []):
                page_text += "表格:\n"
                if tbl.get("headers"):
                    page_text += " | ".join(tbl["headers"]) + "\n"
                for row in tbl.get("rows", []):
                    page_text += " | ".join(row) + "\n"
            content_parts.append(page_text)
    
    if not content_parts:
        return None
    
    full_content = "\n".join(content_parts)
    prompt = CHECK_PROMPT + f"\n\n以下是{subject}第{batch_start}-{batch_end}页的提取内容：\n\n{full_content}"
    
    print(f"  正在检查{subject}第{batch_start}-{batch_end}页...")
    result = call_mimo_text(prompt)
    
    if result:
        try:
            json_match = re.search(r'\{[\s\S]*\}', result)
            if json_match:
                check_result = json.loads(json_match.group())
                return check_result
        except json.JSONDecodeError:
            pass
    
    return {"batch": f"第{batch_start}-{batch_end}页", "issues": [], "summary": result or "检查失败"}

def run_quality_check(subject):
    """对单个科目执行质量检查"""
    raw_file = os.path.join(EXTRACT_DIR, f"{subject}_raw.json")
    if not os.path.exists(raw_file):
        print(f"未找到{subject}的提取数据")
        return
    
    with open(raw_file) as f:
        all_pages = json.load(f)
    
    total = len(all_pages)
    print(f"\n{subject}质量检查: 共{total}页")
    
    os.makedirs(CHECK_DIR, exist_ok=True)
    all_checks = []
    
    # 每20页检查一次
    for start in range(0, total, 20):
        end = min(start + 20, total)
        batch = all_pages[start:end]
        
        check_result = check_batch(subject, batch, start + 1, end)
        if check_result:
            all_checks.append(check_result)
            issues = len(check_result.get("issues", []))
            print(f"  第{start+1}-{end}页: {issues}个问题")
        
        time.sleep(2)  # 限速
    
    # 保存检查结果
    output_file = os.path.join(CHECK_DIR, f"{subject}_quality.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_checks, f, ensure_ascii=False, indent=2)
    
    # 统计
    total_issues = sum(len(c.get("issues", [])) for c in all_checks)
    print(f"\n{subject}质量检查完成:")
    print(f"  检查批次数: {len(all_checks)}")
    print(f"  发现问题数: {total_issues}")
    print(f"  输出: {output_file}")

if __name__ == "__main__":
    subject = sys.argv[1] if len(sys.argv) > 1 else "all"
    
    if subject in ("专利法", "all"):
        run_quality_check("专利法")
    
    if subject in ("相关法", "all"):
        run_quality_check("相关法")
    
    print("\n质量检查全部完成!")
