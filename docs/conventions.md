# Conventions shared by the spatial transcriptomics apps

Every app in the three workflows (Spatial Domain Mapping & Condition Comparison; Cell-type
Deconvolution & Niches; Single-cell Spatial Profiling) follows this contract, so any step's
output can be linked to any other step's input without glue. The contract covers both
**sequencing-based** data (10x Visium, Visium HD bins, Slide-seq/Curio) where an observation
is a spot or bin holding several cells, and **imaging-based** data (10x Xenium, Vizgen
MERSCOPE, NanoString CosMx) where an observation is a segmented cell.

## Runtime contract (Pennsieve processors)

- Read from `$INPUT_DIR`, write to `$OUTPUT_DIR`. Parameters arrive as environment variables
  named as in `app.yml`. Never write elsewhere except `/tmp`.
- One output port: it is the whole `$OUTPUT_DIR`. Two or more outputs: each is written to
  `$OUTPUT_DIR/<name>/`.
- Inputs with several ports use `placement: subfolder`: each arrives at `$INPUT_DIR/<name>/`.
  Apps must also work when no links are used (everything merged side by side at the root of
  `$INPUT_DIR`), by finding files by their names anywhere under `$INPUT_DIR` (follow symlinks;
  INPUT_DIR entries are symlinks).
- Several links may feed the same input port; their entries land side by side in the same
  folder, and two entries with the same name fail the run. So an app that can run more than
  once in a workflow, or whose output can be one of several links into one port of the report
  (st-niches, st-ccc, st-compare), writes everything under a folder named after its `LABEL`
  parameter (default: the label column it worked on, with `_` as `-`). Single-run apps (st-prep,
  st-qc, st-domains, st-svg, st-celltype, cell2location) write at the root of each port.
- Port names: lowercase letters, digits and `-` (no underscores).
- Each output folder gets a `provenance.json`: app name + version (from `VERSION`), tool
  versions (`importlib.metadata.version`), parameters, inputs seen (relative paths), timings,
  per-sample status, peak RSS.
- A sample that fails is logged and skipped; the step fails only when every sample failed or
  no input was found. Exit code non-zero on failure (1 = no usable input / every sample failed,
  2 = bad parameters).
- Logs go to stdout, one line per sample with counts and timings.
- Memory: never hold every sample at once unless the method is joint across samples (BANKSY,
  cell2location training). Per-sample work streams one `.h5ad` at a time. Count matrices are
  CSR sparse (`scipy.sparse.csr_matrix`, float32 or int32); never densify a full matrix.
  Target: a Visium HD 8 µm sample (~500 k bins × 18 k genes) or a Xenium slide (~500 k cells ×
  5 k genes) fits in 16 GiB; 2 µm Visium HD bins are out of scope (document it).
- Threads: `THREADS` (default `0` = from the cgroup CPU quota, never the host's core count);
  set `OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, `MKL_NUM_THREADS`, `NUMBA_NUM_THREADS`
  before importing numpy.
- Reproducible: every random step takes `SEED` (default `42`).
- No network at run time. Resources a tool normally downloads (LIANA+ ligand–receptor resource,
  fonts) are baked into the image at build time.

## Files

### The AnnData contract (`spatial` ports)

`<sample_id>.h5ad`, one per sample, written by `st-prep` and rewritten by `st-qc` (which only
drops observations/genes and adds layers and `obs` columns). `sample_id` matches
`[A-Za-z0-9_-]+`. Read with `anndata.read_h5ad`.

| Slot | Content |
|---|---|
| `X` | From st-prep: raw UMI/transcript counts, CSR, integer-valued. From st-qc: log-normalized (`normalize_total` to `TARGET_SUM`, then `log1p`) float32, CSR; raw counts move to `layers["counts"]`. Downstream apps that need counts (cell2location, st-compare pseudobulk) read `layers["counts"]` when present, else `X`. |
| `obs_names` | `<sample_id>:<barcode or cell_id>`, unique across samples. |
| `obs["sample_id"]` | The sample id (categorical). |
| `obs["x"]`, `obs["y"]` | Spatial coordinates, same values as `obsm["spatial"]`. |
| `obs["in_tissue"]` | 1/0 for Visium (st-prep keeps only in-tissue spots unless `KEEP_OUT_OF_TISSUE=true`); 1 for cells and bins. |
| `obs["array_row"]`, `obs["array_col"]` | Visium / Visium HD grid indices when the platform has them. |
| `obs["total_counts"]`, `obs["n_genes_by_counts"]`, `obs["pct_counts_mt"]` | Written by st-prep (`scanpy.pp.calculate_qc_metrics`, mito genes = `MT-`/`mt-` prefix). |
| `obs["cell_area"]`, `obs["nucleus_area"]` | Cells, when the platform gives them (µm²). |
| `obs["control_counts"]` | Imaging-based: summed counts of control features (negative control probes, blank/unassigned codewords, system controls) per cell, before those features are dropped from `var`. |
| `obs["annotation"]` | Optional: a user-supplied label per observation (from `annotations.csv`, below), e.g. a pathologist's region. Apps that cluster report agreement (ARI, NMI) with it when present. |
| Any extra `samples.csv` column | Copied onto every observation of the sample (`condition`, `batch`, `donor`, ...). |
| `var_names` | Gene symbols, made unique (`var_names_make_unique`). `var["gene_ids"]` (Ensembl id or the platform's id when present), `var["feature_types"]`. Only `Gene Expression` features are kept; control features are summed into `obs["control_counts"]` then dropped. `var["mt"]` boolean. |
| `obsm["spatial"]` | `(n, 2)` float64 `[x, y]` in the units of `uns["pennsieve"]["coordinate_unit"]`. For Visium / Visium HD these are **full-resolution image pixels**, the scanpy/squidpy convention (so `uns["spatial"]` scalefactors apply); for imaging-based platforms, **microns** (Xenium `x_centroid`/`y_centroid`, MERSCOPE `center_x`/`center_y`, CosMx global µm from `CenterX_global_px` × the pixel size). |
| `uns["spatial"][sample_id]` | Visium only, the scanpy convention: `images` (`hires`, `lowres` as uint8 arrays) and `scalefactors` (`tissue_hires_scalef`, `tissue_lowres_scalef`, `spot_diameter_fullres`, `fiducial_diameter_fullres`). Absent for platforms without a registered image. |
| `uns["pennsieve"]` | A dict: `platform` (`visium`, `visium-hd`, `slide-seq`, `xenium`, `merscope`, `cosmx`, `h5ad`, `spatialdata`), `kind` (`spot`, `bin`, `cell`), `coordinate_unit` (`pixel`, `micron`), `spot_diameter` (spot/bin diameter or typical cell diameter in coordinate units; drives neighbour radii), `grid` (`hex`, `square` or `none`; a hex grid lets squidpy build grid neighbours), `bin_size_um` (Visium HD), `source` (the input path), `prep_version`, and after st-qc `normalized: true`, `target_sum`. |
| `obsm["X_pca"]`, `var["highly_variable"]`, `uns["pca"]` | Added by st-qc. |

Observations are ordered as in the source; apps never reorder `obs` of a file they rewrite.

Gene sets may differ between samples after st-qc (it drops genes per sample). Apps that combine
samples use the genes present in every sample, and say how many in their log and `summary.json`.

### `samples.csv` (in the `metadata` port, written by `st-prep`)

One row per sample. Required columns: `sample_id`, `path` (the sample's source folder or file,
relative to the input), `platform`, `kind`, `n_obs`, `n_genes`, `n_obs_in_tissue`. Any extra
columns from the user's sample sheet are carried through unchanged (`condition`, `batch`,
`donor`, `tissue`, ...).

`st-prep` reads an optional sample sheet from its input (`SAMPLE_SHEET`, default `samples.csv`,
with at least `sample_id` and `path`; `path` is matched against folder and file names anywhere
under the input). With a sheet, only its rows are samples: anything else detected is listed in
`prep.json` under `ignored` (so a dataset that ships extra copies, such as the TLS demo's
`h5ad_preprocessed/`, is not read twice). Without one, every detected sample becomes a row: `sample_id` = sanitised
folder name (or file stem for `.h5ad`), `condition` absent.

An optional `annotations.csv` (`sample_id`, `obs_id` (barcode or cell id as in the platform's
files), `annotation`) is joined onto `obs["annotation"]`.

### `prep.json` (in the `metadata` port)

Per sample: platform detected, files read, features dropped (control features by type, with
counts), observations dropped (out of tissue), coordinate unit, image presence, warnings.

### Labels (`labels` ports)

Every app that assigns a label to observations writes `labels.csv` with columns `sample_id`,
`obs_id` (the `obs_names` value), and one or more label columns:

| App | Label columns | Extra |
|---|---|---|
| st-domains | `domain` (`D01`, `D02`, ... shared across samples) | `domain_markers.csv` (`domain, gene, logfoldchange, pval_adj, pct_in, pct_out, rank`), `domain_summary.csv` (`sample_id, domain, n_obs, fraction`), `agreement.csv` when `obs["annotation"]` exists (`sample_id, ari, nmi, n_obs`, plus a confusion table) |
| st-celltype | `cluster` (`C01`, ...), `cell_type` (from the marker table; `Unassigned` when no marker set scores above `MIN_SCORE`) | `cluster_markers.csv`, `cell_type_summary.csv` (`sample_id, cell_type, n_obs, fraction`), `scores.csv` (`obs_id`, one column per cell type) |
| cell2location | `dominant_type` (the cell type with the highest estimated abundance; `Mixed` when the top type holds < `MIN_DOMINANT_FRACTION` of the spot's total) and `colocation_group` (the spot's strongest co-location group, `G01`, ...; every spot has one, so it is the label for niche analysis with a fine-grained reference) | `abundance.csv` (`sample_id, obs_id`, one column per cell type: `q05` posterior cell abundance), `colocation.csv` (co-location groups from cell2location's NMF: `group, cell_type, weight`), `proportions.csv` |

Downstream apps (st-niches, st-ccc, st-compare, st-report) take a `labels` input port and a
`LABEL_COLUMN` parameter naming the column to use. Several `labels.csv` from different apps may
be linked into one `labels` port only if they sit in different subfolders; st-domains,
st-celltype and cell2location each write under their own output root, so a workflow links one
of them per `labels` port. Within a single file all observations of all samples are listed.

### Tables and figures

- Tables are CSV (UTF-8, header row, `.` decimal). Long format where natural.
- Figures are PNG, 150 dpi, one per sample where it is per-sample
  (`<sample_id>_<what>.png`), with the sample id in the title. Spatial scatter plots draw
  `obsm["spatial"]` with y inverted (image convention), on the lowres H&E when there is one.
- A `summary.json` per output port with the headline numbers the report shows.

### Spatial neighbours

Apps that need a spatial graph build it with `squidpy.gr.spatial_neighbors` from the contract:
Visium (`grid: hex`) with `coord_type="grid", n_neighs=6, n_rings=N_RINGS`; everything else
with `coord_type="generic"` and either `delaunay=True` (`NEIGHBOURS=delaunay`, the default for
every non-hex platform) or `n_neighs=k` (`NEIGHBOURS=<k>`; set `NEIGHBOURS=8` for Visium HD square
bins, the 8 surrounding bins), with a `radius` cap of `MAX_NEIGHBOUR_DISTANCE` × `spot_diameter` so
sparse regions don't connect across gaps. Subsampled cell data (`MAX_OBS_PER_SAMPLE`) gives a sparse
graph under that cap; use it for quick runs, not for final numbers. st-ccc uses LIANA's own Gaussian
kernel graph (bandwidth × `spot_diameter`), on which its bivariate scores are defined.

## Platform readers (st-prep)

Detection is by files present, per folder (searched recursively; one sample per folder, or
per file for `.h5ad` / `.zarr`):

| Platform | Detected by | Reads |
|---|---|---|
| Visium (Space Ranger ≥ 1.x) | `filtered_feature_bc_matrix.h5` or the MTX folder `filtered_feature_bc_matrix/` + `spatial/tissue_positions.csv` or `tissue_positions_list.csv` | matrix, positions, `scalefactors_json.json`, `tissue_hires_image.png`, `tissue_lowres_image.png` (`scanpy.read_visium`-equivalent, implemented with `h5py`/`scanpy.read_10x_h5` + pandas + Pillow) |
| Visium HD | `binned_outputs/square_<NNN>um/` (parameter `BIN_SIZE_UM`, default 8) with `filtered_feature_bc_matrix.h5` and `spatial/tissue_positions.parquet` | as Visium; `grid: square` |
| Xenium | `cell_feature_matrix.h5` + `cells.parquet` or `cells.csv.gz` | matrix (`h5` 10x format), cell centroids and areas, `transcript_counts`, control probe/codeword counts |
| MERSCOPE | `cell_by_gene.csv` + `cell_metadata.csv` | counts (dense CSV → CSR), `center_x/center_y`, `volume`; `Blank-*` features are controls |
| CosMx | `*_exprMat_file.csv` + `*_metadata_file.csv` | counts, `CenterX_global_px/CenterY_global_px` × 0.12028 µm/px (AtoMx export; parameter `COSMX_PIXEL_UM`), `Area`; `NegPrb*`/`SystemControl*` are controls |
| AnnData | `*.h5ad` with `obsm["spatial"]` | as is, mapped onto the contract (`sample_id` from the file stem unless `obs` has one) |
| SpatialData | `*.zarr` with a `tables` element | the first table and its `spatial` coords (via `spatialdata`) |

Everything not detected is listed in `prep.json` as ignored.

## Demo data

All gitignored under `data/`; `scripts/fetch-sample-data.sh` downloads and checks them.

- **`data/tls-visium/`**: Dawo S, Nonchev K, Silina K. *10x Visium Spatial Transcriptomics Dataset:
  Kidney (3) and Lung (5) Cancer with Tertiary Lymphoid Structures.* Zenodo 2025,
  doi:10.5281/zenodo.14620362, CC BY 4.0. Eight FFPE tumour sections (Space Ranger 2.1.0
  output per sample) with spot annotations (TLS, Immune, Tumor, Normal, Unassigned) written
  to `annotations.csv`, and `samples.csv` with `tissue` (`kidney`/`lung`) as the `condition`.
- **`data/lymph-node/`**: 10x Genomics, *Human Lymph Node* (Visium, Space Ranger 1.1.0; CC BY
  4.0): `V1_Human_Lymph_Node_filtered_feature_bc_matrix.h5` + `spatial/`, 4,035 spots. And
  `data/lymph-node/reference/tabula-sapiens-lymph-node.h5ad`: Tabula Sapiens Consortium
  (Science 2022, doi:10.1126/science.abl4896), the Lymph_Node dataset from CELLxGENE
  (collection e5f58829-1a66-40b5-a624-9046778e74f5, CC BY 4.0), subsampled by
  `scripts/subsample-reference.py` to at most 500 cells per `cell_type`, raw counts in `X`.
- **`data/xenium-breast/`**: 10x Genomics, *FFPE Human Breast Cancer*, Xenium Onboard
  Analysis 1.0.1, replicates 1 and 2 (Janesick et al. 2023, doi:10.1038/s41467-023-43458-x;
  CC BY 4.0): `cell_feature_matrix.h5`, `cells.parquet`, `cell_boundaries.parquet` per
  replicate; 313-gene panel, ~167 k and ~118 k cells.

For local tests use `MAX_OBS_PER_SAMPLE` in st-prep (seeded subsample, e.g. 20000) unless
measuring memory and time; Docker on the dev Mac has 8 GB.
