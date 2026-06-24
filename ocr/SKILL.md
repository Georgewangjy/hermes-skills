---
name: ocr
description: 识别图片中的文字内容，整理为Markdown格式输出（基于Kimi K2.6多模态视觉模型）
triggers:
  - OCR识别
  - 图片文字识别
  - ocr
parameters:
  - name: image_path
    description: 图片文件路径，支持 png/jpg/jpeg/bmp/webp/gif 格式
    required: true
  - name: mode
    description: 识别模式：default（通用）/ table_focus（表格聚焦）/ financial（金融文档），默认 default
    required: false
---

# 图片OCR识别

## 执行步骤

1. 读取 `config.json` 获取API配置、OCR参数和prompt模板。
2. 验证图片文件：存在性、格式（supported_formats）、大小（max_image_size_mb）。
3. 大图片自动压缩：超过 max_image_dimension（默认2048px）时按比例缩小。
4. 图片转base64，构建 `data:image/{format};base64,{b64}` 内联URL。
5. 根据mode选择prompt模板，构建OpenAI视觉格式messages。
6. 调用讯飞星辰MaaS平台的Kimi K2.6视觉模型。
7. 输出Markdown格式结果到stdout。

## 识别模式

| 模式 | 说明 | 适用场景 |
|------|------|----------|
| default | 通用文字识别，保留原始结构 | 截图、文档照片、公告 |
| table_focus | 聚焦表格数据，严格MD表格输出 | 数据报表、行情截图 |
| financial | 金融文档识别，金额/百分比保留精度 | 财报、研报、持仓截图 |

## 图片处理

| 项目 | 限制 |
|------|------|
| 最大文件大小 | 10 MB |
| 支持格式 | png, jpg, jpeg, bmp, webp, gif |
| 最大尺寸 | 2048px（超限自动缩放，保持宽高比） |

## 输出格式

成功时输出Markdown文本到stdout，可通过 `> output.md` 重定向到文件。

JSON错误格式：

| 场景 | 输出 |
|------|------|
| 文件不存在 | `{"error": "file_not_found", "path": "..."}` |
| 格式不支持 | `{"error": "unsupported_format", "format": "..."}` |
| 文件过大 | `{"error": "file_too_large", "size_mb": ..., "limit_mb": 10}` |
| API调用失败 | `{"error": "api_error", "message": "..."}` |
| API Key未配置 | `{"error": "missing_api_key", "env_var": "XUNFEI_MAAK_API_KEY"}` |

## 使用示例

```bash
# 通用识别
python scripts/ocr.py /path/to/image.png

# 表格聚焦模式
python scripts/ocr.py /path/to/table.png --mode table_focus

# 金融文档模式
python scripts/ocr.py /path/to/financial_report.jpg --mode financial

# 输出到文件
python scripts/ocr.py /path/to/image.png > output.md
```

## 依赖

- `openai>=1.0`：OpenAI兼容客户端（项目已有）
- `Pillow>=9.0`：图片处理（项目已有）
- API Key：环境变量 `XUNFEI_MAAK_API_KEY`
