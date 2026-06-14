#!/usr/bin/env python3
"""
全面重建：数据清洗 + 模板修复 + HTML生成
"""
import json, os, re

BASE_DIR = "/mnt/h/onedrive/hermes/专利法200知识点_20260614"
EXTRACT_DIR = os.path.join(BASE_DIR, "extracted")

def clean_tags(text):
    """清理颜色标签"""
    if not text:
        return ""
    # 标准转换
    text = text.replace("[BLUE]", '<span class="key-blue">')
    text = text.replace("[/BLUE]", '</span>')
    text = text.replace("[RED]", '<span class="key-red">')
    text = text.replace("[/RED]", '</span>')
    # 修复残留的未闭合标签
    text = re.sub(r'\[BLUE\]([^[\]]*?)(?=\[|$)', r'<span class="key-blue">\1</span>', text)
    text = re.sub(r'\[RED\]([^[\]]*?)(?=\[|$)', r'<span class="key-red">\1</span>', text)
    # 修复嵌套错误的span
    text = re.sub(r'<span class="key-red"><span class="key-red">', '<span class="key-red">', text)
    text = re.sub(r'</span></span></span>', '</span></span>', text)
    return text.strip()

def is_page_ref(text):
    """检测是否只是页码引用"""
    if not text:
        return True
    text = text.strip()
    if re.match(r'^第?\d+页?$', text):
        return True
    if re.match(r'^\d+$', text) and len(text) <= 3:
        return True
    return False

def is_raw_json(text):
    """检测是否是未解析的JSON"""
    if not text:
        return False
    text = text.strip()
    return (text.startswith('{') and '"id"' in text and '"title"' in text)

def extract_from_json(text):
    """从原始JSON中提取有意义的内容"""
    try:
        data = json.loads(text)
        parts = []
        if data.get('content') and not is_page_ref(data['content']):
            parts.append(clean_tags(data['content']))
        for sp in data.get('sub_points', []):
            if isinstance(sp, str) and sp.strip() and not is_page_ref(sp):
                parts.append(clean_tags(sp))
        return ' '.join(parts) if parts else ''
    except:
        return clean_tags(text)

def fix_tables(tables):
    """修复表格数据"""
    result = []
    for tbl in tables:
        if not isinstance(tbl, dict):
            continue
        headers = tbl.get('headers', [])
        rows = tbl.get('rows', [])
        fixed_rows = []
        for row in rows:
            if isinstance(row, list):
                fixed_rows.append([clean_tags(str(c)) for c in row])
            elif isinstance(row, str):
                # 尝试按|分割
                cells = [c.strip() for c in row.split('|') if c.strip()]
                if cells:
                    fixed_rows.append([clean_tags(c) for c in cells])
                else:
                    fixed_rows.append([clean_tags(row)])
        if headers or fixed_rows:
            result.append({'headers': headers, 'rows': fixed_rows})
    return result

def fix_point(pt, page_num):
    """修复单个知识点"""
    if not pt:
        return None
    
    title = clean_tags((pt.get('title') or '').strip())
    content = (pt.get('content') or '').strip()
    sub_points = pt.get('sub_points') or []
    tables = pt.get('tables') or []
    
    # 处理content
    if is_raw_json(content):
        content = extract_from_json(content)
    elif is_page_ref(content):
        content = ''
    else:
        content = clean_tags(content)
    
    # 处理sub_points
    clean_subs = []
    for sp in sub_points:
        if isinstance(sp, dict):
            sp_text = json.dumps(sp, ensure_ascii=False)
            if is_raw_json(sp_text):
                sp_text = extract_from_json(sp_text)
            else:
                sp_text = clean_tags(str(sp))
        else:
            sp_text = str(sp).strip()
            if is_raw_json(sp_text):
                sp_text = extract_from_json(sp_text)
            else:
                sp_text = clean_tags(sp_text)
        
        if sp_text and not is_page_ref(sp_text):
            clean_subs.append(sp_text)
    
    # 修复表格
    clean_tables = fix_tables(tables)
    
    # 如果content为空，从sub_points提取第一个作为content
    if not content and clean_subs:
        content = clean_subs.pop(0)
    
    # 跳过完全空的知识点
    if not content and not clean_subs and not clean_tables:
        return None
    
    # 修复title：去掉重复的编号前缀
    # 如果id是"1"而title是"一、xxx"，去掉title中的"一、"
    point_id = pt.get('id', str(page_num))
    # 不做这个修改，保留原始title
    
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
    has_real_content = False
    
    for page in pages:
        if page.get('page_type') in ('api_error', 'parse_error'):
            continue
        
        page_num = page.get('page_num', 0)
        page_title = (page.get('title') or '').strip()
        
        points = []
        for pt in (page.get('points') or []):
            fixed = fix_point(pt, page_num)
            if fixed:
                points.append(fixed)
                if fixed['content'] and not is_page_ref(fixed['content']):
                    has_real_content = True
        
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
    
    # 设置第一个章节标题
    if chapters:
        if not chapters[0]['title']:
            # 检查第一个知识点是否是章节标题
            if chapters[0]['points'] and is_chapter_title(chapters[0]['points'][0].get('title', '')):
                chapters[0]['title'] = chapters[0]['points'][0]['title']
                chapters[0]['points'] = chapters[0]['points'][1:]
            else:
                chapters[0]['title'] = f'{subject}基础知识'
    
    # 过滤掉只有页码引用的章节
    chapters = [ch for ch in chapters if any(
        p['content'] and not is_page_ref(p['content']) 
        for p in ch['points']
    )]
    
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
    
    zl_json = json.dumps(results['专利法'], ensure_ascii=False)
    xg_json = json.dumps(results['相关法'], ensure_ascii=False)
    
    # 在</script>之前注入数据和loadData
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
    
    # 修复renderContent中的表格rows处理
    old_rows = 'tbl.rows.forEach(row => {\n            html += `<tr>`;\n            row.forEach(cell => html += `<td>${cell}</td>`);'
    new_rows = '(tbl.rows||[]).forEach(row => {\n            html += `<tr>`;\n            var cells = Array.isArray(row) ? row : [row];\n            cells.forEach(cell => html += `<td>${cell}</td>`);'
    new_html = new_html.replace(old_rows, new_rows)
    
    # 写入
    output = os.path.join(BASE_DIR, 'index.html')
    with open(output, 'w', encoding='utf-8') as f:
        f.write(new_html)
    
    size = os.path.getsize(output) / 1024
    print(f'\nindex.html: {size:.0f}KB')

if __name__ == '__main__':
    main()
