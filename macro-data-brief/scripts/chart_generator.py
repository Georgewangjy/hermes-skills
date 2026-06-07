#!/usr/bin/env python3
"""
SVG趋势图生成器 - 金融资讯卡片风格
参考：微信公众号/财经App图表样式
浅天蓝背景 + 深紫粗折线 + 白心圆点 + 虚线网格
"""

def generate_trend_chart(
    title: str,
    data: list,
    expected: float = None,
    color: str = "#5D3FD3",
    unit: str = "",
    width: int = 600,
    height: int = 220,
) -> str:
    if not data:
        return ""
    
    margin_left = 50
    margin_right = 20
    margin_top = 30
    margin_bottom = 50
    plot_w = width - margin_left - margin_right
    plot_h = height - margin_top - margin_bottom
    
    values = [v for _, v in data]
    if expected is not None:
        values.append(expected)
    y_min = min(values)
    y_max = max(values)
    y_range = y_max - y_min
    if y_range == 0:
        y_range = y_max * 0.2 if y_max != 0 else 1
    y_min -= y_range * 0.1
    y_max += y_range * 0.1
    y_range = y_max - y_min
    
    def x_pos(i):
        return margin_left + (i / max(len(data) - 1, 1)) * plot_w
    
    def y_pos(v):
        return margin_top + plot_h - ((v - y_min) / y_range) * plot_h
    
    import math
    n_ticks = 4
    tick_step = y_range / n_ticks
    magnitude = 10 ** math.floor(math.log10(tick_step)) if tick_step > 0 else 1
    tick_step = round(tick_step / magnitude) * magnitude
    if tick_step == 0:
        tick_step = 1
    
    svg = []
    svg.append(f'<div class="chart-container">')
    svg.append(f'<div class="chart-title">{title}</div>')
    svg.append(f'<svg viewBox="0 0 {width} {height}" class="chart">')
    
    # 浅天蓝背景
    svg.append(f'<rect x="0" y="0" width="{width}" height="{height}" fill="#F0F8FF" rx="6"/>')
    # 左上角装饰条
    svg.append(f'<rect x="0" y="0" width="4" height="16" fill="{color}" rx="2"/>')
    
    # Y轴水平虚线网格
    tick_val = math.ceil(y_min / tick_step) * tick_step
    while tick_val <= y_max:
        y = y_pos(tick_val)
        svg.append(f'<line x1="{margin_left}" y1="{y:.1f}" x2="{width-margin_right}" y2="{y:.1f}" stroke="#ccc" stroke-width="0.5" stroke-dasharray="4,3"/>')
        label = f"{tick_val:.0f}" if tick_val == int(tick_val) else f"{tick_val:.1f}"
        svg.append(f'<text x="{margin_left-8}" y="{y+4:.1f}" text-anchor="end" font-family="NotoSC,sans-serif" font-size="11" fill="#333">{label}</text>')
        tick_val += tick_step
    
    # X轴标签（竖排旋转-90度）
    label_interval = max(1, len(data) // 6)
    for i, (label, _) in enumerate(data):
        if i % label_interval == 0 or i == len(data) - 1:
            x = x_pos(i)
            svg.append(f'<text x="{x:.1f}" y="{margin_top+plot_h+12}" text-anchor="end" font-family="NotoSC,sans-serif" font-size="10" fill="#666" transform="rotate(-90 {x:.1f},{margin_top+plot_h+12})">{label}</text>')
    
    # 预期值蓝色虚线
    if expected is not None:
        ey = y_pos(expected)
        svg.append(f'<line x1="{margin_left}" y1="{ey:.1f}" x2="{width-margin_right}" y2="{ey:.1f}" stroke="#2563eb" stroke-width="1" stroke-dasharray="6,4"/>')
        svg.append(f'<text x="{width-margin_right+3}" y="{ey+4:.1f}" font-family="NotoSC,sans-serif" font-size="10" fill="#2563eb">预期{expected}{unit}</text>')
    
    # 数据折线（粗线3px）
    points = " ".join(f"{x_pos(i):.1f},{y_pos(v):.1f}" for i, (_, v) in enumerate(data))
    svg.append(f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>')
    
    # 数据点（白心+彩色描边）
    for i, (_, v) in enumerate(data):
        cx = x_pos(i)
        cy = y_pos(v)
        r = 5 if i < len(data) - 1 else 7
        svg.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="#fff" stroke="{color}" stroke-width="2"/>')
    
    # 最新数据标注
    if data:
        last_label, last_val = data[-1]
        lx = x_pos(len(data) - 1)
        ly = y_pos(last_val)
        val_text = f"{last_val:.1f}" if last_val != int(last_val) else f"{last_val:.0f}"
        svg.append(f'<text x="{lx:.1f}" y="{ly-12:.1f}" text-anchor="middle" font-family="NotoSC,sans-serif" font-size="12" font-weight="700" fill="{color}">{val_text}{unit}</text>')
    
    svg.append('</svg>')
    svg.append('</div>')
    
    return "\n".join(svg)


if __name__ == "__main__":
    nfp_data = [
        ('7月', 11.4), ('8月', 15.9), ('9月', 25.4), ('10月', 13.8),
        ('11月', 21.6), ('12月', 23.7), ('1月', 14.3), ('2月', 11.1),
        ('3月', 18.5), ('4月', 17.9), ('5月', 17.2),
    ]
    print(generate_trend_chart("非农就业新增（万人）近12个月趋势", nfp_data, expected=9, color="#5D3FD3", unit="万"))
