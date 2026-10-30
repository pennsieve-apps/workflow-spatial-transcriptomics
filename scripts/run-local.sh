#!/usr/bin/env bash
# Runs the spatial transcriptomics workflows locally with Docker, the way a compute node
# would: each step's INPUT_DIR is assembled from the linked outputs of the steps before it
# (INPUT_DIR/<input>/ <- OUTPUT_DIR/<output>/ of the source; several links into one input
# land side by side), and each step writes its own OUTPUT_DIR. No Pennsieve account needed.
#
# Usage: scripts/run-local.sh <a|b|c> <input-dir> [work-dir]
#   a     Spatial Domain Mapping & Condition Comparison   (input: Space Ranger folders + samples.csv [+ annotations.csv])
#   b     Cell-type Deconvolution & Niches                 (input: Space Ranger folders + samples.csv; REFERENCE=<h5ad> required)
#   c     Single-cell Spatial Profiling                    (input: Xenium/MERSCOPE/CosMx folders + samples.csv [+ markers.csv])
#   The sibling app repos (st-*, cell2location) must be checked out next to this one.
#   MAX_OBS_PER_SAMPLE=20000 makes a quick run (prep subsamples every sample).
set -euo pipefail
WHICH="$1"; IN="$(cd "$2" && pwd)"
WORK="$(mkdir -p "${3:-data/run}" && cd "${3:-data/run}" && pwd)"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PLATFORM="${PLATFORM:-linux/amd64}"
PREFIX="${IMAGE_PREFIX:-spatial-transcriptomics}"

build() { # build <app>
  docker build --platform "$PLATFORM" -q -t "$PREFIX/$1" "$ROOT/../$1" >/dev/null
  echo "built $PREFIX/$1"
}
link() { # link <step> <input> <source-step> <source-output|.>   (subfolder placement)
  # "." = an app with one output, which is the whole OUTPUT_DIR
  local dst="$WORK/$1/input/$2" src="$WORK/$3/output/$4"
  mkdir -p "$dst"
  [ -d "$src" ] && cp -R "$src/." "$dst/" || echo "   ($3 has no $4)"
}
fresh() { rm -rf "$WORK/$1"; mkdir -p "$WORK/$1/input" "$WORK/$1/output"; }
run() { # run <step> <app> [ENV=VAL ...]
  local step="$1" app="$2"; shift 2
  local envs=(); for e in "$@"; do envs+=(-e "$e"); done
  echo "== $step ($app)"; local t0; t0=$(date +%s)
  docker run --rm --platform "$PLATFORM" --memory "${MEMORY:-6g}" --network none \
    -v "$WORK/$step/input:/data/input:ro" -v "$WORK/$step/output:/data/output" \
    -e INPUT_DIR=/data/input -e OUTPUT_DIR=/data/output ${envs[@]+"${envs[@]}"} "$PREFIX/$app" \
    > "$WORK/$step/log.txt" 2>&1 || { tail -30 "$WORK/$step/log.txt"; echo "!! $step failed"; exit 1; }
  echo "   done in $(( $(date +%s) - t0 ))s"
}

APPS=(st-prep st-qc st-report)
case "$WHICH" in
  a) APPS+=(st-domains st-svg st-compare) ;;
  b) APPS+=(cell2location st-niches); [ -n "${REFERENCE:-}" ] || { echo "REFERENCE=<scRNA-seq .h5ad> is required for b" >&2; exit 2; } ;;
  c) APPS+=(st-celltype st-niches st-ccc) ;;
  *) echo "usage: $0 <a|b|c> <input-dir> [work-dir]" >&2; exit 2 ;;
esac
for a in "${APPS[@]}"; do build "$a"; done

# Shared head: prep (the input at the root) and QC.
fresh prep; cp -R "$IN/." "$WORK/prep/input/"
run prep st-prep MAX_OBS_PER_SAMPLE="${MAX_OBS_PER_SAMPLE:-0}"
fresh qc; link qc spatial prep spatial; link qc metadata prep metadata
run qc st-qc

if [ "$WHICH" = a ]; then
  fresh domains; link domains spatial qc spatial; link domains metadata prep metadata
  run domains st-domains
  fresh svg; link svg spatial qc spatial; link svg metadata prep metadata
  run svg st-svg
  fresh compare; link compare spatial qc spatial; link compare labels domains labels; link compare metadata prep metadata
  run compare st-compare LABEL_COLUMN=domain CONDITION_COLUMN="${CONDITION_COLUMN:-tissue}"
  fresh report
  link report metadata prep metadata; link report qc qc qc; link report domains domains labels
  link report svg svg .; link report compare compare .
  run report st-report REPORT_TITLE="Spatial Domain Mapping & Condition Comparison"
fi

if [ "$WHICH" = b ]; then
  fresh deconvolution; link deconvolution spatial qc spatial; link deconvolution metadata prep metadata
  mkdir -p "$WORK/deconvolution/input/reference"; cp "$REFERENCE" "$WORK/deconvolution/input/reference/"
  run deconvolution cell2location CELL_TYPE_COLUMN="${CELL_TYPE_COLUMN:-cell_type}" SPATIAL_EPOCHS="${SPATIAL_EPOCHS:-30000}"
  fresh niches; link niches spatial qc spatial; link niches labels deconvolution labels; link niches metadata prep metadata
  run niches st-niches LABEL_COLUMN=dominant_type LABEL=dominant-type
  fresh report
  link report metadata prep metadata; link report qc qc qc; link report deconvolution deconvolution labels
  link report niches niches .
  run report st-report REPORT_TITLE="Cell-type Deconvolution & Niches"
fi

if [ "$WHICH" = c ]; then
  fresh celltype; link celltype spatial qc spatial; link celltype metadata prep metadata
  [ -f "$IN/markers.csv" ] && { mkdir -p "$WORK/celltype/input/markers"; cp "$IN/markers.csv" "$WORK/celltype/input/markers/"; }
  run celltype st-celltype
  fresh niches; link niches spatial qc spatial; link niches labels celltype labels; link niches metadata prep metadata
  run niches st-niches LABEL_COLUMN=cell_type LABEL=cell-type
  fresh ccc; link ccc spatial qc spatial; link ccc labels celltype labels; link ccc metadata prep metadata
  run ccc st-ccc LABEL_COLUMN=cell_type LABEL=cell-type
  fresh report
  link report metadata prep metadata; link report qc qc qc; link report celltype celltype labels
  link report celltype-figures celltype figures; link report niches niches .; link report ccc ccc .
  run report st-report REPORT_TITLE="Single-cell Spatial Profiling"
fi
echo "Report: $WORK/report/output/report/index.html"
