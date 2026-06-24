#!/usr/bin/env python3
"""ocr: 图片文字识别，输出Markdown格式。

基于讯飞星辰MaaS平台的Kimi K2.6多模态视觉模型。

用法:
    python ocr.py /path/to/image.png
    python ocr.py /path/to/image.png --mode table_focus
    python ocr.py /path/to/image.png --mode financial
"""

import argparse
import base64
import json
import logging
import os
import sys

from openai import OpenAI
from PIL import Image

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.join(SCRIPT_DIR, "..")
CONFIG_PATH = os.path.join(SKILL_DIR, "config.json")

FORMAT_TO_MIME = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "bmp": "image/bmp",
    "webp": "image/webp",
    "gif": "image/gif",
}


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_image(image_path: str, config: dict) -> dict:
    """验证图片文件，返回错误dict或图片信息。"""
    if not os.path.isfile(image_path):
        return {"error": "file_not_found", "path": image_path}

    ext = os.path.splitext(image_path)[1].lstrip(".").lower()
    supported = config.get("ocr", {}).get("supported_formats", [])
    if ext not in supported:
        return {"error": "unsupported_format", "format": ext}

    max_mb = config.get("ocr", {}).get("max_image_size_mb", 10)
    size_mb = os.path.getsize(image_path) / (1024 * 1024)
    if size_mb > max_mb:
        return {"error": "file_too_large", "size_mb": round(size_mb, 2), "limit_mb": max_mb}

    return {"ext": ext}


def resize_if_needed(image_path: str, config: dict) -> tuple[bytes, str]:
    """如果图片超过最大尺寸则缩放，返回(image_bytes, format)。"""
    max_dim = config.get("ocr", {}).get("max_image_dimension", 2048)
    img = Image.open(image_path)

    # 处理RGBA/P模式，转为RGB
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    need_resize = max(img.size) > max_dim
    if need_resize:
        ratio = max_dim / max(img.size)
        new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
        img = img.resize(new_size, Image.Resampling.LANCZOS)
        logger.info("图片缩放: %s -> %s", img.size, new_size)

    fmt = img.format or "PNG"
    if fmt.upper() == "JPG":
        fmt = "JPEG"

    import io
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue(), fmt.lower()


def image_to_base64_url(image_path: str, config: dict) -> tuple[str, str]:
    """将图片转为base64 data URL，返回(data_url, format)。"""
    img_bytes, fmt = resize_if_needed(image_path, config)
    mime = FORMAT_TO_MIME.get(fmt, "image/png")
    b64 = base64.b64encode(img_bytes).decode()
    return f"data:{mime};base64,{b64}", fmt


def run_ocr(image_path: str, mode: str = "default") -> dict:
    """执行OCR识别。"""
    config = load_config()

    # 验证图片
    validation = validate_image(image_path, config)
    if "error" in validation:
        return validation

    # 获取API Key
    api_config = config.get("api", {})
    api_key_env = api_config.get("api_key_env", "XUNFEI_MAAK_API_KEY")
    api_key = os.environ.get(api_key_env, "")
    if not api_key:
        return {"error": "missing_api_key", "env_var": api_key_env}

    # 图片转base64
    logger.info("处理图片: %s", image_path)
    data_url, _ = image_to_base64_url(image_path, config)

    # 选择prompt
    prompts = config.get("prompts", {})
    prompt_text = prompts.get(mode, prompts.get("default", "请识别图片中的文字"))

    # 构建消息
    messages = [{
        "role": "user",
        "content": [
            {"type": "text", "text": prompt_text},
            {"type": "image_url", "image_url": {"url": data_url}},
        ],
    }]

    # 调用API
    logger.info("调用Kimi K2.6视觉模型，模式: %s", mode)
    try:
        client = OpenAI(
            api_key=api_key,
            base_url=api_config.get("base_url"),
        )
        ocr_config = config.get("ocr", {})
        timeout = api_config.get("timeout_seconds", 120)
        response = client.chat.completions.create(
            model=api_config.get("model", "xopkimik26"),
            messages=messages,
            max_tokens=ocr_config.get("max_tokens", 4000),
            temperature=ocr_config.get("temperature", 0.1),
            timeout=timeout,
        )
        content = response.choices[0].message.content
        logger.info("OCR识别完成")
        return {"markdown": content}
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("API调用失败: %s", e)
        return {"error": "api_error", "message": str(e)}


def main():
    parser = argparse.ArgumentParser(description="ocr: 图片文字识别，输出Markdown格式")
    parser.add_argument("image_path", help="图片文件路径")
    parser.add_argument("--mode", choices=["default", "table_focus", "financial"],
                        default="default", help="识别模式（默认: default）")
    args = parser.parse_args()

    result = run_ocr(args.image_path, args.mode)

    if "error" in result:
        print(json.dumps(result, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)

    print(result["markdown"])


if __name__ == "__main__":
    main()
