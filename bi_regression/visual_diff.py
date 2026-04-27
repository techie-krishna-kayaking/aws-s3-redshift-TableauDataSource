"""
visual_diff.py — SSIM-based image comparison with annotated side-by-side output.

Returns a DiffResult dataclass so callers have structured access to
scores, paths, and pass/fail status.
"""
from __future__ import annotations

import cv2
import numpy as np
from dataclasses import dataclass
from pathlib import Path
from skimage.metrics import structural_similarity as ssim
from PIL import Image, ImageDraw, ImageFont


@dataclass
class DiffResult:
    tab_name: str
    passed: bool            # True if SSIM >= threshold
    ssim_score: float       # 0.0 – 1.0
    baseline_path: str      # Path to baseline screenshot
    target_path: str        # Path to target screenshot
    diff_path: str          # Path to side-by-side diff composite
    diff_pixel_count: int = 0
    label_a: str = "Baseline"
    label_b: str = "Target"
    scenario_label: str = ""  # Filter scenario label (empty = no filters)


def compare_images(
    baseline_path: str,
    target_path: str,
    diff_output_path: str,
    threshold: float = 0.98,
    tab_name: str = "Page",
    label_a: str = "Baseline",
    label_b: str = "Target",
) -> DiffResult:
    """
    Compare two dashboard screenshots using SSIM.

    Args:
        baseline_path:   Path to the first (baseline) screenshot.
        target_path:     Path to the second (target) screenshot.
        diff_output_path: Where to save the annotated side-by-side image.
        threshold:       SSIM score below this value → FAIL.
        tab_name:        Tab/page name for labelling.
        label_a/label_b: Human-readable labels for the two dashboards.

    Returns:
        DiffResult with pass/fail status, score, and paths.
    """
    img1_bgr = cv2.imread(str(baseline_path))
    img2_bgr = cv2.imread(str(target_path))

    if img1_bgr is None:
        raise FileNotFoundError(f"Cannot read baseline image: {baseline_path}")
    if img2_bgr is None:
        raise FileNotFoundError(f"Cannot read target image: {target_path}")

    # ---- Resize target to match baseline dimensions (best-effort) --------
    if img1_bgr.shape != img2_bgr.shape:
        img2_bgr = cv2.resize(img2_bgr, (img1_bgr.shape[1], img1_bgr.shape[0]))

    gray1 = cv2.cvtColor(img1_bgr, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(img2_bgr, cv2.COLOR_BGR2GRAY)

    score, diff = ssim(gray1, gray2, full=True)
    diff_uint8 = (diff * 255).astype("uint8")

    # ---- Find difference contours ----------------------------------------
    thresh = cv2.threshold(
        diff_uint8, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU
    )[1]
    contours, _ = cv2.findContours(
        thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )

    img2_annotated = img2_bgr.copy()
    diff_pixel_count = 0

    for c in contours:
        area = cv2.contourArea(c)
        if area > 30:  # ignore tiny noise
            diff_pixel_count += int(area)
            x, y, w, h = cv2.boundingRect(c)
            cv2.rectangle(img2_annotated, (x, y), (x + w, y + h), (0, 0, 255), 2)

    passed = score >= threshold

    # ---- Build side-by-side composite with header labels -----------------
    composite = _build_side_by_side(
        img1_bgr,
        img2_annotated,
        score=score,
        passed=passed,
        label_a=label_a,
        label_b=label_b,
        tab_name=tab_name,
    )
    cv2.imwrite(str(diff_output_path), composite)

    return DiffResult(
        tab_name=tab_name,
        passed=passed,
        ssim_score=round(score, 4),
        baseline_path=str(baseline_path),
        target_path=str(target_path),
        diff_path=str(diff_output_path),
        diff_pixel_count=diff_pixel_count,
        label_a=label_a,
        label_b=label_b,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_side_by_side(
    img_a: np.ndarray,
    img_b: np.ndarray,
    score: float,
    passed: bool,
    label_a: str,
    label_b: str,
    tab_name: str,
    header_height: int = 60,
) -> np.ndarray:
    """
    Produces a horizontally stacked image:
      [Header banner]
      [ label_a image  |  label_b image ]
    """
    h, w = img_a.shape[:2]
    total_w = w * 2
    total_h = h + header_height

    # Background canvas
    canvas = np.zeros((total_h, total_w, 3), dtype=np.uint8)
    canvas[:] = (30, 30, 30)  # dark background

    # Header bar
    status_color = (0, 180, 0) if passed else (0, 0, 220)  # BGR
    canvas[:header_height, :] = status_color

    # Place images
    canvas[header_height:, :w] = img_a
    canvas[header_height:, w:] = img_b

    # Draw divider line
    cv2.line(canvas, (w, header_height), (w, total_h), (200, 200, 200), 2)

    # Annotate with Pillow (better font rendering)
    pil = Image.fromarray(cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil)

    try:
        font_big = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 22)
        font_sm  = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 16)
    except Exception:
        font_big = ImageFont.load_default()
        font_sm  = font_big

    status_text = "PASS ✓" if passed else "FAIL ✗"
    header_text = f"{tab_name}  |  SSIM: {score:.4f}  |  {status_text}"
    draw.text((20, 15), header_text, fill=(255, 255, 255), font=font_big)
    draw.text((20, header_height + 8), label_a, fill=(220, 220, 220), font=font_sm)
    draw.text((w + 20, header_height + 8), label_b, fill=(220, 220, 220), font=font_sm)

    return cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)


def create_missing_tab_image(
    tab_name: str,
    reason: str,
    output_path: str,
    width: int = 1920,
    height: int = 1080,
) -> str:
    """
    Generate a placeholder 'MISSING TAB' image when a tab does not exist
    in one of the two dashboards.
    """
    img = Image.new("RGB", (width, height), color=(40, 40, 40))
    draw = ImageDraw.Draw(img)

    try:
        font_lg = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 48)
        font_md = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 28)
    except Exception:
        font_lg = ImageFont.load_default()
        font_md = font_lg

    draw.text((width // 2, height // 2 - 60), f"TAB NOT FOUND",
              fill=(220, 50, 50), font=font_lg, anchor="mm")
    draw.text((width // 2, height // 2),      f"Tab: {tab_name}",
              fill=(200, 200, 200), font=font_md, anchor="mm")
    draw.text((width // 2, height // 2 + 50), reason,
              fill=(180, 180, 0), font=font_md, anchor="mm")

    img.save(str(output_path))
    return str(output_path)
