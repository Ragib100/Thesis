# Detection Validation (Single Patient)

## Objective

Before scaling U-Net segmentation to the full dataset, validate its
slice-level tumor detection performance on a single patient against
ground-truth annotations, to catch systematic issues early and cheaply.

## Why This Step Was Needed

Running an unvalidated model across an entire dataset wastes time and
compute if the approach has fundamental issues. A single-patient
validation acts as a fast sanity check on whether the segmentation
pipeline is fundamentally sound before committing to full-scale
processing.

## Method

- Ground truth for the test patient: tumor present in **21 of 134**
  total slices (slices 66–86).
- U-Net predictions were compared slice-by-slice against this ground
  truth.
- Results were logged in a CSV file for traceability.

## Results

| Metric | Value |
|---|---|
| Total slices | 134 |
| Ground-truth tumor-positive slices | 21 (slices 66–86) |
| Correctly detected tumor slices | 21 / 21 (100%) |
| False-positive slices (tumor predicted, none present) | 23 |

## Interpretation

- **True positive rate (recall) on this patient: 100%** — every actual
  tumor-containing slice was correctly flagged.
- However, 23 false-positive slices indicate the model over-detects,
  flagging tumor presence in slices where none exists.
- A target true-positive rate of **90–100%** was set as the benchmark for
  "on the right track," which this result met.
- Despite the false positives, the strong recall was considered
  sufficient evidence to proceed to full-dataset segmentation, since
  false positives can potentially be addressed at a later refinement
  stage (see [Stacked Generalization](07-stacked-generalization.md) and
  [Classifier Fusion](08-classifier-fusion.md)), whereas missed tumors
  cannot be recovered later.

## Decision

- Full-dataset U-Net segmentation was approved to proceed, with a
  deadline set to complete it before beginning conference paper drafting.
- This decision also set an expectation that the project might be far
  enough along after full segmentation to consider a publication outcome.

## Next Step

Proceed to full-dataset U-Net segmentation, documented as the first
results section in [Results & Next Steps](10-results-and-next-steps.md)
and further refined in
[Stacked Generalization](07-stacked-generalization.md).
