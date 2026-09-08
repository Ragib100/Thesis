# Segmentation Methods

## Objective

Convert the preprocessed (enhanced + morphologically filtered) CT slices
into explicit region masks that isolate candidate tumor regions from the
rest of the image, moving from "visually separable" to "algorithmically
extracted."

## Why This Step Was Needed

Visual separability (confirmed in the morphological processing stage) is
necessary but not sufficient — an actual segmentation algorithm is
required to produce a discrete mask of tumor pixels/voxels that can be
measured against ground truth and eventually fed into 3D reconstruction
and machine learning stages.

## Method 1: Mean Shift Segmentation

- **What:** A clustering-based segmentation technique that groups pixels
  by density in feature space (e.g., color/intensity and spatial
  proximity) without requiring a predefined number of clusters.
- **Why chosen:** Suggested as a next step once preprocessing showed
  visibly separable regions — a relatively lightweight, non-learning-based
  segmentation approach to test before committing to a deep learning
  model.
- **Process:**
  1. Apply mean shift segmentation to preprocessed slices.
  2. Apply pseudocoloring to the segmented output to make distinct region
     clusters visually distinguishable.
  3. Explicitly mark/label which segmented regions correspond to the
     suspected tumor (shown in white in final outputs), since mean shift
     produces multiple clusters and not all correspond to tumor tissue.

## Method 2: U-Net Segmentation

- **What:** A convolutional neural network architecture specifically
  designed for biomedical image segmentation, using an encoder-decoder
  structure with skip connections to preserve spatial detail.
- **Why chosen:** Tried as an alternative to mean shift to see whether a
  learning-based approach could better capture tumor boundaries,
  especially since mean shift is unsupervised and not tumor-aware by
  design (it clusters by general intensity/spatial similarity, not by
  learned tumor features).
- **Result:** U-Net segmentation produced relatively better results
  compared to mean shift when checked against ground truth, and was
  selected as the primary segmentation method going forward.

## Comparison Summary

| Method | Type | Tumor-aware? | Relative Result |
|---|---|---|---|
| Mean shift | Unsupervised clustering | No (manual region marking needed after) | Baseline |
| U-Net | Supervised deep learning | Yes (learns from annotated tumor masks) | Better than mean shift vs. ground truth |

## Outcome

U-Net was adopted as the primary segmentation method for subsequent
detection validation and full-dataset processing, since it directly
learns tumor-specific features from annotated training data rather than
relying on general-purpose clustering plus manual region selection.

## Next Step

Proceed to [Detection Validation](06-detection-validation.md), where
U-Net's slice-level detection performance is formally checked against
ground truth on a single patient before scaling to the full dataset.
