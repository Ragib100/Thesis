"""
enhance_images.py

Applies global and local image enhancement to the tumor slice images
produced by extract_tumor_slices.py, while preserving the exact same
folder structure and filenames — so every enhanced image can be traced
back 1:1 to its original.

Input structure (from extract_tumor_slices.py):
    tumor_slices/
        LUNG1-001/
            image_01/
                axial.png
                coronal.png
                sagittal.png
            image_02/
                ...

Output structure (mirrored, same names):
    tumor_slices_global/
        LUNG1-001/
            image_01/
                axial.png
                ...
    tumor_slices_local/
        LUNG1-001/
            image_01/
                axial.png
                ...

Also prints a small contrast/entropy comparison table per image, and
optionally saves side-by-side comparison PNGs for a handful of images
so you can visually judge global vs. local enhancement.

Install deps:
    pip install opencv-python-headless numpy --break-system-packages

Usage:
    Edit the CONFIG block below, then run:
        python enhance_images.py
"""

import os
import glob
import numpy as np
import cv2
from skimage import exposure, img_as_ubyte


# ---------------------------------------------------------------------
# EDIT THESE VALUES
# ---------------------------------------------------------------------
INPUT_DIR = "./tumor_slices"           # output of extract_tumor_slices.py
GLOBAL_OUT_DIR = "./tumor_slices_global"
LOCAL_OUT_DIR = "./tumor_slices_local"

# Local enhancement settings (scikit-image adaptive histogram equalization,
# which interpolates between tiles and looks noticeably cleaner than
# OpenCV's blockier CLAHE — see comparison notes)
DENOISE_BEFORE_LOCAL = True   # light denoise pass before local enhancement
DENOISE_STRENGTH = 6          # higher = smoother but less detail (try 4-10)
CLAHE_CLIP_LIMIT = 0.02       # scikit-image scale: roughly 0.005 (subtle) to 0.03 (strong)

# How many sample images to also save as original|global|local comparisons
# (None = generate comparisons for every image, mirroring tumor_slices structure)
COMPARISON_OUT_DIR = "./enhancement_comparisons"
# ---------------------------------------------------------------------


LABEL_FONT = cv2.FONT_HERSHEY_SIMPLEX
LABEL_HEIGHT = 30


def with_label(img_gray: np.ndarray, text: str) -> np.ndarray:
    """Stack a black label bar with white text above a grayscale panel."""
    h, w = img_gray.shape
    bar = np.zeros((LABEL_HEIGHT, w), dtype=np.uint8)
    (tw, th), _ = cv2.getTextSize(text, LABEL_FONT, 0.6, 1)
    x = max((w - tw) // 2, 2)
    y = (LABEL_HEIGHT + th) // 2
    cv2.putText(bar, text, (x, y), LABEL_FONT, 0.6, 255, 1, cv2.LINE_AA)
    return np.vstack([bar, img_gray])


def global_enhance(img_gray: np.ndarray) -> np.ndarray:
    """Global histogram equalization — one transform for the whole image."""
    return cv2.equalizeHist(img_gray)


def local_enhance(img_gray: np.ndarray) -> np.ndarray:
    """Local (adaptive) contrast enhancement via scikit-image's adaptive
    histogram equalization, optionally preceded by a light denoise pass
    so contrast boosting doesn't amplify pixel noise."""
    src = img_gray
    if DENOISE_BEFORE_LOCAL:
        src = cv2.fastNlMeansDenoising(
            src, h=DENOISE_STRENGTH, templateWindowSize=7, searchWindowSize=21
        )
    src_float = src.astype(np.float64) / 255.0
    enhanced = exposure.equalize_adapthist(src_float, clip_limit=CLAHE_CLIP_LIMIT)
    return img_as_ubyte(enhanced)


def entropy(img_gray: np.ndarray) -> float:
    hist = cv2.calcHist([img_gray], [0], None, [256], [0, 256]).flatten()
    p = hist / hist.sum()
    p = p[p > 0]
    return float(-(p * np.log2(p)).sum())


def process_all():
    png_files = sorted(glob.glob(os.path.join(INPUT_DIR, "**", "*.png"), recursive=True))
    if not png_files:
        print(f"No PNG files found under {INPUT_DIR}. Run extract_tumor_slices.py first.")
        return

    print(f"{'file':45s} {'orig_std':>9s} {'global_std':>11s} {'local_std':>10s}"
          f" {'orig_ent':>9s} {'global_ent':>11s} {'local_ent':>10s}")

    for fp in png_files:
        rel_path = os.path.relpath(fp, INPUT_DIR)  # e.g. LUNG1-001/image_01/axial.png

        img = cv2.imread(fp, cv2.IMREAD_GRAYSCALE)
        if img is None:
            print(f"[skip] could not read {fp}")
            continue

        g = global_enhance(img)
        l = local_enhance(img)

        global_out_path = os.path.join(GLOBAL_OUT_DIR, rel_path)
        local_out_path = os.path.join(LOCAL_OUT_DIR, rel_path)
        os.makedirs(os.path.dirname(global_out_path), exist_ok=True)
        os.makedirs(os.path.dirname(local_out_path), exist_ok=True)
        cv2.imwrite(global_out_path, g)
        cv2.imwrite(local_out_path, l)

        print(f"{rel_path:45s} {img.std():9.2f} {g.std():11.2f} {l.std():10.2f}"
              f" {entropy(img):9.3f} {entropy(g):11.3f} {entropy(l):10.3f}")

        # comparison image, mirrored into the same folder structure, labeled
        compare_out_path = os.path.join(COMPARISON_OUT_DIR, rel_path)
        os.makedirs(os.path.dirname(compare_out_path), exist_ok=True)
        h, w = img.shape
        sep = np.full((h + LABEL_HEIGHT, 4), 255, dtype=np.uint8)
        combo = np.hstack([
            with_label(g, "GLOBAL"), sep,
            with_label(img, "INPUT"), sep,
            with_label(l, "LOCAL"),
        ])
        cv2.imwrite(compare_out_path, combo)

    print(f"\nDone. Global -> {GLOBAL_OUT_DIR}, Local -> {LOCAL_OUT_DIR}")
    print(f"Labeled comparisons (same folder structure as {INPUT_DIR}) -> {COMPARISON_OUT_DIR}")


if __name__ == "__main__":
    process_all()