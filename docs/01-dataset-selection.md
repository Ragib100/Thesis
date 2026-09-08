# Dataset Selection

## Objective

Select a tumor type and a public, annotated imaging dataset suitable for
3D reconstruction of tumor regions.

## Why This Step Was Needed

3D reconstruction and any downstream machine learning or deep learning
work requires a dataset that is:
- Large enough to train and validate models reliably.
- Publicly available (for reproducibility and to avoid data-access
  restrictions).
- Annotated with tumor region ground truth, since detection accuracy is
  measured against expert-marked regions.

## Candidates Considered

### Brain Tumor — BraTS 2020
- 369 annotated brain tumor MRI cases.
- ~155 slices per case → ~57,155 total 2D slices.
- Well-established benchmark dataset in brain tumor segmentation
  literature.

### Adenoid
- No public dataset was found for adenoid imaging. This direction was
  dropped early due to lack of available data — a prerequisite the other
  candidates satisfied.

### Lung Cancer — LIDC-IDRI
- 1,018 subjects with annotated lesions.
- Source: The Cancer Imaging Archive (TCIA).
- Link: https://www.cancerimagingarchive.net/collection/lidc-idri/

### Lung Cancer — NSCLC-Radiomics
- 422 patients with confirmed non-small cell lung cancer (NSCLC).
- Includes manually marked 3D tumor regions by medical experts, plus
  clinical outcome data.
- Source: The Cancer Imaging Archive (TCIA).
- Link: https://www.cancerimagingarchive.net/collection/nsclc-radiomics/

## Decision Process

1. Brain tumor reconstruction was initially proposed, but lung cancer
   reconstruction was also suggested as a parallel/alternative direction
   given dataset availability concerns.
2. A literature review was conducted specifically on 3D lung cancer
   reconstruction papers. The review found that most published work in
   this space relies on either LIDC-IDRI or NSCLC-Radiomics (or both).
3. Since the project's approach should be comparable to existing
   published methods, and both datasets were validated as standard
   choices in the literature, the decision was made to proceed with
   these literature-supported datasets rather than searching further for
   alternatives.

## Outcome

- **NSCLC-Radiomics** was carried forward as the primary working dataset
  for subsequent preprocessing and modeling stages (DICOM extraction,
  slice numbering, enhancement, segmentation).
- The dataset provides both imaging data and 3D tumor annotations
  necessary for supervised evaluation (ground-truth comparison) at every
  later pipeline stage.

## Rationale Summary

| Consideration | Why It Mattered |
|---|---|
| Public availability | Required for reproducibility and avoiding access barriers |
| Annotated ground truth | Needed to quantitatively evaluate detection/segmentation accuracy |
| Precedent in literature | Ensures results are comparable to existing published benchmarks |
| Sufficient case count | Needed enough patients/slices for meaningful training and validation |

## Next Step

Proceed to [Image Extraction](02-image-extraction.md) to pull
tumor-annotated slices from the selected dataset's DICOM/RTSTRUCT files.
