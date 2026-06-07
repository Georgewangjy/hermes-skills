#!/usr/bin/env python3
"""
宏观数据速评文章 HTML → PDF 转换器
使用 WeasyPrint 渲染，保持HTML排版原样
"""
import sys
import os

def html_to_pdf(html_path, pdf_path=None):
    """将HTML文件转换为PDF，嵌入中文字体"""
    from weasyprint import HTML
    
    if pdf_path is None:
        pdf_path = html_path.replace('.html', '.pdf')
    
    HTML(html_path).write_pdf(pdf_path)
    print(f"PDF generated: {pdf_path}")
    print(f"Size: {os.path.getsize(pdf_path)/1024:.0f}KB")
    return pdf_path

def ensure_font():
    """确保中文字体已提取"""
    font_path = os.path.expanduser("~/NotoSansCJKSC-Regular.ttf")
    if not os.path.exists(font_path):
        print("Extracting Chinese font...")
        from fontTools.ttLib import TTCollection
        ttc_path = "/system/fonts/NotoSansCJK-Regular.ttc"
        if not os.path.exists(ttc_path):
            print("ERROR: CJK font not found on system")
            return False
        ttc = TTCollection(ttc_path)
        ttc.fonts[2].save(font_path)  # Index 2 = SC (Simplified Chinese)
        print(f"Font extracted: {font_path}")
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python html2pdf.py <input.html> [output.pdf]")
        sys.exit(1)
    
    ensure_font()
    html_path = sys.argv[1]
    pdf_path = sys.argv[2] if len(sys.argv) > 2 else None
    html_to_pdf(html_path, pdf_path)
