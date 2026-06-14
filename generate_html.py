#!/usr/bin/env python3
"""
将提取的原始JSON数据转换为HTML模板所需的格式
并生成最终的自包含HTML文件
"""
import json, os, re

BASE_DIR = "/mnt/h/onedrive/hermes/专利法200知识点_20260614"
EXTRACT_DIR = os.path.join(BASE_DIR, "extracted")
TEMPLATE_FILE = os.path.join(BASE_DIR, "template.html")
OUTPUT_FILE = os.path.join(BASE_DIR, "patent200_mobile.html")

def clean_content(text):
    """清理内容，处理颜色标记"""
    if not text:
        return ""
    # 确保HTML标签正确
    text = text.replace("[BLUE]", '<span class="key-blue">')
    text = text.replace("[/BLUE]", '</span>')
    text = text.replace("[RED]", '<span class="key-red">')
    text = text.replace("[/RED]", '</span>')
    # 清理多余的空白
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text

def process_raw_data(subject, raw_pages):
    """将原始页面数据转换为章节结构"""
    chapters = []
    current_chapter = None
    
    for page in raw_pages:
        if page.get("page_type") in ("api_error", "parse_error"):
            continue
        
        page_num = page.get("page_num", 0)
        
        # 检查是否有大标题(通常是新章节)
        title = page.get("title", "")
        
        # 处理知识点
        points = []
        for pt in page.get("points", []):
            if not pt:
                continue
            
            point = {
                "id": pt.get("id", str(page_num)),
                "title": pt.get("title", ""),
                "content": clean_content(pt.get("content", "")),
                "sub_points": []
            }
            
            # 处理子点
            for sp in pt.get("sub_points", []):
                if isinstance(sp, str):
                    point["sub_points"].append(clean_content(sp))
                elif isinstance(sp, dict):
                    point["sub_points"].append(clean_content(json.dumps(sp, ensure_ascii=False)))
            
            # 处理表格
            point["tables"] = []
            for tbl in pt.get("tables", []):
                if isinstance(tbl, dict):
                    point["tables"].append(tbl)
            
            points.append(point)
        
        # 如果页面有表格但不在points中
        for tbl in page.get("tables", []):
            if isinstance(tbl, dict) and points:
                # 将页面级表格附加到最后一个知识点
                if "tables" not in points[-1]:
                    points[-1]["tables"] = []
                points[-1]["tables"].append(tbl)
        
        if not points:
            continue
        
        # 判断是否是新章节
        # 策略：如果页面有大标题且不以数字开头，可能是新章节
        is_new_chapter = False
        if title:
            # 检查是否是章节标题格式（如"一、" "二、" 或 "第X章"）
            if re.match(r'^[一二三四五六七八九十]+[、.]', title) or re.match(r'^第[一二三四五六七八九十百]+[章节]', title):
                is_new_chapter = True
        
        if is_new_chapter or current_chapter is None:
            if current_chapter is None:
                current_chapter = {"title": f"{subject}知识点", "points": []}
            if is_new_chapter and current_chapter["points"]:
                chapters.append(current_chapter)
                current_chapter = {"title": title, "points": []}
            elif title and not current_chapter["title"]:
                current_chapter["title"] = title
        
        current_chapter["points"].extend(points)
    
    if current_chapter and current_chapter["points"]:
        chapters.append(current_chapter)
    
    return {"subject": subject, "chapters": chapters}

def main():
    # 加载原始数据
    data = {}
    for subject in ["专利法", "相关法"]:
        raw_file = os.path.join(EXTRACT_DIR, f"{subject}_raw.json")
        if os.path.exists(raw_file):
            with open(raw_file) as f:
                raw_pages = json.load(f)
            data[subject] = process_raw_data(subject, raw_pages)
            stats = data[subject]
            total_points = sum(len(ch["points"]) for ch in stats["chapters"])
            total_tables = sum(
                len(t.get("tables", []))
                for ch in stats["chapters"]
                for t in ch["points"]
            )
            print(f"{subject}: {len(stats['chapters'])}章节, {total_points}知识点, {total_tables}表格")
    
    # 生成JS数据文件
    for subject, subject_data in data.items():
        js_var = "zl200Data" if subject == "专利法" else "xg200Data"
        js_file = os.path.join(BASE_DIR, f"data_{'zl' if subject == '专利法' else 'xg'}200.js")
        with open(js_file, "w", encoding="utf-8") as f:
            f.write(f"const {js_var} = ")
            json.dump(subject_data, f, ensure_ascii=False, indent=2)
            f.write(";")
        print(f"已生成: {js_file}")
    
    # 读取HTML模板
    with open(TEMPLATE_FILE, encoding="utf-8") as f:
        html = f.read()
    
    # 读取JS数据
    with open(os.path.join(BASE_DIR, "data_zl200.js"), encoding="utf-8") as f:
        zl_js = f.read()
    with open(os.path.join(BASE_DIR, "data_xg200.js"), encoding="utf-8") as f:
        xg_js = f.read()
    
    # 注入数据到HTML
    # 在</script>之前插入数据
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
    
    # 修改loadData函数以使用内嵌数据
    old_load = """async function loadData() {
  // 尝试加载数据文件
  try {
    const [patentResp, relatedResp] = await Promise.all([
      fetch('data_zl200.js').catch(() => null),
      fetch('data_xg200.js').catch(() => null)
    ]);

    if (patentResp && patentResp.ok) {
      const text = await patentResp.text();
      App.data.patent = eval('(' + text.replace(/^.*?=/s, '').replace(/;\\s*$/, '') + ')');
    }
    if (relatedResp && relatedResp.ok) {
      const text = await relatedResp.text();
      App.data.related = eval('(' + text.replace(/^.*?=/s, '').replace(/;\\s*$/, '') + ')');
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
    
    new_load = """function loadData() {
  // 使用内嵌数据
  if (typeof zl200Data !== 'undefined') {
    App.data.patent = zl200Data;
  }
  if (typeof xg200Data !== 'undefined') {
    App.data.related = xg200Data;
  }

  if (!App.data.patent && !App.data.related) {
    showDemo();
    return;
  }

  renderContent();
  updateStats();
  buildTOC();
}"""
    
    html = html.replace(old_load, new_load)
    
    # 写入最终文件
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    
    file_size = os.path.getsize(OUTPUT_FILE) / 1024
    print(f"\n最终文件: {OUTPUT_FILE}")
    print(f"文件大小: {file_size:.1f} KB")

if __name__ == "__main__":
    main()
