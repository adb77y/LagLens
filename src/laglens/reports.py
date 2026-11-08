"""Self-contained exports. Escape user-controlled names in HTML and SVG."""
import html
import math


def svg_report(record):
    a = record['analysis']
    escape = lambda value: html.escape(str(value), quote=True)
    points = a['timeline']
    duration = max((points[-1]['t'] - points[0]['t']) if points else 1, 1)
    max_y = max(40, math.ceil(max((f['ms'] for f in points), default=0) / 40) * 40)
    first = points[0]['t'] if points else 0
    coords = ' '.join(f"{80+(f['t']-first)/duration*1120:.1f},{430-min(f['ms']/max_y,1)*190:.1f}" for f in points)
    ticks = ''.join(f'<line x1="80" y1="{430-i*47.5}" x2="1200" y2="{430-i*47.5}" stroke="#303034"/><text x="64" y="{434-i*47.5}" text-anchor="end" fill="#b4b4bb" font-size="14">{max_y*i/4:g}</text>' for i in range(5))
    xlabels = ''.join(f'<text x="{80+i*280}" y="458" text-anchor="{("start" if i==0 else "end" if i==4 else "middle")}" fill="#b4b4bb" font-size="14">{duration/1000*i/4:.1f}s</text>' for i in range(5))
    metrics = [('Average FPS', a['average_fps'], 'fps'), ('1% low FPS', a['low_1_fps'], 'fps'),
               ('P99 frame time', a['p99_ms'], 'ms'), ('Stutter events', a['stutter_count'], '')]
    values = ''
    for i, (label, value, unit) in enumerate(metrics):
        value = '—' if value is None else f'{value:,.1f}' if isinstance(value, float) else str(value)
        values += f'<text x="{80+i*290}" y="162" fill="#b4b4bb" font-size="15">{label}</text><text x="{80+i*290}" y="204" fill="#fafafa" font-size="32">{value} <tspan font-size="16" fill="#b4b4bb">{unit}</tspan></text>'
    findings = a['findings'][:2]
    findings_text = ''
    for i, finding in enumerate(findings):
        y = 521 + i*84
        findings_text += f'<text x="80" y="{y}" fill="#fafafa" font-size="19">{escape(finding["title"])} · {escape(finding["confidence"])}</text>'
        words, lines, line = finding['evidence'].split(), [], ''
        for word in words:
            if len(line + ' ' + word) > 116:
                lines.append(line)
                line = word
            else:
                line = (line+' '+word).strip()
        lines.append(line)
        for j, line in enumerate(lines[:2]):
            findings_text += f'<text x="80" y="{y+25+j*19}" fill="#b4b4bb" font-size="14">{escape(line)}</text>'
    sample = 'Illustrative sample — not a hardware benchmark' if record['source']=='demo' else 'Measured capture · correlations are not proof of cause'
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="760" viewBox="0 0 1280 760">
<rect width="1280" height="760" fill="#171719"/><g font-family="Segoe UI,Arial,sans-serif">
<text x="80" y="62" fill="#fafafa" font-size="24" font-weight="600">LagLens</text>
<text x="1200" y="62" text-anchor="end" fill="#b4b4bb" font-size="14">{escape(record['created_at'][:19])}</text>
<text x="80" y="106" fill="#fafafa" font-size="22">{escape(record['name'][:84])}</text>
{values}<text x="80" y="232" fill="#b4b4bb" font-size="13">Frame time (ms) · {a['frame_count']:,} frames · threshold {a['threshold_ms'] or 0:.1f} ms</text>
{ticks}<polyline points="{coords}" fill="none" stroke="#4a8ad6" stroke-width="2"/>{xlabels}
{findings_text}<text x="80" y="707" fill="#b4b4bb" font-size="14">{sample}</text>
<text x="80" y="731" fill="#b4b4bb" font-size="12">Presented frames · one dominant swap chain · compare the same scene and route · laglens 0.1.0</text>
</g></svg>'''


def html_report(record):
    escape = lambda text: html.escape(str(text), quote=True)
    findings = ''.join(f'<section><h2>{escape(f["title"])}</h2><p><b>{escape(f["confidence"])} confidence.</b> {escape(f["evidence"])}</p><p>{escape(f["next"])}</p></section>' for f in record['analysis']['findings'])
    return f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(record['name'])} — LagLens report</title><style>body{{margin:32px auto;max-width:1100px;padding:0 20px;background:#171719;color:#fff;font:16px/1.6 system-ui}}svg{{width:100%;height:auto}}section{{padding:20px 0;border-top:1px solid #333}}h2{{font-size:20px}}p{{color:#c3c3ca}}@media print{{body{{background:white;color:black}}p{{color:#333}}}}</style>
{svg_report(record)}{findings}<p>{escape(record.get('notes',''))}</p><p>Saved locally. This report contains the application name, capture metrics, and findings. No usernames, executable paths or network addresses are included.</p></html>'''
