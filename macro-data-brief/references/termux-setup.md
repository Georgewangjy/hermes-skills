# 宏观数据速评 - Termux依赖安装指南

## WeasyPrint安装（已验证可行）

WeasyPrint是HTML→PDF的核心工具。Termux下不能直接`pip install weasyprint`（依赖编译超时），需分步安装：

```bash
# 1. 系统包
pkg install python-pillow pango libcairo fontconfig -y

# 2. Python包逐个安装（--no-deps避免编译超时）
pip install --no-deps fpdf2 fonttools
pip install --no-deps weasyprint pydyf cffi
pip install --no-deps tinycss2 cssselect2 html5lib tinyhtml5 pyphen

# 3. Pillow链接到hermes venv（pkg装的在系统site-packages，venv找不到）
SYSTEM_SITE=/data/data/com.termux/files/usr/lib/python3.13/site-packages
VENV_SITE=~/hermes-agent/venv/lib/python3.13/site-packages
ln -sf $SYSTEM_SITE/PIL $VENV_SITE/PIL
ln -sf $SYSTEM_SITE/Pillow-*.dist-info $VENV_SITE/

# 4. 提取中文字体（NotoSansCJK-Regular.ttc是.ttc集合，需提取单个ttf）
python3 -c "from fontTools.ttLib import TTCollection; ttc=TTCollection('/system/fonts/NotoSansCJK-Regular.ttc'); ttc.fonts[2].save('$HOME/NotoSansCJKSC-Regular.ttf')"
# Index 2 = SC (Simplified Chinese), 0=JP, 1=KR, 3=TC
```

## 验证

```bash
cd ~/hermes-agent && source venv/bin/activate
python3 -c "import weasyprint; print('weasyprint OK')"
python3 -c "from PIL import Image; print('Pillow OK')"
python3 -c "from fontTools.ttLib import TTFont; print('fonttools OK')"
```

## HTML→PDF生成

HTML必须包含@font-face声明，否则中文显示方框：

```css
@font-face {
  font-family: 'NotoSC';
  src: url('file:///data/data/com.termux/files/home/NotoSansCJKSC-Regular.ttf');
}
body { font-family: 'NotoSC', sans-serif; }
```

```python
from weasyprint import HTML
HTML('/path/to/article.html').write_pdf('/path/to/article.pdf')
```

## 常见问题

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| pip install Pillow超时 | 需编译C扩展 | 用pkg install python-pillow + symlink到venv |
| PDF中文显示方框 | 未嵌入字体 | HTML中加@font-face声明NotoSC |
| weasyprint import失败 | 缺少pyphen等依赖 | pip install --no-deps逐个安装 |
| ModuleNotFoundError: PIL | venv与系统site-packages隔离 | ln -sf symlink PIL到venv |
| .ttc字体无法用于@font-face | WeasyPrint需要.ttf | 用fontTools提取单个字体文件 |
| 结论跨页断裂 | PDF分页切断了div | CSS加break-inside:avoid; page-break-inside:avoid |
