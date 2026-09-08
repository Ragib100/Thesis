# Classifier Fusion Pipeline

## Objective

Directly improve segmentation quality — rather than only post-hoc
classification — by adding a classifier stage that filters U-Net's raw
predicted regions before they are finalized as the tumor mask.

## Why This Step Was Needed

Stacked generalization improved precision and Dice score but barely
moved recall, indicating the raw U-Net segmentation output itself
contained a mix of valid and invalid (false-positive) candidate regions
that needed to be separated *before* final mask generation — not just
reclassified after the fact at the slice level.

## Method

The refined pipeline works as follows:

1. **U-Net segmentation** produces initial candidate tumor regions per
   slice (as before).
2. **Classifier stage:** instead of accepting the U-Net output directly
   as the final segmentation, each predicted region is passed to a
   classifier that evaluates whether it is a genuine tumor region or a
   false positive.
3. **Fusion:** the classifier-approved regions are fused together to
   produce the final tumor mask (false positives identified by the
   classifier are discarded from the mask).
4. **Area-range filtering:** an additional filter based on region area
   (size) is applied to the fused output, removing regions that are
   implausibly small or large to be genuine tumor tissue.
5. Detection counts are computed at both the slice level and patient
   level.

## Why This Differs From Stacked Generalization

Stacking (previous stage) combined multiple models' predictions at the
**decision** level, after segmentation was already complete, and mainly
affected how confidently a slice was labeled positive/negative. This
classifier-fusion approach instead intervenes **within** the
segmentation output itself, filtering out specific false-positive
*regions* before mask fusion — a finer-grained correction than
slice-level reclassification.

## Results

| Metric | Value |
|---|---|
| Slice-level detection rate | 82.12% |
| Patient-level detection rate | 95.25% |

## Interpretation

- Both metrics improved substantially compared to the stacking-only
  approach (73.16% slice-level recall).
- The large gap between slice-level (82.12%) and patient-level (95.25%)
  detection suggests that even when some individual slices are missed
  or misclassified, the tumor is very likely to be caught in at least
  one slice per patient — relevant for patient-level diagnostic screening
  use cases, though less relevant for precise volumetric/3D
  reconstruction accuracy, which depends on slice-level correctness.
- Given the improvement, the next priority became visual/volumetric
  validation via 3D reconstruction, rather than continuing further 2D
  metric tuning.

## Next Step

Proceed to [3D Reconstruction](09-3d-reconstruction.md) to visualize the
classifier-fused segmentation output as a full 3D volume.
