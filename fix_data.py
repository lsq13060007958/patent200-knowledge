#!/usr/bin/env python3
"""修复数据：将sub_points内容合并到content，过滤空知识点"""
import json, os, re

BASE_DIR = "/mnt/h/onedrive/hermes/专利法200知识点_20260614"
EXTRACT_DIR = os.path.join(BASE_DIR, "extracted")

def clean_content(text):
    if not text:
        return ""
    text = text.replace("[BLUE]", '<span class="key-blue">')
    text = text.replace("[/BLUE]", '</span>')
    text = text.replace("[RED]", '<span class="key-red">')
    text = text.replace("[/RED]", '</span>')
    return text.strip()

def process_point(pt, page_num):
    """处理单个知识点，合并content和sub_points"""
    if not pt:
        return None
    
    title = (pt.get("title") or "").strip()
    content = (pt.get("content") or "").strip()
    sub_points = pt.get("sub_points") or []
    tables = pt.get("tables") or []
    raw_text = (pt.get("raw_text") or "").strip()
    
    # 清理sub_points
    clean_subs = []
    for sp in sub_points:
        if isinstance(sp, str) and sp.strip():
            clean_subs.append(clean_content(sp.strip()))
        elif isinstance(sp, dict):
            clean_subs.append(clean_content(json.dumps(sp, ensure_ascii=False)))
    
    # 如果content为空，尝试从sub_points构建
    if not content and clean_subs:
        # 如果第一个sub_point看起来像正文开头（不是（不是①②③编号）
        first = clean_subs[0]
        if not re.match(r'^[①②③④⑤⑥⑦⑧⑨⑩]', first) and not re.match(r'^\([1-9]', first):
            content = clean_subs[0]
            clean_subs = clean_subs[1:]
    
    # 如果还是空，用raw_text
    if not content and raw_text:
        content = clean_content(raw_text[:500])
    
    # 如果title也是空的，用id或跳过
    if not title:
        title = f"知识点{pt.get('id', page_num)}"
    
    # 过滤完全空的知识点
    if not content and not clean_subs and not tables:
        return None
    
    # 处理表格
    clean_tables = []
    for tbl in tables:
        if isinstance(tbl, dict) and tbl.get("headers"):
            clean_tables.append(tbl)
    
    return {
        "id": pt.get("id", str(page_num)),
        "title": title,
        "content": clean_content(content),
        "sub_points": clean_subs,
        "tables": clean_tables
    }

def is_chapter_title(title):
    """判断是否是章节标题"""
    if not title:
        return False
    return bool(re.match(r'^[一二三四五六七八九十百]+[、.．]', title) or 
                re.match(r'^第[一二三四五六七八九十百]+[章节]', title) or
                re.match(r'^[一二三四五六七八九十]+\s*[、.]', title))

def process_subject(subject):
    raw_file = os.path.join(EXTRACT_DIR, f"{subject}_raw.json")
    with open(raw_file) as f:
        pages = json.load(f)
    
    chapters = []
    current_chapter = {"title": "", "points": []}
    first_chapter = True
    
    for page in pages:
        if page.get("page_type") in ("api_error", "parse_error"):
            continue
        
        page_num = page.get("page_num", 0)
        page_title = (page.get("title") or "").strip()
        
        # 处理所有知识点
        points = []
        for pt in (page.get("points") or []):
            processed = process_point(pt, page_num)
            if processed:
                points.append(processed)
        
        # 处理页面级表格
        for tbl in (page.get("tables") or []):
            if isinstance(tbl, dict) and tbl.get("headers") and points:
                if "tables" not in points[-1]:
                    points[-1]["tables"] = []
                points[-1]["tables"].append(tbl)
        
        if not points:
            continue
        
        # 判断是否开始新章节
        if is_chapter_title(page_title):
            if current_chapter["points"]:
                chapters.append(current_chapter)
            current_chapter = {"title": page_title, "points": []}
            first_chapter = False
        elif first_chapter and not current_chapter["title"]:
            current_chapter["title"] = f"{subject}知识点"
        
        current_chapter["points"].extend(points)
    
    if current_chapter["points"]:
        chapters.append(current_chapter)
    
    # 合并同名章节
    merged = {}
    for ch in chapters:
        key = ch["title"]
        if key in merged:
            merged[key]["points"].extend(ch["points"])
        else:
            merged[key] = ch
    
    chapters = list(merged.values())
    
    # 统计
    total_points = sum(len(ch["points"]) for ch in chapters)
    total_tables = sum(
        len(t) for ch in chapters 
        for p in ch["points"] 
        for t in [p.get("tables", [])]
    )
    
    print(f"\n{subject}:")
    print(f"  章节: {len(chapters)}")
    print(f"  知识点: {total_points}")
    print(f"  表格: {total_tables}")
    for ch in chapters[:5]:
        print(f"    {ch['title'][:30]}: {len(ch['points'])}点")
    if len(chapters) > 5:
        print(f"    ...")
    
    return {"subject": subject, "chapters": chapters}

def main():
    results = {}
    for subject in ["专利法", "相关法"]:
        results[subject] = process_subject(subject)
    
    # 生成JS文件
    for subject, data in results.items():
        js_var = "zl200Data" if subject == "专利法" else "xg200Data"
        prefix = "zl" if subject == "专利法" else "xg"
        js_file = os.path.join(BASE_DIR, f"data_{prefix}200.js")
        with open(js_file, "w", encoding="utf-8") as f:
            f.write(f"const {js_var} = ")
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write(";")
        print(f"\n已生成: {js_file}")
    
    # 读取模板
    template_file = os.path.join(BASE_DIR, "template.html")
    with open(template_file, encoding="utf-8") as f:
        html = f.read()
    
    # 读取数据
    with open(os.path.join(BASE_DIR, "data_zl200.js"), encoding="utf-8") as f:
        zl_js = f.read()
    with open(os.path.join(BASE_DIR, "data_xg200.js"), encoding="utf-8") as f:
        xg_js = f.read()
    
    # 注入数据
    inject_point = html.rfind("</script>")
    if inject_point > 0:
        html = (
            html[:inject_point]
            + "\n// ====== INJECTED DATA ======\n"
            + zl_js + "\n"
            + xg_js + "\n"
            + "// ====== END DATA ======\n"
            + html[inject_point:]
        )
    
    # 替换loadData为同步版本
    old_fn = """async function loadData() {
  // 尝试加载数据文件
  try {
    const [patentResp, relatedResp] = await Promise.all([
      fetch('data_zl200.js').catch(() => null),
      fetch('data_xg200.js').catch(() => null)
    ]);

    if (patentResp && patentResp.ok) {
      const text = await patentResp.text();
      App.data.patent = eval('(' + text.replace(/^.*?=/s, '').replace(/;\\\\s*$/, '') + ')');
    }
    if (relatedResp && relatedResp.ok) {
      const text = await relatedResp.text();
      App.data.related = eval('(' + text.replace(/^.*?=/s, '').replace(/;\\\\s*$/, '') + ')');
    }
  } catch(e) {
    console.log('Data loading:', e);
  }

  // 如果没有数据，显示示例
  if (!App.data.patent && !App.data.related) {
    showDemo();
    return;
  }

  renderContent();
  updateStats();
  buildTOC();
}"""
    
    new_fn = """function loadData() {
  if (typeof zl200Data !== 'undefined') App.data.patent = zl200Data;
  if (typeof xg200Data !== 'undefined') App.data.related = xg200Data;
  if (!App.data.patent && !App.data.related) { showDemo(); return; }
  renderContent();
  updateStats();
  buildTOC();
}"""
    
    html = html.replace(old_fn, new_fn)
    
    # 输出
    output_file = os.path.join(BASE_DIR, "patent200_mobile.html")
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html)
    
    # 同步到index.html
    import shutil
    shutil.copy2(output_file, os.path.join(BASE_DIR, "index.html"))
    
    size = os.path.getsize(output_file) / 1024
    print(f"\n最终文件: {output_file} ({size:.1f}KB)")

if __name__ == "__main__":
    main()
