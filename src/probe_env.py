"""
probe_env.py

Reports what the training machine actually has, so the rest of the
pipeline can be written against real facts instead of assumptions.

Uses only the Python standard library, except that DICOM inspection
needs pydicom — if it isn't installed the script still runs and just
skips that section.

What it reports:
1. OS / Python / CPU / free disk
2. GPU (via nvidia-smi) and whether torch sees CUDA
3. Which pipeline packages are installed, and at what version
4. A scan of the dataset folder: patient count, modalities present,
   CT slices per patient, and the ROI names inside each RTSTRUCT

Usage:
    python probe_env.py <path-to-dataset-dir>

    e.g.  python probe_env.py D:\\datasets\\nsclc_radiomics
          python probe_env.py ~/datasets/nsclc_radiomics

If no path is given it just skips the dataset scan and reports the
environment only.
"""

import os
import sys
import glob
import shutil
import platform
import subprocess


# how many patient folders to inspect in detail (full scan of every
# patient would mean opening tens of thousands of files)
PATIENTS_TO_INSPECT = 3


def section(title):
    print()
    print("=" * 62)
    print(title)
    print("=" * 62)


def report_system():
    section("1. SYSTEM")
    print(f"OS               : {platform.system()} {platform.release()}")
    print(f"Platform         : {platform.platform()}")
    print(f"Machine          : {platform.machine()}")
    print(f"Python           : {sys.version.split()[0]}  ({sys.executable})")
    print(f"CPU cores        : {os.cpu_count()}")
    try:
        total, used, free = shutil.disk_usage(os.path.expanduser("~"))
        gb = 1024 ** 3
        print(f"Disk (home)      : {free // gb} GB free of {total // gb} GB")
    except OSError as e:
        print(f"Disk (home)      : unavailable ({e})")


def report_gpu():
    section("2. GPU")
    try:
        out = subprocess.run(
            ["nvidia-smi",
             "--query-gpu=name,memory.total,driver_version",
             "--format=csv,noheader"],
            capture_output=True, text=True, timeout=30,
        )
        if out.returncode == 0 and out.stdout.strip():
            for line in out.stdout.strip().splitlines():
                print(f"nvidia-smi       : {line.strip()}")
        else:
            print("nvidia-smi       : ran but returned nothing useful")
            if out.stderr.strip():
                print(f"                   {out.stderr.strip().splitlines()[0]}")
    except FileNotFoundError:
        print("nvidia-smi       : NOT FOUND (no NVIDIA driver on PATH)")
    except subprocess.TimeoutExpired:
        print("nvidia-smi       : timed out")

    try:
        import torch
        print(f"torch            : {torch.__version__}")
        print(f"torch CUDA build : {torch.version.cuda}")
        print(f"torch.cuda avail : {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            for i in range(torch.cuda.device_count()):
                props = torch.cuda.get_device_properties(i)
                vram = props.total_memory / 1024 ** 3
                print(f"  device {i}      : {props.name}  ({vram:.1f} GB VRAM)")
    except ImportError:
        print("torch            : not installed")


def report_packages():
    section("3. PIPELINE PACKAGES")
    # (import name, what stage needs it)
    wanted = [
        ("numpy",       "everything"),
        ("pydicom",     "stage 2  DICOM/RTSTRUCT extraction"),
        ("PIL",         "stage 2  contour rasterisation"),
        ("cv2",         "stage 3  enhancement"),
        ("skimage",     "stage 3/4  adaptive equalisation, morphology"),
        ("scipy",       "stage 4  morphological reconstruction"),
        ("torch",       "stage 5  U-Net"),
        ("sklearn",     "stage 7/8  stacking, classifier fusion"),
        ("matplotlib",  "stage 9  figures"),
        ("skimage.measure", "stage 9  marching cubes"),
    ]
    for name, why in wanted:
        try:
            mod = __import__(name, fromlist=["__version__"])
            ver = getattr(mod, "__version__", "(no __version__)")
            print(f"  {name:18s} {ver:18s} {why}")
        except ImportError:
            print(f"  {name:18s} {'MISSING':18s} {why}")


def dicom_summary(patient_dir):
    """Open every .dcm under one patient and tally modalities + ROI names."""
    import pydicom

    counts = {}
    roi_names = []
    rtstruct_files = []

    dcms = glob.glob(os.path.join(patient_dir, "**", "*.dcm"), recursive=True)
    for path in dcms:
        try:
            ds = pydicom.dcmread(path, stop_before_pixels=True)
        except Exception:
            counts["UNREADABLE"] = counts.get("UNREADABLE", 0) + 1
            continue
        modality = getattr(ds, "Modality", "UNKNOWN")
        counts[modality] = counts.get(modality, 0) + 1
        if modality == "RTSTRUCT":
            rtstruct_files.append(path)

    # read ROI names out of the first RTSTRUCT found
    for path in rtstruct_files[:1]:
        try:
            ds = pydicom.dcmread(path)
            for roi in getattr(ds, "StructureSetROISequence", []):
                roi_names.append(str(getattr(roi, "ROIName", "?")))
        except Exception as e:
            roi_names.append(f"<could not read: {e}>")

    return len(dcms), counts, roi_names


def report_dataset(dataset_dir):
    section("4. DATASET")
    dataset_dir = os.path.abspath(os.path.expanduser(dataset_dir))
    print(f"Path             : {dataset_dir}")

    if not os.path.isdir(dataset_dir):
        print("  -> DOES NOT EXIST or is not a directory")
        return

    entries = sorted(
        d for d in os.listdir(dataset_dir)
        if os.path.isdir(os.path.join(dataset_dir, d))
    )
    print(f"Subfolders       : {len(entries)}")
    print(f"First few        : {entries[:8]}")

    all_dcm = glob.glob(os.path.join(dataset_dir, "**", "*.dcm"), recursive=True)
    all_png = glob.glob(os.path.join(dataset_dir, "**", "*.png"), recursive=True)
    all_nii = glob.glob(os.path.join(dataset_dir, "**", "*.nii*"), recursive=True)
    print(f".dcm files       : {len(all_dcm)}")
    print(f".png files       : {len(all_png)}")
    print(f".nii/.nii.gz     : {len(all_nii)}")

    if not all_dcm:
        print()
        print("  No DICOM found -> this is NOT the raw TCIA download.")
        return

    try:
        import pydicom  # noqa: F401
    except ImportError:
        print()
        print("  pydicom not installed, so modality/ROI detail is skipped.")
        print("  Install it and re-run to get the full picture:")
        print("      pip install pydicom")
        return

    print()
    print(f"Inspecting the first {PATIENTS_TO_INSPECT} patient folders in detail:")
    for name in entries[:PATIENTS_TO_INSPECT]:
        pdir = os.path.join(dataset_dir, name)
        n, counts, rois = dicom_summary(pdir)
        modality_str = ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
        print()
        print(f"  {name}")
        print(f"    .dcm files   : {n}")
        print(f"    modalities   : {modality_str or '(none)'}")
        if rois:
            print(f"    ROI names    : {rois}")
        else:
            print(f"    ROI names    : (no RTSTRUCT found)")


def main():
    print("probe_env.py — reporting what this machine has")
    report_system()
    report_gpu()
    report_packages()

    if len(sys.argv) > 1:
        report_dataset(sys.argv[1])
    else:
        section("4. DATASET")
        print("No dataset path given. Re-run as:")
        print("    python probe_env.py <path-to-dataset-dir>")

    print()
    print("Done. Paste this whole output back.")


if __name__ == "__main__":
    main()
