# How the tumor slice images are generated

Script: [`src/extract_tumor_slices.py`](../src/extract_tumor_slices.py)

## The core idea

We don't detect tumors from pixel intensity. The NSCLC-Radiomics dataset
already ships radiologist-drawn tumor contours in an **RTSTRUCT** DICOM file
(ROI name `GTV-1` — Gross Tumor Volume). Each contour references the exact CT
slice it belongs to via `ReferencedSOPInstanceUID`. So the task is geometric
(parse contours, map them to pixels) rather than a detection/ML problem.

## Step by step

### 1. Classify files by DICOM Modality

Each patient folder contains a CT series and an RTSTRUCT file, but TCIA names
the containing folders with opaque numeric UIDs (not `CT/`, `RTSTRUCT/`, etc).
So the script doesn't trust folder names — it opens every `.dcm` file and
reads the `Modality` tag directly:

- `Modality == "CT"` → one axial slice, keyed by its `SOPInstanceUID`
- `Modality == "RTSTRUCT"` → the structure set (contours)
- `RTDOSE` / `RTPLAN` → ignored (not needed for this task)

### 2. Build a 3D CT volume

All of a patient's CT slices are loaded and stacked into one 3D NumPy array,
sorted by `ImagePositionPatient[2]` (the z / slice position):

```
volume.shape == (num_slices, rows, cols)
```

Each voxel is converted from raw pixel values to **Hounsfield Units (HU)**
using the DICOM `RescaleSlope` / `RescaleIntercept` tags — this is what makes
CT intensities physically meaningful (air ≈ -1000 HU, water = 0 HU, bone ≈
+1000 HU, soft tissue / tumor ≈ 0-80 HU).

Voxel spacing is also recorded:
- `dy, dx` — in-plane pixel spacing (mm), from `PixelSpacing`
- `dz` — slice spacing (mm), computed as the median distance between
  consecutive slices' z positions (more robust than trusting
  `SliceThickness` alone, which can differ from actual spacing)

### 3. Find the tumor ROI

The RTSTRUCT's `StructureSetROISequence` lists all defined structures (GTV,
lungs, spinal cord, external body outline, etc). The script searches ROI
names for tumor-related keywords (`gtv`, `tumor`, `tumour`, `nodule`, `ctv`),
preferring an exact `GTV` match since that's the standard name for the
primary tumor volume in this dataset.

### 4. Rasterize contours into a 3D tumor mask

For the chosen ROI, each contour in `ROIContourSequence` contains:
- `ReferencedSOPInstanceUID` → which CT slice this contour is on
- `ContourData` → a flat list of `(x, y, z)` points in patient (world)
  coordinates (mm), forming a closed polygon outlining the tumor on that
  slice

Each polygon is converted from world coordinates to pixel coordinates using
that slice's `ImagePositionPatient` and `PixelSpacing`, then rasterized (filled
in) into a 2D boolean mask using Pillow's `ImageDraw.polygon`. That 2D mask is
written into the matching z-index of a 3D mask volume the same shape as the
CT volume. If a slice has multiple contour loops (e.g. tumor appears as more
than one connected region), their masks are combined with a logical OR.

The result: `mask_volume[z, y, x] == True` wherever there is tumor.

### 5. Pick the best slices in each of the 3 anatomical planes

Instead of only looking top-down (axial), we replicate what you'd see
scrubbing through 3D Slicer's three-pane view:

| Plane | Fixed axis | "Richness" score |
|---|---|---|
| Axial (top-down) | z | tumor voxel count in that z-slice |
| Coronal (front view) | y | tumor voxel count in that y-row across all z, x |
| Sagittal (side view) | x | tumor voxel count in that x-column across all z, y |

For each plane, slice indices are ranked by tumor voxel count (descending),
and the top `VIEWS_PER_PLANE` are kept — i.e. the axial slices with the
largest tumor cross-section, the coronal row with the most tumor visible
front-on, and so on.

### 6. Render and save each view

For each selected slice:
1. Apply CT **windowing** — clip the HU range to a diagnostic window
   (`soft` = level 40 / width 400 for soft tissue/tumor visibility, or
   `lung` = level -600 / width 1500 for airway/parenchyma detail) and rescale
   to 0–255 grayscale. This is the same windowing radiologists use when
   reading CT — it's why the image still looks like a normal grayscale CT
   slice, not raw HU data.
2. Overlay the corresponding 2D tumor mask slice as a translucent red fill
   plus a red contour outline (`ax.contour` at the 0.5 mask level).
3. For coronal/sagittal views, apply the correct **aspect ratio**
   (`dz/dx` or `dz/dy`) since slice spacing and in-plane pixel spacing are
   usually different — without this correction the anatomy would look
   stretched or squashed vs. how it appears in Slicer.
4. Flip the z-axis (`np.flipud`) for coronal/sagittal views so the head
   appears at the top, matching standard radiological display convention.

### 7. Output structure

Rather than grouping all axial images together, all coronal together, etc.,
images are grouped by **rank**, so the 3 views making up one "look" at the
tumor live together:

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
rank**, not by exact 3D coordinate — the #1 axial slice and #1 coronal row
are each independently the richest in their own plane, not necessarily
intersecting at the same voxel. This gives you the clearest possible view in
each orientation rather than a single fixed 3D crosshair location.

## Known limitations

- Not every patient's RTSTRUCT uses the exact name `GTV-1` — a few cases use
  different naming or are missing the structure entirely. The script prints
  the available ROI names when it can't confidently find a tumor ROI.
- Coronal/sagittal head-up orientation is a default assumption
  (`np.flipud`) — verify against 3D Slicer on a new dataset in case
  acquisition convention differs.
- Multiple contour loops on one slice are combined with OR (union), so
  contours representing holes (rare for solid tumors) aren't handled
  specially.