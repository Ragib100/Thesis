"""
extract_tumor_slices.py

Extract tumor-containing views (axial, coronal, sagittal — like 3D Slicer's
3-pane view) from the NSCLC-Radiomics (TCIA) dataset, using RTSTRUCT
contours to know exactly where the tumor is, and save them as PNGs with
the tumor outlined/highlighted.

How it works:
1. Load every CT slice for a patient into one 3D volume (z, y, x).
2. Read the RTSTRUCT, find the tumor ROI (e.g. "GTV-1"), and rasterize
   its contours into a matching 3D binary mask volume.
3. Rank slices along each of the 3 axes (axial=z, coronal=y, sagittal=x)
   by how much tumor they contain, and pick the top few per axis.
4. Save each chosen slice as a PNG with the tumor mask outlined in red.

Install deps:
    pip install pydicom numpy matplotlib Pillow --break-system-packages

Usage:
    Edit the CONFIG block below, then just run:
        python extract_tumor_slices.py

Expected structure (typical TCIA download):
    dataset-dir/
        LUNG1-001/
            <study-uid>/
                <series-uid-1>/  (CT slices, many .dcm files)
                <series-uid-2>/  (RTSTRUCT, usually a single .dcm file)
                <series-uid-3>/  (RTDOSE/RTPLAN, ignored)
        LUNG1-002/
            ...

The script does NOT rely on folder names — it opens every .dcm file and
checks the Modality tag (CT / RTSTRUCT / RTDOSE / RTPLAN) itself.
"""

import argparse
import os
import glob
from dataclasses import dataclass, field

import numpy as np
import pydicom
from PIL import Image, ImageDraw
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


# ---------------------------------------------------------------------
# EDIT THESE VALUES TO MATCH YOUR SETUP
# ---------------------------------------------------------------------
DATASET_DIR = "../image dataset/nsclc_radiomics"  # folder containing one subfolder per patient
NUM_PATIENTS = 6                            # how many patients to process
VIEWS_PER_PLANE = 6                         # how many slices per plane (axial/coronal/sagittal)
                                             # e.g. 6 -> 6 axial + 6 coronal + 6 sagittal = 18 images/patient
OUT_DIR = "./tumor_slices"                  # where to save the output PNGs
WINDOW = "soft"                             # "soft" (soft tissue) or "lung"
# ---------------------------------------------------------------------


TUMOR_ROI_KEYWORDS = ["gtv", "tumor", "tumour", "nodule", "ctv"]


@dataclass
class PatientData:
    patient_id: str
    ct_files: dict = field(default_factory=dict)  # SOPInstanceUID -> filepath
    rtstruct_path: str = None


def find_patient_data(patient_dir: str) -> PatientData:
    pid = os.path.basename(os.path.normpath(patient_dir))
    data = PatientData(patient_id=pid)

    dcm_files = glob.glob(os.path.join(patient_dir, "**", "*.dcm"), recursive=True)
    if not dcm_files:
        dcm_files = [
            os.path.join(root, f)
            for root, _, files in os.walk(patient_dir)
            for f in files
        ]

    for fp in dcm_files:
        try:
            ds = pydicom.dcmread(fp, stop_before_pixels=True, force=True)
        except Exception:
            continue

        modality = getattr(ds, "Modality", None)
        if modality == "CT":
            sop_uid = getattr(ds, "SOPInstanceUID", None)
            if sop_uid:
                data.ct_files[sop_uid] = fp
        elif modality == "RTSTRUCT":
            data.rtstruct_path = fp

    return data


def find_tumor_roi_number(rtstruct: pydicom.Dataset):
    candidates = []
    for roi in rtstruct.StructureSetROISequence:
        name = (roi.ROIName or "").lower()
        if any(kw in name for kw in TUMOR_ROI_KEYWORDS):
            candidates.append((roi.ROINumber, roi.ROIName))

    if not candidates:
        return None, None

    for num, name in candidates:
        if "gtv" in name.lower():
            return num, name

    return candidates[0]


def load_ct_volume(ct_files: dict):
    """
    Load all CT slices into a single 3D volume, sorted by z position.

    Returns:
        volume: np.ndarray (num_slices, rows, cols) in Hounsfield Units
        sop_uid_by_z: list of SOPInstanceUID, index = z-index in volume
        spacing: (dz, dy, dx) in mm
        pixel_spacing: (row_spacing, col_spacing) in mm (dy, dx)
    """
    entries = []
    for sop_uid, fp in ct_files.items():
        ds = pydicom.dcmread(fp)
        z = float(ds.ImagePositionPatient[2])
        entries.append((z, sop_uid, ds))

    entries.sort(key=lambda e: e[0])  # ascending z

    rows, cols = entries[0][2].pixel_array.shape
    num_slices = len(entries)
    volume = np.zeros((num_slices, rows, cols), dtype=np.float32)
    sop_uid_by_z = []

    z_positions = []
    for i, (z, sop_uid, ds) in enumerate(entries):
        slope = float(getattr(ds, "RescaleSlope", 1))
        intercept = float(getattr(ds, "RescaleIntercept", 0))
        volume[i] = ds.pixel_array.astype(np.float32) * slope + intercept
        sop_uid_by_z.append(sop_uid)
        z_positions.append(z)

    dy, dx = [float(v) for v in entries[0][2].PixelSpacing]
    z_diffs = np.diff(z_positions)
    dz = float(np.median(z_diffs)) if len(z_diffs) > 0 else float(
        getattr(entries[0][2], "SliceThickness", 1.0)
    )

    return volume, sop_uid_by_z, (abs(dz), dy, dx)


def world_to_pixel(points_xyz, ct_ds):
    origin = np.array(ct_ds.ImagePositionPatient, dtype=float)
    spacing = np.array(ct_ds.PixelSpacing, dtype=float)  # [row_spacing, col_spacing]
    pts = np.array(points_xyz, dtype=float)

    col = (pts[:, 0] - origin[0]) / spacing[1]
    row = (pts[:, 1] - origin[1]) / spacing[0]
    return np.stack([col, row], axis=1)  # (x_pixel, y_pixel)


def build_tumor_mask_volume(rtstruct, roi_number, ct_files, sop_uid_by_z, volume_shape):
    """Rasterize RTSTRUCT contours for the tumor ROI into a 3D boolean mask."""
    sop_to_z = {uid: i for i, uid in enumerate(sop_uid_by_z)}
    num_slices, rows, cols = volume_shape
    mask_volume = np.zeros((num_slices, rows, cols), dtype=bool)

    # A slice usually carries several contour loops, and every one of them
    # needs the same ImagePositionPatient / PixelSpacing to map world mm to
    # pixels. Read each CT header once and keep it, instead of re-reading the
    # file per contour — that re-read dominates runtime over a full dataset.
    header_cache = {}

    def ct_header(uid):
        if uid not in header_cache:
            header_cache[uid] = pydicom.dcmread(ct_files[uid], stop_before_pixels=True)
        return header_cache[uid]

    any_contour = False
    for roi_contour in rtstruct.ROIContourSequence:
        if roi_contour.ReferencedROINumber != roi_number:
            continue
        if not hasattr(roi_contour, "ContourSequence"):
            continue

        for contour in roi_contour.ContourSequence:
            if not hasattr(contour, "ContourImageSequence"):
                continue
            ref_uid = contour.ContourImageSequence[0].ReferencedSOPInstanceUID
            if ref_uid not in sop_to_z or ref_uid not in ct_files:
                continue

            z_idx = sop_to_z[ref_uid]
            flat = np.array(contour.ContourData, dtype=float).reshape(-1, 3)

            px = world_to_pixel(flat, ct_header(ref_uid))

            if len(px) < 3:
                continue

            img = Image.new("L", (cols, rows), 0)
            ImageDraw.Draw(img).polygon([tuple(p) for p in px], outline=1, fill=1)
            slice_mask = np.array(img, dtype=bool)
            mask_volume[z_idx] |= slice_mask
            any_contour = True

    return mask_volume if any_contour else None


def apply_window(hu_array, level, width):
    lo = level - width / 2
    hi = level + width / 2
    windowed = np.clip(hu_array, lo, hi)
    windowed = (windowed - lo) / (hi - lo) * 255.0
    return windowed.astype(np.uint8)


def top_indices_by_score(scores: np.ndarray, n: int):
    order = np.argsort(scores)[::-1]
    order = [i for i in order if scores[i] > 0]
    return order[:n]


def save_view(image_2d, mask_2d, aspect, out_path, title, window):
    if window == "lung":
        level, width = -600, 1500
    else:
        level, width = 40, 400

    img = apply_window(image_2d, level, width)

    fig, ax = plt.subplots(figsize=(6, 6))
    ax.imshow(img, cmap="gray", aspect=aspect)
    if mask_2d.any():
        # translucent fill
        overlay = np.zeros((*mask_2d.shape, 4), dtype=np.float32)
        overlay[mask_2d] = [1, 0, 0, 0.30]  # red, semi-transparent
        ax.imshow(overlay, aspect=aspect)
        # outline
        ax.contour(mask_2d, levels=[0.5], colors="red", linewidths=1.5)
    ax.set_title(title, fontsize=8)
    ax.axis("off")
    fig.savefig(out_path, bbox_inches="tight", dpi=150)
    plt.close(fig)


def process_patient(patient_dir, out_dir, views_per_plane=2, window="soft"):
    data = find_patient_data(patient_dir)

    if not data.ct_files:
        print(f"[skip] {data.patient_id}: no CT slices found")
        return 0
    if not data.rtstruct_path:
        print(f"[skip] {data.patient_id}: no RTSTRUCT found")
        return 0

    rtstruct = pydicom.dcmread(data.rtstruct_path)
    roi_number, roi_name = find_tumor_roi_number(rtstruct)
    if roi_number is None:
        available = [r.ROIName for r in rtstruct.StructureSetROISequence]
        print(f"[skip] {data.patient_id}: no tumor-like ROI found (available: {available})")
        return 0

    volume, sop_uid_by_z, (dz, dy, dx) = load_ct_volume(data.ct_files)
    mask_volume = build_tumor_mask_volume(
        rtstruct, roi_number, data.ct_files, sop_uid_by_z, volume.shape
    )

    if mask_volume is None:
        print(f"[skip] {data.patient_id}: ROI '{roi_name}' has no usable contours")
        return 0

    patient_out_dir = os.path.join(out_dir, data.patient_id)
    os.makedirs(patient_out_dir, exist_ok=True)
    saved = 0

    axial_scores = mask_volume.sum(axis=(1, 2))
    coronal_scores = mask_volume.sum(axis=(0, 2))
    sagittal_scores = mask_volume.sum(axis=(0, 1))

    axial_idx = top_indices_by_score(axial_scores, views_per_plane)
    coronal_idx = top_indices_by_score(coronal_scores, views_per_plane)
    sagittal_idx = top_indices_by_score(sagittal_scores, views_per_plane)

    n = max(len(axial_idx), len(coronal_idx), len(sagittal_idx))

    for rank in range(n):
        image_dir = os.path.join(patient_out_dir, f"image_{rank+1:02d}")
        os.makedirs(image_dir, exist_ok=True)

        if rank < len(axial_idx):
            z = axial_idx[rank]
            out_path = os.path.join(image_dir, "axial.png")
            save_view(
                volume[z, :, :], mask_volume[z, :, :], aspect=dy / dx,
                out_path=out_path, title=f"{data.patient_id} axial (z={z})", window=window,
            )
            saved += 1

        if rank < len(coronal_idx):
            y = coronal_idx[rank]
            out_path = os.path.join(image_dir, "coronal.png")
            img_slice = np.flipud(volume[:, y, :])       # z on vertical axis, head at top
            mask_slice = np.flipud(mask_volume[:, y, :])
            save_view(
                img_slice, mask_slice, aspect=dz / dx,
                out_path=out_path, title=f"{data.patient_id} coronal (y={y})", window=window,
            )
            saved += 1

        if rank < len(sagittal_idx):
            x = sagittal_idx[rank]
            out_path = os.path.join(image_dir, "sagittal.png")
            img_slice = np.flipud(volume[:, :, x])        # z on vertical axis, head at top
            mask_slice = np.flipud(mask_volume[:, :, x])
            save_view(
                img_slice, mask_slice, aspect=dz / dy,
                out_path=out_path, title=f"{data.patient_id} sagittal (x={x})", window=window,
            )
            saved += 1

    print(f"[ok] {data.patient_id}: ROI '{roi_name}', saved {saved} image(s) -> {patient_out_dir}")
    return saved


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dataset-dir", default=DATASET_DIR)
    ap.add_argument("--num-patients", type=int, default=NUM_PATIENTS)
    ap.add_argument("--views-per-plane", type=int, default=VIEWS_PER_PLANE)
    ap.add_argument("--out-dir", default=OUT_DIR)
    ap.add_argument("--window", choices=["soft", "lung"], default=WINDOW)
    args = ap.parse_args()

    patient_dirs = sorted(
        d for d in glob.glob(os.path.join(args.dataset_dir, "*"))
        if os.path.isdir(d)
    )

    os.makedirs(args.out_dir, exist_ok=True)

    done = 0
    for pdir in patient_dirs:
        if done >= args.num_patients:
            break
        n = process_patient(pdir, args.out_dir, args.views_per_plane, args.window)
        if n > 0:
            done += 1

    print(f"\nFinished. {done} patient(s) processed into: {args.out_dir}")


if __name__ == "__main__":
    main()