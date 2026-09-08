# Stacked Generalization (Ensemble Refinement)

## Objective

Improve the slice-level tumor detection rate beyond what raw U-Net
segmentation achieved on the full dataset, by combining multiple models
into an ensemble.

## Why This Step Was Needed

After scaling U-Net segmentation to the full dataset, the slice-level
detection rate came out to **71.62%** with a Dice coefficient of **0.65**
— a result far below the 90–100% "on the right track" range established
during single-patient validation. This gap indicated the model's outputs
needed to be filtered/corrected, ideally by learning to distinguish
correct detections from missed or falsely detected ones. Stacked
generalization (stacking) was chosen as a principled way to combine
several classifiers' strengths rather than relying on a single model or
manual thresholding.

## Full-Dataset Baseline (Before Stacking)

| Metric | Value |
|---|---|
| Ground-truth tumor-positive slices | 7,354 |
| Predicted tumor-positive slices | 7,377 |
| Correctly detected slices | 5,267 |
| Slice-level detection rate | 71.62% |
| Dice coefficient | 0.65 |

## What Is Stacked Generalization

Stacked generalization (stacking) is an ensemble technique where:
1. Several different **base models** are trained on the same task.
2. Each base model produces predictions on held-out data via
   cross-validation (out-of-fold, or OOF, predictions), avoiding
   information leakage from training data.
3. A separate **meta-learner** model is trained using only the base
   models' OOF predictions as its input features, learning how to best
   combine/weight them into a final prediction.

This differs from simple averaging or voting because the meta-learner can
learn non-trivial, data-driven combinations of the base models' outputs.

## Implementation

- **Base models:**
  - Logistic Regression
  - Random Forest
  - Extra Trees
  - HistGradientBoosting
  - Support Vector Machine (SVM)
- **Cross-validation:** 5-fold out-of-fold predictions generated for each
  base model.
- **Meta-learner:** Logistic Regression, trained only on the OOF
  predictions from the base models (not on raw image features directly).

## Results

| Metric | Baseline (U-Net only) | After Stacking |
|---|---|---|
| Dice | 0.65 | **0.77** |
| IoU | — | 0.63 |
| Precision | — | 82.32% |
| Recall (detection rate) | 71.62% | 73.16% |

- Threshold adjustment was also tried: lowering the classification
  threshold raised recall to **93%**, but this came at the cost of a
  large increase in false positives, making it an unfavorable
  precision/recall trade-off.

## Interpretation

- Stacking meaningfully improved Dice, IoU, and precision — the ensemble
  is better at correctly identifying true tumor slices when it does make
  a positive prediction.
- However, recall barely improved over the raw U-Net baseline (71.62% →
  73.16%), meaning the ensemble was not substantially better at catching
  tumor slices that the base segmentation had already missed.
- This indicated the bottleneck was not purely a classification/ensembling
  problem — the underlying **segmentation quality itself** (i.e., what
  U-Net produces before any ensembling) needed to be addressed, since
  stacking can only refine/re-weight what the base segmentation already
  detects, not recover regions the segmentation never captured.

## Decision

Rather than continuing to tune the ensemble/threshold, focus shifted to
improving the segmentation pipeline directly — leading to the
[Classifier Fusion Pipeline](08-classifier-fusion.md) approach.

## Next Step

Proceed to [Classifier Fusion Pipeline](08-classifier-fusion.md).
