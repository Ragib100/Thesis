# Image Extraction

Script: [`src/extract_tumor_slices.py`](../src/extract_tumor_slices.py)

## Objective

Extract tumor-containing views (axial, coronal, sagittal) from the
NSCLC-Radiomics dataset, using the dataset's own radiologist-drawn tumor
contours to know exactly where the tumor is, and save them as PNGs with
the tumor outlined/highlighted — producing the input images that all
later stages (enhancement, morphological processing, segmentation) work
from.

## Why This Step Was Needed

DICOM CT series come as raw slice stacks with no inherent notion of
"where the tumor is" or "which slices matter." Before any enhancement or
segmentation work is meaningful, tumor location needs to be established
from ground truth, and a manageable, representative subset of slices per
patient needs to be selected and rendered as standard images (rather than
raw DICOM) that downstream scripts can consume uniformly.

## Core Idea

Tumor location is **not** detected from pixel intensity at this stage.
The NSCLC-Radiomics dataset already ships radiologist-drawn tumor
contours in an **RTSTRUCT** DICOM file (ROI name `GTV-1` — Gross Tumor
Volume). Each contour references the exact CT slice it belongs to via
`ReferencedSOPInstanceUID`. This makes the task geometric (parse
contours, map them to pixels) rather than a detection/ML problem —
detection/ML comes later, in the [Segmentation](05-segmentation-methods.md)
and later stages, once ground truth is already available for training
and evaluation.

## Method

### 1. Classify files by DICOM Modality
Each patient folder contains a CT series and an RTSTRUCT file, but TCIA
names the containing folders with opaque numeric UIDs rather than
descriptive names. The script does not trust folder names — it opens
every `.dcm` file and reads the `Modality` tag directly:
- `Modality == "CT"` → one axial slice, keyed by its `SOPInstanceUID`
- `Modality == "RTSTRUCT"` → the structure set (contours)
- `RTDOSE` / `RTPLAN` → ignored (not needed for this task)

### 2. Build a 3D CT volume
All of a patient's CT slices are loaded and stacked into one 3D array,
sorted by `ImagePositionPatient[2]` (the z / slice position):
`volume.shape == (num_slices, rows, cols)`.

Each voxel is converted from raw pixel values to **Hounsfield Units
(HU)** using the DICOM `RescaleSlope` / `RescaleIntercept` tags — this is
what makes CT intensities physically meaningful (air ≈ -1000 HU, water =
0 HU, bone ≈ +1000 HU, soft tissue/tumor ≈ 0–80 HU).

Voxel spacing is also recorded:
- `dy, dx` — in-plane pixel spacing (mm), from `PixelSpacing`.
- `dz` — slice spacing (mm), computed as the median distance between
  consecutive slices' z positions (more robust than trusting
  `SliceThickness` alone, which can differ from actual spacing).

### 3. Find the tumor ROI
The RTSTRUCT's `StructureSetROISequence` lists all defined structures
(GTV, lungs, spinal cord, external body outline, etc.). ROI names are
searched for tumor-related keywords (`gtv`, `tumor`, `tumour`, `nodule`,
`ctv`), preferring an exact `GTV` match since that is the standard name
for the primary tumor volume in this dataset.

### 4. Rasterize contours into a 3D tumor mask
For the chosen ROI, each contour in `ROIContourSequence` contains:
- `ReferencedSOPInstanceUID` — which CT slice this contour is on.
- `ContourData` — a flat list of `(x, y, z)` points in patient (world)
  coordinates (mm), forming a closed polygon outlining the tumor on that
  slice.

Each polygon is converted from world to pixel coordinates using that
slice's `ImagePositionPatient` and `PixelSpacing`, then rasterized into a
2D boolean mask (Pillow's `ImageDraw.polygon`). That mask is written into
the matching z-index of a 3D mask volume the same shape as the CT
volume. Multiple contour loops on one slice (e.g. tumor appears as more
than one connected region) are combined with a logical OR.

Result: `mask_volume[z, y, x] == True` wherever there is tumor.

### 5. Pick the best slices in each of the 3 anatomical planes
Rather than only looking top-down (axial), the script replicates what a
3-pane clinical viewer (e.g. 3D Slicer) shows:

| Plane | Fixed axis | "Richness" score |
|---|---|---|
| Axial (top-down) | z | tumor voxel count in that z-slice |
| Coronal (front view) | y | tumor voxel count in that y-row across all z, x |
| Sagittal (side view) | x | tumor voxel count in that x-column across all z, y |

For each plane, slice indices are ranked by tumor voxel count
(descending), and the top `VIEWS_PER_PLANE` are kept — i.e. the axial
slices with the largest tumor cross-section, the coronal row with the
most tumor visible front-on, and so on.

### 6. Render and save each view
For each selected slice:
1. Apply CT **windowing** — clip the HU range to a diagnostic window
   (`soft` = level 40 / width 400 for soft tissue/tumor visibility, or
   `lung` = level -600 / width 1500 for airway/parenchyma detail) and
   rescale to 0–255 grayscale. This matches how radiologists view CT —
   it's why the saved image still looks like a normal grayscale CT slice
   rather than raw HU data.
2. Overlay the corresponding 2D tumor mask slice as a translucent red
   fill plus a red contour outline.
3. For coronal/sagittal views, apply the correct **aspect ratio**
   (`dz/dx` or `dz/dy`), since slice spacing and in-plane pixel spacing
   are usually different — without this correction anatomy would look
   stretched or squashed relative to a clinical viewer.
4. Flip the z-axis for coronal/sagittal views so the head appears at the
   top, matching standard radiological display convention.

### 7. Output structure
Images are grouped by **rank** rather than by view type, so the 3 views
making up one "look" at the tumor live together:

```
tumor_slices/
  LUNG1-001/
    image_01/
      axial.png
      coronal.png
      sagittal.png
    image_02/
      axial.png
      coronal.png
      sagittal.png
    ...
  LUNG1-002/
    ...
```

Note: axial/coronal/sagittal within one `image_N` folder are paired **by
rank**, not by exact 3D coordinate — the #1 axial slice and #1 coronal
row are each independently the richest in their own plane, not
necessarily intersecting at the same voxel. This gives the clearest
possible view in each orientation rather than a single fixed 3D
crosshair location.

## Configuration

Set at the top of `extract_tumor_slices.py` (or via CLI flags):

| Setting | Meaning |
|---|---|
| `DATASET_DIR` | Folder containing one subfolder per patient (TCIA download layout) |
| `NUM_PATIENTS` | How many patients to process |
| `VIEWS_PER_PLANE` | How many ranked slices to keep per plane (e.g. 6 → 18 images/patient) |
| `OUT_DIR` | Where to save output PNGs |
| `WINDOW` | `"soft"` (soft tissue) or `"lung"` (airway/parenchyma) windowing |

## Known Limitations

- Not every patient's RTSTRUCT uses the exact name `GTV-1` — a few cases
  use different naming or are missing the structure entirely. The script
  prints the available ROI names when it can't confidently find a tumor
  ROI, so these cases can be checked manually rather than silently
  skipped without a trace.
- Coronal/sagittal head-up orientation is a default assumption — worth
  verifying against a clinical viewer (e.g. 3D Slicer) on a new dataset
  in case acquisition convention differs.
- Multiple contour loops on one slice are combined with OR (union), so
  contours representing holes (rare for solid tumors) aren't handled
  specially.

## Outcome

This step produces the tumor-annotated, per-patient, per-view PNG
dataset (`tumor_slices/`) that all subsequent processing stages consume
as their raw input, along with a visual (outlined) reference of ground
truth for every extracted slice — useful for spot-checking later stages
against the original contour without needing to reopen DICOM/RTSTRUCT
files.

## Next Step

Proceed to [Image Enhancement](03-image-enhancement.md), applied to the
extracted `tumor_slices/` output.
