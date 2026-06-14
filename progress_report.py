#!/usr/bin/env python3
"""
进度汇报脚本 - 供cron job调用
读取progress.json，生成简洁的进度报告
"""
import json, os, time

PROGRESS_FILE = "/mnt/h/onedrive/hermes/专利法200知识点_20260614/progress.json"
EXTRACT_DIR = "/mnt/h/onedrive/hermes/专利法200知识点_20260614/extracted"

def get_report():
    if not os.path.exists(PROGRESS_FILE):
        return "⏳ 提取任务尚未启动"
    
    with open(PROGRESS_FILE) as f:
        progress = json.load(f)
    
    lines = []
    lines.append("📊 专利法200+相关法200 知识点提取进度")
    lines.append("=" * 40)
    
    for subject in ["专利法", "相关法"]:
        if subject in progress:
            p = progress[subject]
            status_icon = {"pending": "⏳", "running": "🔄", "completed": "✅", "error": "❌"}.get(p["status"], "❓")
            
            lines.append(f"\n{status_icon} {subject}:")
            lines.append(f"   进度: {p['page']}/{p['total']}页 ({p['percent']}%)")
            
            if p["status"] == "running":
                # 估算剩余时间
                raw_file = os.path.join(EXTRACT_DIR, f"{subject}_raw.json")
                if os.path.exists(raw_file) and p["page"] > 0:
                    with open(raw_file) as f:
                        pages = json.load(f)
                    if pages:
                        avg_time = sum(pg.get("extract_time", 0) for pg in pages) / len(pages)
                        remaining = (p["total"] - p["page"]) * avg_time
                        lines.append(f"   预计剩余: {remaining/60:.0f}分钟")
            
            if p.get("note"):
                lines.append(f"   备注: {p['note']}")
            lines.append(f"   更新: {p['timestamp']}")
    
    lines.append(f"\n整体更新时间: {progress.get('last_update', 'N/A')}")
    
    return "\n".join(lines)

if __name__ == "__main__":
    print(get_report())
