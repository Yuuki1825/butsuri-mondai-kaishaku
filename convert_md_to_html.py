import re
import urllib.parse

def convert_md_to_html(input_md, output_html, title):
    with open(input_md, "r", encoding="utf-8") as f:
        content = f.read()

    content = re.sub(r'\n\[image\d+\]: <data:image/png;base64,[^>]*>', '', content)

    formulas = []

    def store_codecogs(match):
        encoded_latex = match.group(1)
        encoded_latex = re.sub(r'#\d+$', '', encoded_latex)
        latex = urllib.parse.unquote(encoded_latex)
        latex = latex.replace('\\(', '(')
        latex = latex.replace('\\)', ')')
        idx = len(formulas)
        formulas.append(latex)
        return f'\x00F{idx}\x00'

    pattern = r'\[!\[\]\[image\d+\]\]\(https://www\.codecogs\.com/eqnedit\.php\?latex=(.*?#\d+)\)'
    content = re.sub(pattern, store_codecogs, content)

    def fix_latex(latex):
        latex = re.sub(r'\\\\([a-zA-Z])', lambda m: '\\' + m.group(1), latex)
        latex = latex.replace('\\=', '=')
        latex = latex.replace('\\_', '_')
        latex = latex.replace('\\<', '<')
        latex = latex.replace('\\>', '>')
        latex = latex.replace('\\+', '+')
        latex = latex.replace('\\-', '-')
        latex = latex.replace('\\*', '*')
        latex = latex.replace('\\[', '[')
        latex = latex.replace('\\]', ']')
        return latex

    def store_formula(match):
        latex = fix_latex(match.group(1))
        idx = len(formulas)
        formulas.append(latex)
        return f'\x00F{idx}\x00'

    new_lines = []
    for line in content.split('\n'):
        line = re.sub(r'\$\$([^\$]+?)\$\$', store_formula, line)
        line = re.sub(r'\$([^\$]+?)\$', store_formula, line)
        if '$' in line:
            line = line.replace('$$', '')
            if '$' in line:
                parts = line.split('$')
                rebuilt = parts[0]
                for pi in range(1, len(parts)):
                    fragment = parts[pi]
                    latex = fix_latex(fragment.strip())
                    if latex:
                        latex = latex.rstrip('| ')
                        opens = latex.count('{') - latex.count('}')
                        if opens > 0:
                            latex += '}' * opens
                        if latex:
                            idx = len(formulas)
                            formulas.append(latex)
                            rebuilt += f'\x00F{idx}\x00'
                line = rebuilt
        new_lines.append(line)

    content = '\n'.join(new_lines)

    def fix_plain_text(text):
        text = text.replace('\\=', '=')
        text = text.replace('\\_', '_')
        text = text.replace('\\-', '-')
        text = text.replace('\\+', '+')
        text = text.replace('\\<', '<')
        text = text.replace('\\>', '>')
        text = text.replace('\\[', '[')
        text = text.replace('\\]', ']')
        text = re.sub(r'\\\\([a-zA-Z])', lambda m: '\\' + m.group(1), text)
        return text

    def fix_text_preserving_placeholders(text):
        text = re.sub(r'\\\*\\\*(.+?)\\\*\\\*', lambda m: '\x01STRONG' + m.group(1) + '\x01/STRONG', text)
        text = re.sub(r'\*\*(.+?)\*\*', lambda m: '\x01STRONG' + m.group(1) + '\x01/STRONG', text)
        text = text.replace('\\*', '*')
        parts = re.split(r'(\x00F\d+\x00)', text)
        result = []
        for part in parts:
            if part.startswith('\x00F') and part.endswith('\x00'):
                result.append(part)
            else:
                result.append(fix_plain_text(part))
        return ''.join(result)

    content = fix_text_preserving_placeholders(content)

    lines = content.split('\n')
    html_lines = []
    toc_entries = []
    in_table = False
    in_thead = False
    in_tbody = False
    table_alignment = []
    heading_counter = 0

    def restore_formulas(text):
        parts = re.split(r'(\x00F\d+\x00)', text)
        result = []
        for part in parts:
            m = re.match(r'\x00F(\d+)\x00', part)
            if m:
                idx = int(m.group(1))
                result.append('$' + formulas[idx] + '$')
            else:
                part = part.replace('&', '&amp;')
                part = part.replace('<', '&lt;')
                part = part.replace('>', '&gt;')
                result.append(part)
        out = ''.join(result)
        out = out.replace('\x01STRONG', '<strong>')
        out = out.replace('\x01/STRONG', '</strong>')
        return out

    def strip_html(text):
        return re.sub(r'<[^>]+>', '', text)

    def parse_table_cells(line):
        cells = []
        current = ''
        in_placeholder = False
        raw = line.strip()
        if raw.startswith('|'): raw = raw[1:]
        if raw.endswith('|'): raw = raw[:-1]
        for ch in raw:
            if ch == '\x00':
                in_placeholder = not in_placeholder
                current += ch
            elif ch == '|' and not in_placeholder:
                cells.append(current.strip())
                current = ''
            else:
                current += ch
        if current.strip():
            cells.append(current.strip())
        return cells

    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        if line == '':
            if in_table:
                if in_tbody: html_lines.append('</tbody>'); in_tbody = False
                html_lines.append('</table>'); in_table = False; in_thead = False
            i += 1; continue
        hm = re.match(r'^(#{1,6})\s+(.*)', line)
        if hm:
            if in_table:
                if in_tbody: html_lines.append('</tbody>'); in_tbody = False
                html_lines.append('</table>'); in_table = False; in_thead = False
            level = len(hm.group(1))
            text_html = restore_formulas(hm.group(2))
            heading_counter += 1
            hid = f'sec-{heading_counter}'
            toc_entries.append((level, hid, strip_html(text_html)))
            html_lines.append(f'<h{level} id="{hid}">{text_html}</h{level}>')
            i += 1; continue
        if re.match(r'^\|[\s:\-]+\|', line):
            cells = [c.strip() for c in line.strip('|').split('|')]
            table_alignment = []
            for cell in cells:
                c = cell.strip()
                if c.startswith(':') and c.endswith(':'): table_alignment.append('center')
                elif c.endswith(':'): table_alignment.append('right')
                else: table_alignment.append('left')
            if in_thead: html_lines.append('</thead>'); in_thead = False
            html_lines.append('<tbody>'); in_tbody = True
            i += 1; continue
        if line.startswith('|'):
            if not in_table:
                html_lines.append('<table>'); html_lines.append('<thead>'); in_table = True; in_thead = True
            cells = parse_table_cells(line)
            tag = 'th' if in_thead else 'td'
            html_lines.append('<tr>')
            for j, cell in enumerate(cells):
                align = table_alignment[j] if j < len(table_alignment) else 'left'
                html_lines.append(f'<{tag} style="text-align: {align};">{restore_formulas(cell)}</{tag}>')
            html_lines.append('</tr>')
            i += 1; continue
        html_lines.append(f'<p>{restore_formulas(line)}</p>')
        i += 1

    if in_table:
        if in_tbody: html_lines.append('</tbody>')
        html_lines.append('</table>')

    html_body = '\n'.join(html_lines)

    # Build sidebar TOC
    toc_html_parts = []
    for level, hid, text in toc_entries:
        cls = 'toc-h2' if level == 2 else 'toc-h3'
        toc_html_parts.append(f'<a class="{cls}" href="#{hid}">{text}</a>')
    toc_html = '\n'.join(toc_html_parts)

    # Derive the index page filename from the output filename
    base = output_html.replace('.html', '')
    index_page = base + '_index.html'

    html = f'''<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<script>
MathJax = {{
  tex: {{
    inlineMath: [['$', '$']],
    displayMath: [['$$', '$$']],
    processEscapes: true
  }},
  options: {{
    skipHtmlTags: ['script', 'noscript', 'style', 'textarea', 'pre']
  }}
}};
</script>
<script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js" async></script>
<style>
  * {{ box-sizing: border-box; }}
  body {{
    font-family: "Hiragino Kaku Gothic ProN", "Noto Sans JP", "Meiryo", sans-serif;
    margin: 0; padding: 0;
    line-height: 1.8; color: #333; background-color: #fafafa;
  }}
  .layout {{ display: flex; min-height: 100vh; }}
  .sidebar {{
    position: sticky; top: 0; align-self: flex-start;
    width: 240px; min-width: 240px; height: 100vh;
    overflow-y: auto; background: #fff;
    border-right: 1px solid #e0e0e0;
    padding: 16px 0; font-size: 0.82rem;
  }}
  .sidebar-home {{
    display: block; text-decoration: none;
    padding: 8px 16px 12px; margin-bottom: 4px;
    color: #555; font-size: 0.8rem;
    border-bottom: 1px solid #eee;
    transition: color 0.1s;
  }}
  .sidebar-home:hover {{ color: #1a5276; }}
  .sidebar-home svg {{ vertical-align: -2px; margin-right: 4px; }}
  .sidebar-title {{
    font-weight: 700; font-size: 0.85rem; color: #1a5276;
    padding: 4px 16px 12px;
  }}
  .sidebar a.toc-h2, .sidebar a.toc-h3 {{
    display: block; text-decoration: none; color: #555;
    padding: 3px 16px; transition: background 0.1s, color 0.1s;
  }}
  .sidebar a:hover {{ background: #eef2f7; color: #1a5276; }}
  .sidebar a.active {{
    color: #1a5276; font-weight: 600; background: #eef2f7;
    border-left: 3px solid #3498db; padding-left: 13px;
  }}
  .toc-h2 {{ font-weight: 600; color: #1a5276 !important; margin-top: 10px; font-size: 0.88rem; }}
  .toc-h3 {{ padding-left: 28px !important; font-size: 0.8rem; }}
  .sidebar a.toc-h3.active {{ padding-left: 25px !important; }}
  .main {{
    flex: 1; max-width: 1000px; padding: 20px 36px; min-width: 0;
  }}
  h1 {{ font-size: 1.6rem; margin-bottom: 4px; }}
  h2 {{ color: #1a5276; border-bottom: 3px solid #1a5276; padding-bottom: 8px; margin-top: 40px; }}
  h3 {{ color: #2c3e50; border-left: 5px solid #3498db; padding-left: 12px; margin-top: 30px; }}
  table {{ border-collapse: collapse; width: 100%; margin: 16px 0; background-color: #fff; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
  th, td {{ border: 1px solid #ddd; padding: 10px 14px; text-align: left; vertical-align: top; }}
  th {{ background-color: #2c3e50; color: #fff; font-weight: bold; }}
  tr:nth-child(even) {{ background-color: #f8f9fa; }}
  tr:hover {{ background-color: #eef2f7; }}
  mjx-container {{ overflow-x: auto; }}
  .sidebar-toggle {{
    display: none; position: fixed; bottom: 20px; right: 20px; z-index: 1000;
    width: 48px; height: 48px; border-radius: 50%;
    background: #1a5276; color: #fff; border: none;
    font-size: 1.3rem; cursor: pointer; box-shadow: 0 2px 8px rgba(0,0,0,0.2);
  }}
  @media (max-width: 800px) {{
    .sidebar {{
      position: fixed; left: -260px; top: 0; z-index: 999;
      transition: left 0.25s; box-shadow: 2px 0 12px rgba(0,0,0,0.1);
    }}
    .sidebar.open {{ left: 0; }}
    .sidebar-toggle {{ display: block; }}
    .main {{ padding: 16px 18px; }}
  }}
</style>
</head>
<body>
<div class="layout">
  <nav class="sidebar" id="sidebar">
    <a class="sidebar-home" href="{index_page}">
      <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor"><path d="M6 2L0 7h2v7h3V9h2v5h3V7h2L6 2z"/></svg>
      章一覧に戻る
    </a>
    <div class="sidebar-title">{title}</div>
    {toc_html}
  </nav>
  <div class="main">
    <h1>{title}</h1>
    {html_body}
  </div>
</div>
<button class="sidebar-toggle" id="sidebarToggle" aria-label="目次">&#9776;</button>
<script>
(() => {{
  const btn = document.getElementById('sidebarToggle');
  const sb = document.getElementById('sidebar');
  btn.addEventListener('click', () => sb.classList.toggle('open'));
  document.querySelector('.main').addEventListener('click', () => sb.classList.remove('open'));
  const links = sb.querySelectorAll('a.toc-h2, a.toc-h3');
  const headings = [];
  links.forEach(a => {{
    const id = a.getAttribute('href').slice(1);
    const el = document.getElementById(id);
    if (el) headings.push({{ el, a }});
  }});
  let ticking = false;
  function updateActive() {{
    let current = headings[0];
    const scrollY = window.scrollY + 80;
    for (const h of headings) {{
      if (h.el.offsetTop <= scrollY) current = h;
    }}
    links.forEach(a => a.classList.remove('active'));
    if (current) {{
      current.a.classList.add('active');
      const sbRect = sb.getBoundingClientRect();
      const aRect = current.a.getBoundingClientRect();
      if (aRect.top < sbRect.top + 50 || aRect.bottom > sbRect.bottom - 20) {{
        current.a.scrollIntoView({{ block: 'center', behavior: 'smooth' }});
      }}
    }}
    ticking = false;
  }}
  window.addEventListener('scroll', () => {{
    if (!ticking) {{ requestAnimationFrame(updateActive); ticking = true; }}
  }});
  updateActive();
}})();
</script>
</body>
</html>
'''

    def wrap_bare_vars(html_text):
        def fix_td(m):
            content = m.group(1)
            parts = re.split(r'(\$[^\$]+?\$)', content)
            result = []
            for pi, part in enumerate(parts):
                if pi % 2 == 1: result.append(part)
                else:
                    part = re.sub(r'(?<![A-Za-z0-9])([A-Za-z])_([A-Za-z0-9]+)(?![A-Za-z0-9_])', lambda mm: f'${mm.group(1)}_{{{mm.group(2)}}}$', part)
                    result.append(part)
            return '<td' + m.group(0)[3:].replace(m.group(1), ''.join(result), 1)
        return re.sub(r'<td[^>]*>(.*?)</td>', fix_td, html_text, flags=re.DOTALL)

    html = wrap_bare_vars(html)

    with open(output_html, "w", encoding="utf-8") as f:
        f.write(html)

    # --- Generate chapter index page ---
    detail_filename = output_html.split('/')[-1] if '/' in output_html else output_html
    chapters = []  # list of (chapter_name, [(hid, problem_label)])
    current_chapter = None
    current_problems = []

    for level, hid, text in toc_entries:
        if level == 2:
            # Save any h3s collected before the first h2
            if current_problems and current_chapter is None:
                # Infer chapter name from problem titles (use most common topic keyword)
                topics = [p[1].split(None, 1)[1] if ' ' in p[1] else p[1] for p in current_problems]
                first_topic = topics[0].split('・')[0] if topics else "その他"
                chapters.append((first_topic, current_problems))
            elif current_chapter is not None:
                chapters.append((current_chapter, current_problems))
            current_chapter = text
            current_problems = []
        elif level == 3:
            current_problems.append((hid, text))
    if current_chapter is not None:
        chapters.append((current_chapter, current_problems))
    elif current_problems:
        chapters.append(("問題一覧", current_problems))

    # If no h2 headings at all, treat all h3 as one flat list
    if not chapters:
        all_h3 = [(hid, text) for level, hid, text in toc_entries if level == 3]
        if all_h3:
            chapters = [("問題一覧", all_h3)]

    index_body_parts = []
    for ch_name, problems in chapters:
        index_body_parts.append(f'<h2>{ch_name}</h2>')
        index_body_parts.append('<div class="problem-grid">')
        for hid, label in problems:
            index_body_parts.append(f'<a class="problem-chip" href="{detail_filename}#{hid}">{label}</a>')
        index_body_parts.append('</div>')

    index_body = '\n'.join(index_body_parts)

    index_html = f'''<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{
    font-family: "Hiragino Kaku Gothic ProN", "Noto Sans JP", "Meiryo", sans-serif;
    margin: 0; padding: 0;
    background: #f5f7fa; color: #2c3e50;
  }}
  .container {{
    max-width: 800px; margin: 0 auto; padding: 32px 24px 60px;
  }}
  .back-link {{
    display: inline-block; text-decoration: none; color: #555;
    font-size: 0.85rem; margin-bottom: 20px; transition: color 0.1s;
  }}
  .back-link:hover {{ color: #1a5276; }}
  .back-link svg {{ vertical-align: -2px; margin-right: 4px; }}
  h1 {{
    font-size: 1.6rem; font-weight: 700; margin-bottom: 32px;
  }}
  h2 {{
    font-size: 1.1rem; font-weight: 600; color: #1a5276;
    border-bottom: 2px solid #1a5276;
    padding-bottom: 6px; margin: 28px 0 14px;
  }}
  .problem-grid {{
    display: flex; flex-wrap: wrap; gap: 8px;
  }}
  a.problem-chip {{
    display: inline-block;
    padding: 6px 14px;
    background: #fff;
    border: 1px solid #dce1e8;
    border-radius: 8px;
    text-decoration: none;
    color: #2c3e50;
    font-size: 0.85rem;
    transition: background 0.12s, border-color 0.12s, transform 0.1s;
  }}
  a.problem-chip:hover {{
    background: #eef2f7;
    border-color: #3498db;
    transform: translateY(-1px);
  }}
</style>
</head>
<body>
<div class="container">
  <a class="back-link" href="index.html">
    <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor"><path d="M10 2L4 8l6 6V2z"/></svg>
    TOP
  </a>
  <h1>{title}</h1>
  {index_body}
</div>
</body>
</html>
'''

    with open(index_page, "w", encoding="utf-8") as f:
        f.write(index_html)

    print(f"Done: {output_html} ({len(formulas)} formulas)")
    print(f"  Index: {index_page} ({len(chapters)} chapters, {sum(len(p) for _, p in chapters)} problems)")

    return index_page


# --- Convert all ---
idx1 = convert_md_to_html("問題解釈｜良問の風.md", "問題解釈｜良問の風.html", "問題解釈｜良問の風")
idx2 = convert_md_to_html("問題解釈｜名門の森1.md", "問題解釈｜名門の森1.html", "問題解釈｜名門の森1")
idx3 = convert_md_to_html("問題解釈｜名門の森2.md", "問題解釈｜名門の森2.html", "問題解釈｜名門の森2")
