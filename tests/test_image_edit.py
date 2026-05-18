"""tests/test_image_edit.py — 图片编辑模块单元测试"""

import base64
import io
from PIL import Image


def test_find_mask_region_finds_painted_area(sample_mask_uri):
    """验证 find_mask_region 能正确检测涂抹区域边界"""
    from api.routers.image_gen import find_mask_region

    header, b64 = sample_mask_uri.split(",", 1)
    mask_img = Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGBA")
    x1, y1, x2, y2 = find_mask_region(mask_img)
    assert x1 >= 75 and x1 <= 80, f"x1={x1} 预期≈75"
    assert y1 >= 75 and y1 <= 80, f"y1={y1} 预期≈75"
    assert x2 >= 120 and x2 <= 125, f"x2={x2} 预期≈124"
    assert y2 >= 120 and y2 <= 125, f"y2={y2} 预期≈124"


def test_find_mask_region_returns_none_for_empty_mask(all_white_mask_uri):
    """全白 mask 应返回 None"""
    from api.routers.image_gen import find_mask_region

    header, b64 = all_white_mask_uri.split(",", 1)
    mask_img = Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGBA")
    result = find_mask_region(mask_img)
    assert result is None


def test_compute_crop_region():
    """验证 compute_crop_region 正确计算 padding 后的裁剪区域"""
    from api.routers.image_gen import compute_crop_region

    result = compute_crop_region(50, 50, 150, 150, img_w=200, img_h=200, padding=0.25)
    # padding = (150-50) * 0.25 = 25
    # x1 = max(0, 50-25) = 25, y1 = ... = 25
    # x2 = min(200, 150+25) = 175, y2 = ... = 175
    assert result == (25, 25, 175, 175), f"结果={result}"


def test_compute_crop_region_clamps_to_image_bounds():
    """验证裁剪区域不会超出图片边界"""
    from api.routers.image_gen import compute_crop_region

    # mask 紧贴边缘 (0, 0, 10, 10)，原图 100x100
    result = compute_crop_region(0, 0, 10, 10, img_w=100, img_h=100, padding=0.5)
    # pad = int(max(20, min(11, 11)*0.5)) = 20
    # cx1 = max(0, -20) = 0, cy1 = 0, cx2 = min(100, 30) = 30, cy2 = 30
    assert result == (0, 0, 30, 30)


def test_analyze_image_basic(sample_image_uri):
    from api.routers.image_gen import _analyze_image_basic

    header, b64 = sample_image_uri.split(",", 1)
    img = Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGBA")
    result = _analyze_image_basic(img, (75, 75, 124, 124))
    assert "dominant_colors" in result
    assert "brightness" in result
    assert result["region_ratio"] > 0


def test_find_mask_region_full_alpha(full_alpha_mask_uri):
    """全透明 mask（全图涂抹）应返回整张图片的边界"""
    from api.routers.image_gen import find_mask_region

    header, b64 = full_alpha_mask_uri.split(",", 1)
    mask_img = Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGBA")
    result = find_mask_region(mask_img)
    assert result is not None
    x1, y1, x2, y2 = result
    assert x1 == 0
    assert y1 == 0
    # 200x200 图片，最大边界
    assert x2 == 199
    assert y2 == 199
