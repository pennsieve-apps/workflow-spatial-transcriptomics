#!/usr/bin/env bash
# Creates the public GitHub repositories of the spatial transcriptomics workflows in the
# pennsieve-apps organization (empty; each app is pushed from its own checkout). Idempotent:
# a repo that already exists is skipped.
set -euo pipefail
ORG=pennsieve-apps
while IFS='|' read -r name desc; do
  if gh repo view "$ORG/$name" >/dev/null 2>&1; then echo "exists: $ORG/$name"; continue; fi
  gh repo create "$ORG/$name" --public -d "$desc"
done <<'EOF'
workflow-spatial-transcriptomics|Pennsieve workflows: spatial domain mapping, cell-type deconvolution and single-cell spatial profiling for Visium, Xenium, MERSCOPE and CosMx
st-prep|Pennsieve app: reads Visium, Visium HD, Xenium, MERSCOPE, CosMx, h5ad or SpatialData into one AnnData-per-sample contract for the spatial transcriptomics workflows
st-qc|Pennsieve app: QC, filtering, normalization and HVG/PCA for spatial transcriptomics samples
st-domains|Pennsieve app: spatial domains with BANKSY across samples, with domain markers and agreement with annotations
st-svg|Pennsieve app: spatially variable genes by Moran's I per sample (squidpy)
cell2location|Pennsieve app: cell-type deconvolution of Visium spots with cell2location from a scRNA-seq reference, with co-location groups
st-celltype|Pennsieve app: clustering and marker-based cell typing for single-cell spatial data (Xenium, MERSCOPE, CosMx)
st-niches|Pennsieve app: neighbourhood enrichment, co-occurrence and cellular niches from any spatial label (squidpy)
st-ccc|Pennsieve app: ligand-receptor cell-cell communication in space with LIANA+
st-compare|Pennsieve app: composition and pseudobulk differential expression between conditions per spatial domain or cell type (PyDESeq2)
st-report|Pennsieve app: HTML report and tables for the spatial transcriptomics workflows
EOF
