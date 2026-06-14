#!/usr/bin/env python3
"""
全面修复数据+生成最终HTML
修复项：
1. [BLUE]/[RED]标签 → HTML span
2. 原始JSON内容 → 解析为文字
3. 表格rows统一为数组
4. 编号去重(不要"1. 一、..."这种)
5. 统一两科目的章节结构
"""
import json, os, re

BASE_DIR = "/mnt/h/onedrive/hermes/专利法200知识点_20260614"
EXTRACT_DIR = os.path.join(BASE_DIR, "extracted")

def clean_color_tags(text):
    """修复颜色标记"""
    if not text:
        return ""
    text = text.replace("[BLUE]", '<span class="key-blue">')
    text = text.replace("[/BLUE]", '</span>')
    text = text.replace("[RED]", '<span class="key-red">')
    text = text.replace("[/RED]", '</span>')
    # 修复不完整的标签
    text = re.sub(r'\[BLUE\]([^[]*?)(?=\[|$)', r'<span class="key-blue">\1</span>', text)
    text = re.sub(r'\[RED\]([^[]*?)(?=\[|$)', r'<span class="key-red">\1</span>', text)
    return text.strip()

def is_json_content(text):
    """检测是否是原始JSON内容"""
    if not text:
        return False
    text = text.strip()
    return text.startswith('{') and '"id"' in text and '"title"' in text

def parse_json_content(text):
    """从原始JSON中提取文字内容"""
    try:
        data = json.loads(text)
        parts = []
        if data.get('title'):
            parts.append(data['title'])
        if data.get('content'):
            parts.append(data['content'])
        for sp in data.get('sub_points', []):
            if isinstance(sp, str):
                parts.append(sp)
        return ' '.join(parts)
    except:
        return text

def fix_point(pt, page_num):
    """修复单个知识点"""
    if not pt:
        return None
    
    title = (pt.get('title') or '').strip()
    content = (pt.get('content') or '').strip()
    sub_points = pt.get('sub_points') or []
    tables = pt.get('tables') or []
    
    # 修复：如果content是原始JSON，解析它
    if is_json_content(content):
        content = parse_json_content(content)
    
    # 修复颜色标记
    content = clean_color_tags(content)
    title = clean_color_tags(title)
    
    # 修复sub_points
    clean_subs = []
    for sp in sub_points:
        if isinstance(sp, str):
            sp = sp.strip()
            if is_json_content(sp):
                sp = parse_json_content(sp)
            if sp:
                clean_subs.append(clean_color_tags(sp))
    
    # 修复表格
    clean_tables = []
    for tbl in tables:
        if not isinstance(tbl, dict):
            continue
        headers = tbl.get('headers', [])
        rows = tbl.get('rows', [])
        # 确保rows是数组的数组
        fixed_rows = []
        for row in rows:
            if isinstance(row, list):
                fixed_rows.append(row)
            elif isinstance(row, str):
                fixed_rows.append([row])
            else:
                fixed_rows.append([str(row)])
        if headers or fixed_rows:
            clean_tables.append({'headers': headers, 'rows': fixed_rows})
    
    # 如果content为空，从sub_points提取
    if not content and clean_subs:
        content = clean_subs.pop(0)
    
    # 跳过完全空的知识点
    if not content and not clean_subs and not clean_tables:
        return None
    
    # 修复编号：去掉重复的"一、"等前缀
    # 如果title是"一、xxx"格式，id就不需要再显示"一、"
    point_id = pt.get('id', str(page_num))
    
    return {
        'id': point_id,
        'title': title,
        'content': content,
        'sub_points': clean_subs,
        'tables': clean_tables
    }

def is_chapter_title(title):
    """判断是否是章节标题"""
    if not title:
        return False
    return bool(
        re.match(r'^[一二三四五六七八九十百]+[、.．]', title) or
        re.match(r'^第[一二三四五六七八九十百]+[章节]', title)
    )

def process_subject(subject):
    raw_file = os.path.join(EXTRACT_DIR, f"{subject}_raw.json")
    with open(raw_file) as f:
        pages = json.load(f)
    
    chapters = []
    current = {'title': '', 'points': []}
    
    for page in pages:
        if page.get('page_type') in ('api_error', 'parse_error'):
            continue
        
        page_num = page.get('page_num', 0)
        page_title = (page.get('title') or '').strip()
        
        # 处理知识点
        points = []
        for pt in (page.get('points') or []):
            fixed = fix_point(pt, page_num)
            if fixed:
                points.append(fixed)
        
        if not points:
            continue
        
        # 判断新章节
        if is_chapter_title(page_title):
            if current['points']:
                chapters.append(current)
            current = {'title': page_title, 'points': []}
        
        current['points'].extend(points)
    
    if current['points']:
        chapters.append(current)
    
    # 合并同名章节
    merged = {}
    for ch in chapters:
        key = ch['title']
        if key in merged:
            merged[key]['points'].extend(ch['points'])
        else:
            merged[key] = ch
    chapters = list(merged.values())
    
    # 过滤掉第一个"大杂烩"章节（如果title为空或是通用名）
    if chapters and not chapters[0]['title']:
        chapters[0]['title'] = f'{subject}基础知识'
    
    total = sum(len(c['points']) for c in chapters)
    print(f'{subject}: {len(chapters)}章, {total}知识点')
    
    return {'subject': subject, 'chapters': chapters}

def main():
    results = {}
    for subject in ['专利法', '相关法']:
        results[subject] = process_subject(subject)
    
    # 读取模板
    with open(os.path.join(BASE_DIR, 'template.html'), encoding='utf-8') as f:
        template = f.read()
    
    # 提取JSON数据
    zl_json = json.dumps(results['专利法'], ensure_ascii=False)
    xg_json = json.dumps(results['相关法'], ensure_ascii=False)
    
    # 在</script>之前注入数据
    inject = template.rfind('</script>')
    
    new_html = (
        template[:inject]
        + '\nvar zl200Data = ' + zl_json + ';\n'
        + 'var xg200Data = ' + xg_json + ';\n'
        + '''
function loadData() {
  App.data.patent = zl200Data;
  App.data.related = xg200Data;
  renderContent();
  updateStats();
  buildTOC();
}
'''
        + template[inject:]
    )
    
    # 移除模板中的async loadData
    new_html = re.sub(
        r'async function loadData\(\)\s*\{.*?\n\}',
        '',
        new_html,
        flags=re.DOTALL
    )
    
    # 修复render函数中的表格rows问题
    old_tbl = 't.rows.forEach(function(r) {\n            html += "<tr>" + r.map'
    new_tbl = '(t.rows||[]).forEach(function(r) {\n            var cells = Array.isArray(r) ? r : [r];\n            html += "<tr>" + cells.map'
    new_html = new_html.replace(old_tbl, new_tbl)
    
    # 写入文件
    output = os.path.join(BASE_DIR, 'index.html')
    with open(output, 'w', encoding='utf-8') as f:
        f.write(new_html)
    
    size = os.path.getsize(output) / 1024
    print(f'\nindex.html: {size:.0f}KB')
    
    # 验证
    check_zl = re.search(r'var zl200Data = (\{.*?\});', new_html, re.DOTALL)
    check_xg = re.search(r'var xg200Data = (\{.*?\});', new_html, re.DOTALL)
    print(f'zl200Data: {"✓" if check_zl else "✗"}')
    print(f'xg200Data: {"✓" if check_xg else "✗"}')
    
    if 'async function loadData' in new_html:
        print('⚠ 仍有async loadData')
    elif 'function loadData()' in new_html:
        print('✓ loadData: 同步版本')

if __name__ == '__main__':
    main()
