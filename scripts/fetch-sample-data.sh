#!/usr/bin/env bash
# Downloads the demo data of the three spatial transcriptomics workflows into data/ and checks
# every file's checksum (MD5 from the Zenodo record; SHA-256 of the 10x and CELLxGENE files as
# fetched on 2026-10-29, since those servers publish none). All CC BY 4.0. Needs curl, unzip,
# tar, and Python 3 with h5py (annotations), numpy, scipy, pandas and anndata (reference).
#
# Usage: scripts/fetch-sample-data.sh [tls|lymph|xenium|all]   (default: all)
#   tls     data/tls-visium/   Dawo, Nonchev, Silina: Kidney (3) and Lung (5) Cancer with TLS,
#                              Visium, Space Ranger 2.1.0; Zenodo 10.5281/zenodo.14620362 (2.1 GB)
#   lymph   data/lymph-node/   10x Genomics Human Lymph Node (Visium, Space Ranger 1.1.0) and the
#                              Tabula Sapiens Lymph_Node scRNA-seq reference from CELLxGENE
#                              (4.1 GB download, subsampled to 58 MB)
#   xenium  data/xenium-breast/ 10x Genomics Xenium FFPE Human Breast Cancer, Rep1 and Rep2
#                              (cell-level files only, 55 MB)
# PYTHON=... picks the interpreter (default: python3).
set -euo pipefail
WHICH="${1:-all}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA="$ROOT/data"; DL="$DATA/download"; mkdir -p "$DL"
PYTHON="${PYTHON:-python3}"

fetch() { # fetch <url> <file> <sha256|md5:...>
  local url="$1" file="$DL/$2" sum="$3"
  if [ ! -f "$file" ] || ! check "$file" "$sum"; then
    echo "downloading $2"
    curl -sSL -C - --retry 5 --retry-all-errors -o "$file" "$url"
    check "$file" "$sum" || { echo "checksum mismatch: $2" >&2; exit 1; }
  else
    echo "have $2"
  fi
}
check() { # check <file> <sha256|md5:...>
  case "$2" in
    md5:*) [ "$(md5 -q "$1" 2>/dev/null || md5sum "$1" | cut -d' ' -f1)" = "${2#md5:}" ] ;;
    *) [ "$(shasum -a 256 "$1" | cut -d' ' -f1)" = "$2" ] ;;
  esac
}

tls() {
  fetch "https://zenodo.org/api/records/14620362/files/TLS_VISIUM_USZ.zip/content" TLS_VISIUM_USZ.zip \
        md5:4115532257e9c6a0dd2bcdb7f0e463d8
  mkdir -p "$DATA/tls-visium"
  # Space Ranger outputs (MTX matrices, positions, images) and the authors' preprocessed h5ad
  # (for the spot annotations); the 300 MB full-resolution TIFs are not needed.
  unzip -q -o "$DL/TLS_VISIUM_USZ.zip" "TLS_VISIUM_USZ/10x_Visium/*" "TLS_VISIUM_USZ/h5ad_preprocessed/*" \
        -x "*/.ipynb_checkpoints/*" -d "$DATA/tls-visium/"
  "$PYTHON" "$ROOT/scripts/make-tls-annotations.py" "$DATA/tls-visium"
  echo "TLS Visium demo: $DATA/tls-visium/ (samples.csv, annotations.csv)"
}

lymph() {
  local B=https://cf.10xgenomics.com/samples/spatial-exp/1.1.0/V1_Human_Lymph_Node
  fetch $B/V1_Human_Lymph_Node_filtered_feature_bc_matrix.h5 V1_Human_Lymph_Node_filtered_feature_bc_matrix.h5 \
        86fd533eb907450e7125b9820183a0ca73776eeafcc5eddae5695b6aabfd9139
  fetch $B/V1_Human_Lymph_Node_raw_feature_bc_matrix.h5 V1_Human_Lymph_Node_raw_feature_bc_matrix.h5 \
        b957f48b0d5a9dc7a870ce99458c1aa3d49a8cd013d5766df5914133c41b7228
  fetch $B/V1_Human_Lymph_Node_spatial.tar.gz V1_Human_Lymph_Node_spatial.tar.gz \
        812808883366ff9623dc8354847a7211b0d922b2bfc4c9359d6e12e993ea6a73
  local S="$DATA/lymph-node/V1_Human_Lymph_Node"; mkdir -p "$S" "$DATA/lymph-node/reference"
  cp "$DL/V1_Human_Lymph_Node_filtered_feature_bc_matrix.h5" "$S/filtered_feature_bc_matrix.h5"
  cp "$DL/V1_Human_Lymph_Node_raw_feature_bc_matrix.h5" "$S/raw_feature_bc_matrix.h5"
  tar -xzf "$DL/V1_Human_Lymph_Node_spatial.tar.gz" -C "$S/"
  printf 'sample_id,path,tissue\nlymph_node,V1_Human_Lymph_Node,lymph_node\n' > "$DATA/lymph-node/samples.csv"
  # Tabula Sapiens - Lymph_Node (CELLxGENE collection e5f58829-1a66-40b5-a624-9046778e74f5), 4.1 GB.
  fetch https://datasets.cellxgene.cziscience.com/6dd28080-1d36-4905-8b44-a9954a4438a2.h5ad tabula-sapiens-lymph-node.h5ad \
        b251738b269cf6f2c29ee81375634a633b377375cec501c6a6bafdad230dcba1
  "$PYTHON" "$ROOT/scripts/subsample-reference.py" "$DL/tabula-sapiens-lymph-node.h5ad" \
        "$DATA/lymph-node/reference/tabula-sapiens-lymph-node.h5ad"
  echo "Lymph node demo: $DATA/lymph-node/ (samples.csv, reference/)"
}

xenium() {
  local B=https://cf.10xgenomics.com/samples/xenium/1.0.1
  xsum() { # xsum <Rep>_<file> -> sha256 (bash 3 has no associative arrays)
    case "$1" in
      Rep1_cell_feature_matrix.h5) echo 681e1c1dfce0e517aa63a43dcdbe25df3de81498a3684f4168c9a8e166a48404 ;;
      Rep1_cells.parquet) echo aac8cc395143de2d7a73a951028686c9eb4c06b9a3b32677ff1413cd20f65bd3 ;;
      Rep1_cells.csv.gz) echo 8fc6f2b4c000c42ca97a1bb904a8d7608b33fa69ff86b1be0291016acbc2649c ;;
      Rep1_cell_boundaries.parquet) echo b25587098e36211ec2a46059fbbd4656f9407b1b8c3e06d868304060ad02206a ;;
      Rep2_cell_feature_matrix.h5) echo 691735ef59894aed7e3690cd529bc25fce93033af3c089c00f3a352b34dda9a8 ;;
      Rep2_cells.parquet) echo fa5f6be9a64ed1e5e40e5730dd2a603be72073a09e159b2879e9568421fd7d10 ;;
      Rep2_cells.csv.gz) echo 0b35c9c1afc1da17fd862d84a94f1f741e1e7d79e11ddca3871f0c98bf32f102 ;;
      Rep2_cell_boundaries.parquet) echo bdc57177d980be9ec356c9935fc32c980c1c1cc40310a296e0ef2257928fab4c ;;
    esac
  }
  for r in Rep1 Rep2; do
    mkdir -p "$DATA/xenium-breast/$r"
    for f in cell_feature_matrix.h5 cells.parquet cells.csv.gz cell_boundaries.parquet; do
      local name="Xenium_FFPE_Human_Breast_Cancer_${r}_$f"
      fetch "$B/Xenium_FFPE_Human_Breast_Cancer_$r/$name" "$name" "$(xsum ${r}_$f)"
      cp "$DL/$name" "$DATA/xenium-breast/$r/$f"
    done
  done
  printf 'sample_id,path,condition,replicate\nbreast_rep1,Rep1,breast_cancer,1\nbreast_rep2,Rep2,breast_cancer,2\n' \
    > "$DATA/xenium-breast/samples.csv"
  echo "Xenium demo: $DATA/xenium-breast/ (samples.csv)"
}

case "$WHICH" in
  tls) tls ;; lymph) lymph ;; xenium) xenium ;;
  all) tls; lymph; xenium ;;
  *) echo "usage: $0 [tls|lymph|xenium|all]" >&2; exit 2 ;;
esac
