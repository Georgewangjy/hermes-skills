---
name: macro-data-brief
description: Use when user says macro analysis or requests analysis of macroeconomic data releases (NFP, CPI, GDP, FOMC, PMI). Full pipeline from data search to PDF with SVG charts and WeChat delivery.
version: 1.3.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [macro, economics, nonfarm, CPI, GDP, FOMC, article, PDF, WeChat]
    related_skills: [duckduckgo-search-free, sina-finance, eastmoney_financial_data]
---

# 宏观数据速评文章生成

## Overview

将宏观经济数据发布（非农、CPI、GDP、FOMC决议、PMI等）的搜索、分析、成文、排版、交付流程标准化。从原始数据到可发布的公众号文章，一条龙完成。

## When to Use

- 用户说"宏观分析"或要求分析某项宏观数据（"分析非农"、"CPI怎么看"）
- 用户要求生成公众号文章/报告
- 用户要求输出PDF格式报告
- 定时任务触发宏观数据速评

Don't use for:
- 实时行情查询（用sina-finance/东方财富API）
- 单纯数据获取不做分析

## 完整流程

### Phase 1: 数据采集（Data Collection）

**步骤**：
1. 确定数据类型和发布时间
2. 用DuckDuckGo搜索英文+中文双源
3. 优先抓取权威源：BLS/BEA/Fed官网 + 第一财经/财新/中新社
4. 提取核心数据点

**搜索模板**：
```
英文: "{指标名} {月份} {年份} {国家}" 例: "US nonfarm payrolls June 2026"
中文: "美国{月份}{指标中文名} {年份}" 例: "美国5月非农就业数据 2026"
```

**中国数据搜索模板**（与美欧数据不同）：
```
英文: "China {指标英文名} {月份} {年份}" 例: "China PMI May 2026"
中文: "中国{月份}{指标中文名} {年份}" 例: "中国5月PMI数据 2026"
权威源优先: 国家统计局 stats.gov.cn（中文版+英文版均有完整数据表）
英文版优势: stats.gov.cn/english 提供完整历史数据表格（Table 1/2/3），比中文新闻更完整
补充源: 财新网 pmi.caixin.com、中国物流与采购网 chinawuliu.com.cn
```

**数据提取清单**（以非农为例，其他指标类推）：

| 字段 | 说明 | 优先级 |
|------|------|--------|
| 实际值 | 本次发布数据 | P0 |
| 预期值 | 市场共识预期 | P0 |
| 前值 | 上期数据（含修正） | P0 |
| 前值修正 | 上修/下修幅度 | P1 |
| 分项数据 | 行业/地区拆解 | P1 |
| 关联指标 | 失业率/薪资/参与率等 | P1 |
| 历史数据 | 近6-12个月趋势数据 | P1 |
| 机构观点 | 投行/IMF/央行评论 | P2 |
| 市场反应 | 期货定价/汇率/利率变化 | P2 |

**数据验证规则**：
- 🔴 **永远不假设数据**：未找到则明确标注"数据待确认"
- 🔴 **交叉验证**：至少2个独立来源确认核心数据
- 🔴 **标注来源**：每个数据点标注出处

### Phase 2: 结构化分析（Analysis Framework）

**固定分析框架**：

```
1. 核心数据一览（表格+卡片+历史趋势图）
   - 实际 vs 预期 vs 前值
   - 信号灯：🔴超预期 / 🟢低于预期 / ⚪符合预期
   - 历史趋势图：近12个月数据变化（SVG内嵌）

2. 结构拆解
   - 分项/行业/地区贡献度
   - 一次性因素识别（季节性/事件驱动）
   - 趋势 vs 噪音分离

3. 三大核心解读
   ① 表面数据 vs 内在质量
   ② 被市场忽视的信号
   ③ 政策含义（美联储/央行反应函数）

4. 传导路径（对A股/人民币/北向/黄金）
   - 方向判断（↑↓⚠️）
   - 传导逻辑（1-2句）

5. 结论 + 下周关注点
```

**分析原则**：
- 结构性分析优先于总量分析
- 识别一次性效应 vs 趋势性变化
- 政策含义必须结合通胀/增长双维度
- 传导路径需区分短期冲击 vs 中期趋势

### Phase 3: HTML→PDF 输出

**重要**：涉及排版/样式调整时，先生成预览版发给用户确认，再改最终版。避免多次返工。

生成自包含HTML文件（CSS内嵌+SVG图表+移动端适配），再用WeasyPrint渲染为PDF。

**关键CSS变量**：
```css
--accent: #c41e3a;      /* 红色强调 */
--green: #059669;       /* 绿色积极 */
--amber: #d97706;       /* 黄色警告 */
--ink: #1a1a2e;         /* 深色正文 */
--surface: #f7f8fa;     /* 卡片背景 */
```

**组件库**：
- `highlight-grid`：2列数据卡片
- `data-table`：深色表头数据表
- `industry-list`：行业条目+进度条
- `insight-box`：彩色提示框（red/green/amber）
- `quote-block`：引用块
- `conclusion`：深色结论卡片
- `chart-container`：SVG历史趋势图（浅天蓝背景#F0F8FF，边框#d0e8f5）
- `chart-title`：图表标题（左侧紫色竖条装饰）

**历史趋势图（SVG内嵌）— 金融资讯卡片风格**：

用 `scripts/chart_generator.py` 生成近12个月数据趋势图，每个核心指标一张图。无需外部依赖。

**视觉规范（用户确认的金融资讯卡片风格）**：
- **背景**: 浅天蓝色 `#F0F8FF`，不是纯白或浅灰
- **折线**: 深紫色 `#5D3FD3`，粗线 3px，直折线（非平滑曲线）
- **数据点**: 白心 + 彩色描边圆圈，最新点加大(r=7)并标注数值
- **网格线**: 水平虚线(dashed)，浅灰 `#ccc`，0.5px宽；无垂直网格线
- **坐标轴**: 隐藏轴线，仅保留刻度标签。Y轴标签黑色左对齐，X轴标签旋转-90°竖排
- **装饰**: 图表标题左侧紫色竖条，SVG左上角装饰方块
- **预期值**: 蓝色 `#2563eb` 水平虚线
- **无填充**: 折线下方无面积填充、无阴影、无渐变

**图表颜色分配**（不同指标用不同色）：

| 指标类型 | 折线色 | 用途 |
|----------|--------|------|
| 就业/NFP | `#5D3FD3` 深紫 | 主指标默认色 |
| 失业率 | `#D97706` 琥珀 | 警示类指标 |
| 薪资/通胀 | `#059669` 绿色 | 积极信号指标 |
| 对比指标 | `#2563eb` 蓝色 | 辅助对比 |

**生成示例**：
```python
from chart_generator import generate_trend_chart

nfp_data = [('7月', 11.4), ('8月', 15.9), ..., ('5月', 17.2)]
chart = generate_trend_chart(
    title="非农就业新增（万人）近12个月趋势",
    data=nfp_data,
    expected=9,        # 预期值虚线
    color="#5D3FD3",   # 深紫色
    unit="万",
)
```

**结论不跨页处理**：

在结论区块的CSS中添加：
```css
.conclusion {
  break-inside: avoid;  /* 防止跨页断裂 */
  page-break-inside: avoid;
}
```
如果结论前剩余空间不足，WeasyPrint会自动将整个结论块推到下一页。

**WeasyPrint前置条件**：
```bash
pip install --no-deps fpdf2 fonttools weasyprint pydyf cffi tinycss2 cssselect2 html5lib tinyhtml5 pyphen
pkg install python-pillow
python3 -c "from fontTools.ttLib import TTCollection; ttc=TTCollection('/system/fonts/NotoSansCJK-Regular.ttc'); ttc.fonts[2].save('$HOME/NotoSansCJKSC-Regular.ttf')"
```

**HTML必须包含字体声明**：
```css
@font-face {
  font-family: 'NotoSC';
  src: url('file:///data/data/com.termux/files/home/NotoSansCJKSC-Regular.ttf');
  font-weight: normal;
}
body { font-family: 'NotoSC', sans-serif; }
```

**生成命令**：
```python
from weasyprint import HTML
HTML('/path/to/article.html').write_pdf('/path/to/article.pdf')
```

### Phase 4: 交付（Delivery）

**交付方式**：PDF通过微信发送。

```
send_message(action='send', target='weixin', message='标题 MEDIA:/path/to/file.pdf')
```

**同时将HTML文件一并发送**，供用户浏览器预览或截图：
```
send_message(action='send', target='weixin', message='HTML预览版 MEDIA:/path/to/file.html')
```

**样式确认流程**：当涉及排版/图表样式调整时，先发预览版→用户确认→再生成最终版。不要跳过确认直接改。

## 模板文件

### HTML模板骨架

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<style>
@font-face {
  font-family: 'NotoSC';
  src: url('file:///data/data/com.termux/files/home/NotoSansCJKSC-Regular.ttf');
}
body { font-family: 'NotoSC', sans-serif; max-width: 680px; margin: 0 auto; padding: 20px; }
/* 组件CSS见Phase 3b */
</style>
</head>
<body>
<!-- Hero: 标题+标签+日期 -->
<!-- 核心数据: 卡片+表格 -->
<!-- 结构拆解: 列表+提示框 -->
<!-- 三大解读: 小标题+引用 -->
<!-- 传导路径: 表格 -->
<!-- 结论: 深色卡片 -->
<!-- Footer: 来源+免责 -->
</body>
</html>
```

## 支持文件

| 文件 | 用途 |
|------|------|
| `templates/article.html` | HTML排版模板（含CSS组件库+图表容器+防跨页结论） |
| `scripts/chart_generator.py` | SVG趋势图生成器（金融资讯卡片风格：浅蓝底+深紫粗线+白心圆点） |
| `scripts/html2pdf.py` | HTML→PDF转换脚本（WeasyPrint） |
| `references/termux-setup.md` | Termux环境WeasyPrint安装指南 |
| `references/china-pmi-data-guide.md` | 中国PMI数据采集指南（来源优先级+分项说明+历史数据） |

## 常见宏观数据指标对照

| 英文 | 中文 | 发布机构 | 发布频率 | 关键分项 |
|------|------|----------|----------|----------|
| Nonfarm Payrolls | 非农就业 | BLS | 月度 | 行业/薪资/失业率/U6 |
| CPI | 消费者物价指数 | BLS | 月度 | 核心/食品/能源/环比 |
| GDP | 国内生产总值 | BEA | 季度 | 消费/投资/净出口/政府 |
| FOMC Decision | 美联储决议 | Fed | 6周/次 | 利率/点阵图/声明措辞 |
| ISM PMI | 制造业PMI | ISM | 月度 | 新订单/就业/物价/库存 |
| PCE | 个人消费支出 | BEA | 月度 | 核心PCE（Fed首选通胀指标） |
| Jobless Claims | 初请失业金 | DOL | 周度 | 初请/续请/4周均值 |
| 中国官方PMI | 制造业PMI | 国家统计局 | 月度 | 生产/新订单/新出口/从业人员/购进价格/出厂价格/库存 |
| 中国非制造业PMI | 非制造业商务活动指数 | 国家统计局 | 月度 | 服务业/建筑业/新订单 |
| 中国综合PMI | 综合PMI产出指数 | 国家统计局 | 月度 | 制造业+非制造业加权 |
| 财新PMI | 财新制造业PMI | S&P Global/财新 | 月度 | 侧重中小企业/出口导向，与官方PMI互补 |

## Common Pitfalls

1. **假设数据而非搜索**：永远从搜索开始，不凭记忆填写数据。用户对数据准确性要求极高（偏差>5%即不可接受）。

2. **只搜中文源**：英文源（BLS/Yahoo Finance/Investing.com）数据更完整更及时，中文源适合补充解读。**例外**：中国数据的国家统计局英文版(stats.gov.cn/english)提供完整历史表格，比中文新闻源更可靠。

3. **忽略前值修正**：非农等数据常大幅上修/下修，修正幅度本身是重要信号。

4. **PDF中文乱码**：必须嵌入@font-face声明NotoSC字体，否则WeasyPrint在Termux下无法渲染中文。

5. **结论跨页断裂**：结论区块必须加`break-inside: avoid; page-break-inside: avoid;`，防止被切分到两页。

6. **HTML未做移动端适配**：公众号主要在手机阅读，max-width:680px + 响应式断点必须。

7. **分析缺乏结构**：避免纯叙述，必须用表格/卡片/信号灯做结构化呈现。

8. **遗漏一次性因素**：世界杯/奥运会/罢工结束等一次性效应必须标注，否则误导趋势判断。

9. **历史图表缺失**：核心指标必须有近12个月SVG趋势图，仅有表格不够直观。

10. **图表风格不对**：必须使用金融资讯卡片风格（浅天蓝背景#F0F8FF + 深紫粗折线#5D3FD3 + 白心圆点 + 虚线网格），不是简单的红细线+浅灰背景。用户明确拒绝了后者。

11. **未经确认就改最终版**：涉及排版/样式调整时，先发预览版让用户确认，再改最终版。

12. **中国PMI分析遗漏企业规模分化**：官方PMI按大/中/小型企业分列，规模分化是核心信号（大企扩张vs中小企收缩），必须单独列表呈现。

13. **中国PMI分析遗漏新旧动能分化**：高技术制造PMI和装备制造PMI是关键领先指标，与整体PMI的差距扩大=分化加剧，必须重点标注。

14. **混淆2025/2026年数据**：搜索财新PMI时，DuckDuckGo常返回旧年份数据（2025年5月而非2026年5月），必须核对发布日期。

## Verification Checklist

- [ ] 核心数据（实际/预期/前值）至少2个来源交叉验证
- [ ] 前值修正已标注
- [ ] 历史趋势图已生成（SVG内嵌，近12个月，金融资讯卡片风格）
- [ ] 一次性效应已识别并标注
- [ ] 政策含义已分析（美联储/央行反应函数）
- [ ] A股传导路径已列出
- [ ] 结论+下周关注点完整
- [ ] 结论区块有break-inside:avoid防止跨页
- [ ] HTML包含@font-face字体声明
- [ ] PDF中文渲染正常（非方框/乱码）
- [ ] 所有数据点标注来源
