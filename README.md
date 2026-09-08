# 3D Reconstruction of Tumor Regions from CT/MRI Scans

## Overview

This repository documents the design, experimentation, and decision-making
process behind a thesis project on **automated tumor detection and 3D
reconstruction from medical imaging data**. The work covers the full
pipeline from dataset selection through preprocessing, segmentation,
classification, and 3D visualization of tumor regions, with the eventual
goal of producing a publishable pipeline and a conference paper.

The documentation is organized chronologically by pipeline stage. Each
document explains **what** was done, **why** it was done, what parameters
or methods were used, what results were obtained, and what decision or
next step followed from those results.

## Project Pipeline

```
Dataset Selection
      │
      ▼
Image Extraction (RTSTRUCT contours → tumor slice PNGs)
      │
      ▼
Image Enhancement (Global vs Local)
      │
      ▼
Morphological Processing (Opening, Opening by Reconstruction)
      │
      ▼
Segmentation (Mean Shift vs U-Net)
      │
      ▼
Detection Validation (Single Patient)
      │
      ▼
Full-Dataset U-Net Segmentation
      │
      ▼
Stacked Generalization (Ensemble Classification)
      │
      ▼
Classifier Fusion Pipeline (Post-Segmentation Refinement)
      │
      ▼
3D Reconstruction & Visualization
      │
      ▼
Results Evaluation & Paper Preparation
```

## Documentation Index

| # | Document | Description |
|---|----------|--------------|
| 1 | [Dataset Selection](docs/01-dataset-selection.md) | Choice of tumor type and dataset, with rationale |
| 2 | [Image Extraction](docs/02-image-extraction.md) | Extracting tumor-annotated slices from DICOM + RTSTRUCT via `src/extract_tumor_slices.py` |
| 3 | [Image Enhancement](docs/03-image-enhancement.md) | Global vs. local contrast enhancement via `src/enhance_images.py` |
| 4 | [Morphological Processing](docs/04-morphological-processing.md) | Opening, opening by reconstruction, structuring element tuning |
| 5 | [Segmentation Methods](docs/05-segmentation-methods.md) | Mean shift segmentation vs. U-Net segmentation |
| 6 | [Detection Validation](docs/06-detection-validation.md) | Single-patient validation against ground truth |
| 7 | [Stacked Generalization](docs/07-stacked-generalization.md) | Ensemble learning approach to reduce false detections |
| 8 | [Classifier Fusion Pipeline](docs/08-classifier-fusion.md) | Post-segmentation classification refinement stage |
| 9 | [3D Reconstruction](docs/09-3d-reconstruction.md) | Volumetric visualization of predicted vs. ground-truth tumor regions |
| 10 | [Results & Next Steps](docs/10-results-and-next-steps.md) | Consolidated metrics, benchmark comparison, and current status |
| — | [Progress Log](docs/00-progress-log.md) | Anonymized chronological log of all discussions and decisions |

## Source Code

| Script | Used By | Purpose |
|---|---|---|
| [`src/extract_tumor_slices.py`](src/extract_tumor_slices.py) | [Image Extraction](docs/02-image-extraction.md) | Extract tumor-annotated axial/coronal/sagittal PNGs from DICOM + RTSTRUCT |
| [`src/enhance_images.py`](src/enhance_images.py) | [Image Enhancement](docs/03-image-enhancement.md) | Apply global (histogram equalization) and local (adaptive equalization) enhancement, with comparison outputs |

## Current Status

The pipeline has completed one full iteration: dataset selection through
3D reconstruction. Detected tumor region accuracy is below the 95%
threshold considered acceptable relative to recent published benchmarks
on the same dataset. The project has now moved into the **conference
paper drafting stage**.

## Repository Conventions

- All documentation is written in Markdown and version-controlled with Git.
- Each pipeline stage has its own document; update the relevant document
  as new experiments are run rather than creating duplicate files.
- Individual contributor names are intentionally omitted from these docs;
  all work is attributed to "the team," with guidance attributed to
  "the supervisor."
- Reproducible processing scripts live under `src/` and are linked from
  their corresponding stage document (e.g. `src/extract_tumor_slices.py`
  is linked from `docs/02-image-extraction.md`). As each pipeline stage
  is re-run with a finalized script, add it to `src/` and link it from
  the matching doc the same way.
- Raw comparison images, CSVs, and notebooks referenced in these docs are
  kept outside this documentation folder (e.g., `/data`, `/notebooks`,
  `/results`) and linked by relative path where applicable.
