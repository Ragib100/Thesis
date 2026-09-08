"""
build_slice_dataset.py

Stage 2b — turn the raw NSCLC-Radiomics DICOM download into a compact,
model-ready slice dataset.

Why this exists alongside extract_tumor_slices.py
-------------------------------------------------
extract_tumor_slices.py produces *pictures for humans*: a handful of
ranked axial/coronal/sagittal PNGs per patient with the tumour painted on
in red. Those are the right output for eyeballing ground truth, and this
script does not replace them.

They cannot train anything, though, for two reasons:
  1. The mask is burned into the pixels. A network fed those images can
     read the answer straight off its own input.
  2. Only the top few slices per plane are kept, so there is no way to
     count the false positives on tumour-free slices that stages 6-8 are
     built around.

This script writes the other half: clean grayscale slices and *separate*
binary masks, for every axial slice of every patient.

Output
------
    out_dir/
        LUNG1-001.npz
        LUNG1-002.npz
        ...
        manifest.csv

Each .npz holds:
    image     uint8   (N, SIZE, SIZE)   windowed CT, 0-255
    mask      uint8   (N, SIZE, SIZE)   1 = tumour (GTV), 0 = background
    z_pos     float32 (N,)              slice z position in mm
    spacing   float32 (3,)              (dz, dy, dx) in mm, resize-corrected
    orig_hw   int32   (2,)              CT rows/cols before resizing

N is every axial slice the patient has, not just the tumour-bearing ones,
so slice-level recall *and* false-positive rate stay measurable.

manifest.csv carries one row per patient (id, ROI name, slice counts,
tumour voxel count, spacing) — enough to sanity-check the dataset without
reopening any .npz.

Intensity windowing
-------------------
The docs use the soft-tissue window (level 40 / width 400) for the display
PNGs, which is right for looking at a tumour. It is the wrong choice for
training input: it clips everything below -160 HU to pure black, so lung
parenchyma, the pleural boundary and the airways all collapse into one
flat value, and the network loses the context that says whether a bright
blob is a tumour or a vessel.

The default here is therefore WINDOW = "wide" (level -300 / width 1400,
i.e. -1000..400 HU), which keeps lung and soft tissue separable in the
same 8-bit image. "soft" and "lung" are still available if you want to
reproduce the original setup exactly.

Install deps:
    pip install pydicom numpy opencv-python-headless Pillow matplotlib

Usage:
    python build_slice_dataset.py --dataset-dir <dicom-root> --out-dir slice_dataset

    On Kaggle, after adding umutkrdrms/nsclc-radiomics as input data:
        python build_slice_dataset.py \\
            --dataset-dir /kaggle/input/nsclc-radiomics/NSCLC-Radiomics \\
            --out-dir /kaggle/working/slice_dataset

Re-running skips patients that already have an .npz, so an interrupted
Kaggle session can be resumed by just running it again.
"""

import os
import sys
import csv
import glob
import time
import argparse

import numpy as np
import cv2
import pydicom

# Reuse the DICOM/RTSTRUCT logic that stage 2 already proved out, rather
# than reimplementing contour rasterisation a second time.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_tumor_slices import (  # noqa: E402
    find_patient_data,
    find_tumor_roi_number,
    load_ct_volume,
    build_tumor_mask_volume,
)


# ---------------------------------------------------------------------
# EDIT THESE VALUES TO MATCH YOUR SETUP
# ---------------------------------------------------------------------
DATASET_DIR = "/kaggle/input/nsclc-radiomics/NSCLC-Radiomics"
OUT_DIR = "/kaggle/working/slice_dataset"
NUM_PATIENTS = 0        # 0 = every patient found
TARGET_SIZE = 256       # slices are resized to TARGET_SIZE x TARGET_SIZE
WINDOW = "wide"         # "wide" (recommended), "soft", or "lung"
# ---------------------------------------------------------------------

WINDOWS = {
    "wide": (-300, 1400),   # -1000..400 HU  — lung + soft tissue together
    "soft": (40, 400),      # -160..240 HU   — what the display PNGs use
    "lung": (-600, 1500),   # -1350..150 HU  — parenchyma detail
}


def window_to_uint8(hu_volume, window):
    """Clip a HU volume to a diagnostic window and rescale to 0-255."""
    level, width = WINDOWS[window]
    lo = level - width / 2.0
    hi = level + width / 2.0
    out = np.clip(hu_volume, lo, hi)
    out = (out - lo) / (hi - lo) * 255.0
    return out.astype(np.uint8)


def resize_stack(images, size, is_mask):
    """
    Resize an (N, H, W) stack to (N, size, size).

    Masks are resized on their float form and re-thresholded at 0.5 rather
    than with nearest-neighbour: nearest drops thin protrusions of the
    contour entirely, which would quietly shrink the ground-truth volume
    that stage 9 measures its 3D Dice against.
    """
    n = images.shape[0]
    out = np.zeros((n, size, size), dtype=np.uint8)
    for i in range(n):
        if is_mask:
            r = cv2.resize(images[i].astype(np.float32), (size, size),
                           interpolation=cv2.INTER_AREA)
            out[i] = (r >= 0.5).astype(np.uint8)
        else:
            out[i] = cv2.resize(images[i], (size, size),
                                interpolation=cv2.INTER_AREA)
    return out


def process_patient(patient_dir, out_dir, size, window):
    """
    Build one patient's .npz. Returns a manifest row dict — with a status
    other than "ok" if the patient had to be skipped, so failures end up
    counted in the manifest instead of only scrolling past in the log.
    """
    pid = os.path.basename(os.path.normpath(patient_dir))
    row = {
        "patient_id": pid, "status": "", "roi_name": "",
        "n_slices": 0, "n_tumor_slices": 0, "tumor_voxels": 0,
        "dz": "", "dy": "", "dx": "", "orig_rows": "", "orig_cols": "",
    }

    data = find_patient_data(patient_dir)
    if not data.ct_files:
        row["status"] = "no_ct"
        return row
    if not data.rtstruct_path:
        row["status"] = "no_rtstruct"
        return row

    rtstruct = pydicom.dcmread(data.rtstruct_path)
    roi_number, roi_name = find_tumor_roi_number(rtstruct)
    if roi_number is None:
        available = [str(r.ROIName) for r in rtstruct.StructureSetROISequence]
        row["status"] = "no_tumor_roi"
        row["roi_name"] = "|".join(available)
        return row
    row["roi_name"] = str(roi_name)

    volume, sop_uid_by_z, (dz, dy, dx) = load_ct_volume(data.ct_files)
    mask_volume = build_tumor_mask_volume(
        rtstruct, roi_number, data.ct_files, sop_uid_by_z, volume.shape
    )
    if mask_volume is None:
        row["status"] = "no_contours"
        return row

    orig_rows, orig_cols = volume.shape[1], volume.shape[2]

    image = resize_stack(window_to_uint8(volume, window), size, is_mask=False)
    mask = resize_stack(mask_volume.astype(np.uint8), size, is_mask=True)

    # In-plane spacing changes with the resize; dz does not. Stage 9 needs
    # the corrected values to reconstruct a volume with true proportions.
    scaled_dy = dy * orig_rows / size
    scaled_dx = dx * orig_cols / size

    z_pos = np.zeros(len(sop_uid_by_z), dtype=np.float32)
    for i, uid in enumerate(sop_uid_by_z):
        ds = pydicom.dcmread(data.ct_files[uid], stop_before_pixels=True)
        z_pos[i] = float(ds.ImagePositionPatient[2])

    np.savez_compressed(
        os.path.join(out_dir, f"{pid}.npz"),
        image=image,
        mask=mask,
        z_pos=z_pos,
        spacing=np.array([dz, scaled_dy, scaled_dx], dtype=np.float32),
        orig_hw=np.array([orig_rows, orig_cols], dtype=np.int32),
    )

    row.update({
        "status": "ok",
        "n_slices": int(image.shape[0]),
        "n_tumor_slices": int((mask.reshape(mask.shape[0], -1).sum(axis=1) > 0).sum()),
        "tumor_voxels": int(mask.sum()),
        "dz": f"{dz:.4f}", "dy": f"{scaled_dy:.4f}", "dx": f"{scaled_dx:.4f}",
        "orig_rows": orig_rows, "orig_cols": orig_cols,
    })
    return row


def main():
    ap = argparse.ArgumentParser(description="Build a model-ready slice dataset.")
    ap.add_argument("--dataset-dir", default=DATASET_DIR)
    ap.add_argument("--out-dir", default=OUT_DIR)
    ap.add_argument("--num-patients", type=int, default=NUM_PATIENTS,
                    help="0 = all")
    ap.add_argument("--size", type=int, default=TARGET_SIZE)
    ap.add_argument("--window", choices=sorted(WINDOWS), default=WINDOW)
    args = ap.parse_args()

    patient_dirs = sorted(
        d for d in glob.glob(os.path.join(args.dataset_dir, "*"))
        if os.path.isdir(d)
    )
    if args.num_patients > 0:
        patient_dirs = patient_dirs[:args.num_patients]

    if not patient_dirs:
        print(f"No patient folders under {args.dataset_dir}")
        return 1

    os.makedirs(args.out_dir, exist_ok=True)
    manifest_path = os.path.join(args.out_dir, "manifest.csv")

    fields = ["patient_id", "status", "roi_name", "n_slices", "n_tumor_slices",
              "tumor_voxels", "dz", "dy", "dx", "orig_rows", "orig_cols"]

    # Resume: keep rows for patients already written, redo everything else.
    done = {}
    if os.path.exists(manifest_path):
        with open(manifest_path, newline="") as f:
            for r in csv.DictReader(f):
                npz = os.path.join(args.out_dir, f"{r['patient_id']}.npz")
                if r["status"] == "ok" and os.path.exists(npz):
                    done[r["patient_id"]] = r
        if done:
            print(f"Resuming — {len(done)} patient(s) already built.")

    print(f"{len(patient_dirs)} patient folder(s) found")
    print(f"window={args.window}  size={args.size}x{args.size}  out={args.out_dir}")
    print()

    rows = []
    t0 = time.time()
    for i, pdir in enumerate(patient_dirs, 1):
        pid = os.path.basename(os.path.normpath(pdir))
        if pid in done:
            rows.append(done[pid])
            continue

        try:
            row = process_patient(pdir, args.out_dir, args.size, args.window)
        except Exception as e:
            row = dict.fromkeys(fields, "")
            row["patient_id"] = pid
            row["status"] = f"error: {type(e).__name__}: {e}"

        rows.append(row)

        elapsed = time.time() - t0
        rate = elapsed / max(i - len(done), 1)
        eta = rate * (len(patient_dirs) - i) / 60.0
        if row["status"] == "ok":
            print(f"[{i:4d}/{len(patient_dirs)}] {pid}  "
                  f"{row['n_tumor_slices']:3d}/{row['n_slices']:3d} tumour slices  "
                  f"ROI={row['roi_name']}  (eta {eta:.0f}m)")
        else:
            print(f"[{i:4d}/{len(patient_dirs)}] {pid}  SKIPPED: {row['status']}")

        # Rewrite the manifest as we go, so a session that dies mid-run
        # still leaves a resumable record behind.
        with open(manifest_path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)

    ok = [r for r in rows if r["status"] == "ok"]
    bad = [r for r in rows if r["status"] != "ok"]

    print()
    print("=" * 62)
    print("SUMMARY")
    print("=" * 62)
    print(f"patients built      : {len(ok)} / {len(rows)}")
    print(f"total slices        : {sum(int(r['n_slices']) for r in ok)}")
    print(f"tumour-bearing      : {sum(int(r['n_tumor_slices']) for r in ok)}")
    if ok:
        share = sum(int(r['n_tumor_slices']) for r in ok) / max(
            sum(int(r['n_slices']) for r in ok), 1)
        print(f"positive slice rate : {share:.1%}")
    roi_names = sorted({r["roi_name"] for r in ok})
    print(f"ROI names used      : {roi_names}")
    if bad:
        print()
        print(f"{len(bad)} patient(s) skipped:")
        for r in bad:
            print(f"  {r['patient_id']:14s} {r['status']}")
    print()
    print(f"manifest -> {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
