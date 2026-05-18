"""tests/conftest.py — 共享 fixtures"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import base64
import io
import pytest
from PIL import Image, ImageDraw


def _image_to_data_uri(img: Image.Image) -> str:
    """将 PIL Image 转为 data:image/png;base64 URI"""
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{b64}"


@pytest.fixture
def sample_image_png() -> bytes:
    """生成 200x200 的纯色测试图片 PNG 字节"""
    img = Image.new("RGBA", (200, 200), (100, 149, 237, 255))  # cornflower blue
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def sample_image_uri(sample_image_png) -> str:
    """返回 data:image/png;base64,..."""
    b64 = base64.b64encode(sample_image_png).decode("utf-8")
    return f"data:image/png;base64,{b64}"


@pytest.fixture
def sample_mask_uri() -> str:
    """生成 200x200 的 mask：中心 50x50 区域为透明（涂抹区域），其余为白色"""
    img = Image.new("RGBA", (200, 200), (255, 255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.rectangle((75, 75, 124, 124), fill=(255, 255, 255, 0))
    return _image_to_data_uri(img)


@pytest.fixture
def all_white_mask_uri() -> str:
    """全白 mask = 无涂抹区域"""
    img = Image.new("RGBA", (200, 200), (255, 255, 255, 255))
    return _image_to_data_uri(img)


@pytest.fixture
def full_alpha_mask_uri() -> str:
    """全透明 mask = 全图编辑（涂抹了整张图片）"""
    img = Image.new("RGBA", (200, 200), (255, 255, 255, 0))
    return _image_to_data_uri(img)
