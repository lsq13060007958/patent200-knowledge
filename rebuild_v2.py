#!/usr/bin/env python3
"""
根据PDF实际目录，按页码重新分配知识点到正确章节
"""
import json, os, re

BASE_DIR = "/mnt/h/onedrive/hermes/专利法200知识点_20260614"
EXTRACT_DIR = os.path.join(BASE_DIR, "extracted")

# ==================== 专利法目录 ====================
# (章节名, 起始页, 结束页)
ZL_CHAPTERS = [
    ("一、专利法基础知识与权利归属", 1, 1),
    ("二、专利代理制度", 2, 4),
    ("三、说明书", 5, 7),
    ("四、权利要求", 8, 10),
    ("五、专利保护的对象和主题", 11, 17),
    ("六、新颖性", 18, 19),
    ("七、不丧失新颖性的宽限期", 20, 20),
    ("八、同样的发明创造", 21, 21),
    ("九、创造性", 22, 22),
    ("十、单一性", 23, 23),
    ("十一、专利申请的受理和初步审查", 24, 26),
    ("十二、对请求书的初步审查", 27, 27),
    ("十三、对委托书的初步审查", 27, 27),
    ("十四、对著录项目变更申报书的初步审查", 28, 28),
    ("十五、优先权", 29, 30),
    ("十六、对分案申请的审查", 31, 31),
    ("十七、对涉及生物材料的申请的审查", 32, 32),
    ("十八、对涉及遗传资源的申请的审查", 33, 33),
    ("十九、实质审查", 34, 36),
    ("二十、期限", 37, 38),
    ("二十一、费用", 39, 39),
    ("二十二、专利权的授予", 40, 40),
    ("二十三、专利申请撤回、专利权的放弃和终止", 41, 41),
    ("二十四、专利权的中止", 41, 41),
    ("二十五、通知和决定的送达", 42, 42),
    ("二十六、优先审查、延迟审查和快速审查", 43, 43),
    ("二十七、保密专利和保密审查", 43, 43),
    ("二十八、非正常专利申请", 44, 44),
    ("二十九、专利权评价报告", 44, 44),
    ("三十、复审无效总则", 45, 45),
    ("三十一、复审程序", 46, 48),
    ("三十二、无效宣告请求审理程序", 49, 52),
    ("三十三、无效审查中的证据", 53, 53),
    ("三十四、外观设计的申请文件与初步审查", 54, 58),
    ("三十五、外观设计专利的授权条件", 59, 62),
    ("三十六、专利侵权行为分析", 63, 64),
    ("三十七、专利侵权判断", 65, 68),
    ("三十八、专利纠纷司法程序", 69, 71),
    ("三十九、专利纠纷行政裁决和调解", 72, 75),
    ("四十、对假冒专利行为的查处", 76, 76),
    ("四十一、专利许可", 77, 78),
    ("四十二、专利合作条约(PCT)", 79, 81),
    ("四十三、PCT进入中国国家阶段", 82, 83),
    ("四十四、海牙协定", 84, 84),
    ("四十五、专利文献", 85, 86),
    ("附录一 期限及涉及数字知识点汇总", 87, 97),
    ("附录二 四种数值范围的判断", 98, 99),
    ("附录三 不予受理、视为撤回等总结", 100, 100),
]

# ==================== 相关法目录 ====================
XG_CHAPTERS = [
    ("一、民法典总则编", 1, 8),
    ("二、民法典合同编", 9, 18),
    ("三、民事诉讼法", 19, 33),
    ("四、行政复议法和行政诉讼法", 34, 47),
    ("五、商标法", 48, 60),
    ("六、著作权法", 61, 69),
    ("七、反不正当竞争法", 70, 71),
    ("八、植物新品种", 72, 73),
    ("九、集成电路布图设计", 74, 75),
    ("十、知识产权海关保护条例", 76, 77),
    ("十一、展会知识产权保护", 78, 78),
    ("十二、对外贸易法", 79, 79),
    ("十三、刑法", 79, 80),
    ("十四、巴黎公约", 81, 82),
    ("十五、Trips协定", 83, 89),
    ("附录一 期限及涉及数字知识点汇总", 90, 104),
]

def clean_tags(text):
    if not text: return ""
    text = text.replace("[BLUE]", '<span class="key-blue">')
    text = text.replace("[/BLUE]", '</span>')
    text = text.replace("[RED]", '<span class="key-red">')
    text = text.replace("[/RED]", '</span>')
    text = re.sub(r'\[BLUE\]([^[\]]*?)(?=\[|$)', r'<span class="key-blue">\1</span>', text)
    text = re.sub(r'\[RED\]([^[\]]*?)(?=\[|$)', r'<span class="key-red">\1</span>', text)
    return text.strip()

def is_page_ref(text):
    if not text: return True
    text = text.strip()
    return bool(re.match(r'^第?\d+页?$', text) or (re.match(r'^\d+$', text) and len(text) <= 3))

def is_raw_json(text):
    if not text: return False
    text = text.strip()
    return text.startswith('{') and '"id"' in text and '"title"' in text

def extract_from_json(text):
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
    result = []
    for tbl in tables:
        if not isinstance(tbl, dict): continue
        headers = tbl.get('headers', [])
        rows = tbl.get('rows', [])
        fixed = []
        for row in rows:
            if isinstance(row, list):
                fixed.append([clean_tags(str(c)) for c in row])
            elif isinstance(row, str):
                cells = [c.strip() for c in row.split('|') if c.strip()]
                fixed.append([clean_tags(c) for c in cells] if cells else [clean_tags(row)])
        if headers or fixed:
            result.append({'headers': headers, 'rows': fixed})
    return result

def fix_point(pt):
    if not pt: return None
    title = clean_tags((pt.get('title') or '').strip())
    content = (pt.get('content') or '').strip()
    sub_points = pt.get('sub_points') or []
    tables = pt.get('tables') or []
    
    if is_raw_json(content):
        content = extract_from_json(content)
    elif is_page_ref(content):
        content = ''
    else:
        content = clean_tags(content)
    
    clean_subs = []
    for sp in sub_points:
        if isinstance(sp, dict):
            sp = extract_from_json(json.dumps(sp, ensure_ascii=False))
        else:
            sp = str(sp).strip()
            if is_raw_json(sp):
                sp = extract_from_json(sp)
            else:
                sp = clean_tags(sp)
        if sp and not is_page_ref(sp):
            clean_subs.append(sp)
    
    clean_tables = fix_tables(tables)
    
    if not content and clean_subs:
        content = clean_subs.pop(0)
    
    if not content and not clean_subs and not clean_tables:
        return None
    
    return {
        'id': pt.get('id', ''),
        'title': title,
        'content': content,
        'sub_points': clean_subs,
        'tables': clean_tables
    }

def get_chapter_for_page(page_num, chapters):
    for name, start, end in chapters:
        if start <= page_num <= end:
            return name
    return chapters[-1][0]  # 默认最后一章

def process_subject(subject, chapter_defs):
    raw_file = os.path.join(EXTRACT_DIR, f"{subject}_raw.json")
    with open(raw_file) as f:
        pages = json.load(f)
    
    # 按页码分配到章节
    chapter_map = {name: [] for name, _, _ in chapter_defs}
    
    for page in pages:
        if page.get('page_type') in ('api_error', 'parse_error'):
            continue
        
        page_num = page.get('page_num', 0)
        chapter_name = get_chapter_for_page(page_num, chapter_defs)
        
        for pt in (page.get('points') or []):
            fixed = fix_point(pt)
            if fixed:
                chapter_map[chapter_name].append(fixed)
        
        # 页面级表格
        for tbl in (page.get('tables') or []):
            if isinstance(tbl, dict) and tbl.get('headers'):
                fixed_tbl = fix_tables([tbl])
                if fixed_tbl and chapter_map[chapter_name]:
                    last = chapter_map[chapter_name][-1]
                    last['tables'].extend(fixed_tbl)
    
    # 构建章节列表（过滤空章节）
    chapters = []
    for name, _, _ in chapter_defs:
        points = chapter_map[name]
        if points:
            chapters.append({'title': name, 'points': points})
    
    total = sum(len(c['points']) for c in chapters)
    print(f'\n{subject}: {len(chapters)}章, {total}知识点')
    for ch in chapters:
        print(f'  {ch["title"][:30]}: {len(ch["points"])}点')
    
    return {'subject': subject, 'chapters': chapters}

def main():
    zl = process_subject('专利法', ZL_CHAPTERS)
    xg = process_subject('相关法', XG_CHAPTERS)
    
    # 读取模板
    with open(os.path.join(BASE_DIR, 'template.html'), encoding='utf-8') as f:
        template = f.read()
    
    zl_json = json.dumps(zl, ensure_ascii=False)
    xg_json = json.dumps(xg, ensure_ascii=False)
    
    inject = template.rfind('</script>')
    new_html = (
        template[:inject]
        + '\nvar zl200Data = ' + zl_json + ';\n'
        + 'var xg200Data = ' + xg_json + ';\n'
        + 'function loadData() {\n'
        + '  App.data.patent = zl200Data;\n'
        + '  App.data.related = xg200Data;\n'
        + '  renderContent();\n  updateStats();\n  buildTOC();\n'
        + '}\n'
        + template[inject:]
    )
    
    # 移除async loadData
    new_html = re.sub(r'async function loadData\(\)\s*\{.*?\n\}', '', new_html, flags=re.DOTALL)
    
    # 修复表格rows
    old = 'tbl.rows.forEach(row => {\n            html += `<tr>`;\n            row.forEach(cell => html += `<td>${cell}</td>`);'
    new = '(tbl.rows||[]).forEach(row => {\n            html += `<tr>`;\n            var cells = Array.isArray(row) ? row : [row];\n            cells.forEach(cell => html += `<td>${cell}</td>`);'
    new_html = new_html.replace(old, new)
    
    with open(os.path.join(BASE_DIR, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(new_html)
    
    print(f'\nindex.html: {os.path.getsize(os.path.join(BASE_DIR, "index.html"))//1024}KB')

if __name__ == '__main__':
    main()
