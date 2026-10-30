#!/usr/bin/env python3
"""
Writes the three spatial transcriptomics workflow definitions (workflow/*.json, the body of
POST /compute/workflows/definitions) from the step lists below. Add
"organizationId": "N:organization:..." to the body when posting: without it the workflow
belongs to no workspace and the Workflow Library doesn't list it (an organization_id query
parameter is not enough). Each step's cpu/memory comes from its app's app.yml runtime (the
sibling repo ../<app>), rounded up to a size Fargate offers, so the definitions
follow the apps.

Each step pins the newest release tag at or before the checked-out commit of its app.

Usage: scripts/build-workflows.py
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ORG = "https://github.com/pennsieve-apps"
COL, ROW = 260, 130  # canvas grid

# Fargate accepts only some cpu/memory pairs (MiB): from a minimum per cpu, in steps of 1 GiB (4 GiB
# from 8 vCPU). An app that asks for something else (4 vCPU / 4 GiB, or the 3008 MiB of a Lambda-sized
# step on 1 vCPU) has its step rounded up to the next valid size, or the task is refused. GPU steps run
# on EC2, not Fargate, and keep what they ask for.
FARGATE_MIN_MEMORY = {256: 512, 512: 1024, 1024: 2048, 2048: 4096, 4096: 8192, 8192: 16384, 16384: 32768}
FARGATE_STEP = {256: 512, 512: 1024, 1024: 1024, 2048: 1024, 4096: 1024, 8192: 4096, 16384: 8192}


def fargate_memory(cpu: str, mem: str) -> str:
    c, m = int(cpu), int(mem)
    floor, step = FARGATE_MIN_MEMORY.get(c, 0), FARGATE_STEP.get(c, 1)
    valid = max(floor, -(-m // step) * step)
    if valid != m:
        print(f"note: {cpu} cpu / {mem} MiB is not a Fargate size; using {valid} MiB")
    return str(valid)


def runtime(app: str, variant: str | None = None) -> tuple[str, str]:
    path = ROOT.parent / f"{app}" / "app.yml"
    if not path.exists():
        raise SystemExit(f"{path} not found: check out {app} next to this repo")
    text = path.read_text()
    block = re.search(r"^runtime:\n((?:[ #].*\n?)*)", text, re.M).group(1)
    cpu = re.search(r"^\s+cpu:\s*(\d+)", block, re.M).group(1)
    mem = re.search(r"^\s+memory:\s*(\d+)", block, re.M).group(1)
    if variant:  # a variant's runtime fields replace the top level's (app-manifest-variants.md)
        v = re.search(rf"^  - id: {re.escape(variant)}\n((?:    .*\n?|\s*\n)*)", text, re.M)
        if not v:
            raise SystemExit(f"{app}: no variant {variant!r} in app.yml")
        m = re.search(r"runtime:\s*\{([^}]*)\}", v.group(1)) or re.search(r"runtime:\n((?:      .*\n?)*)", v.group(1))
        if m:
            cpu = (re.search(r"cpu:\s*(\d+)", m.group(1)) or [None, cpu])[1]
            mem = (re.search(r"memory:\s*(\d+)", m.group(1)) or [None, mem])[1]
    return cpu, mem


def release_tag(app: str) -> str:
    """The newest release tag at or before the checked-out commit, after refreshing tags from
    origin (local tags can be stale). Commits after it (docs, CITATION.cff) are not released yet."""
    repo = ROOT.parent / f"{app}"
    git = lambda *a: subprocess.run(["git", "-C", repo, *a], capture_output=True, text=True)
    git("fetch", "-q", "--tags", "--force", "origin")
    tag = git("describe", "--tags", "--abbrev=0", "--match", "v*", "HEAD").stdout.strip()
    if not tag:
        raise SystemExit(f"{app}: no release tag at or before HEAD")
    commit = git("rev-list", "-n1", tag).stdout.strip()
    same = git("tag", "--points-at", commit, "--list", "v*").stdout.split()
    tag = max(same, key=lambda t: [int(n) for n in re.findall(r"\d+", t)])
    ahead = git("rev-list", "--count", f"{tag}..HEAD").stdout.strip()
    if ahead not in ("", "0"):
        print(f"note: {app} is {ahead} commit(s) past {tag}; the workflow pins {tag}")
    return tag


def step(id_, app, col, row, depends, links=(), params=None, variant=None):
    cpu, mem = runtime(app, variant)
    if variant != "gpu":
        mem = fargate_memory(cpu, mem)
    tag = release_tag(app)
    node = {
        "id": id_,
        "type": "processor",
        "sourceUrl": f"{ORG}/{app}",
        "tag": tag,
        "dependsOn": list(depends),
        "position": {"x": 40 + COL * col, "y": 40 + ROW * row},
        "cpu": cpu,
        "memory": mem,
    }
    if variant:
        node["variant"] = variant
    if links:
        # A link from a workflow input (output None) names no output: the input is the data itself.
        node["inputs"] = [{"from": f, "input": i} if o is None else {"from": f, "output": o, "input": i}
                          for f, o, i in links]
    if params:
        node["defaultParams"] = params
    return node


def output(id_, name, step_, out, folder, col, row, default=True):
    o = {"id": id_, "name": name, "from": {"step": step_, "output": out},
         "position": {"x": 40 + COL * col, "y": 40 + ROW * row}}
    if default:
        o["default"] = {"targetType": "Pennsieve Dataset", "params": {"TARGET_FOLDER": folder}}
    return o


def spatial_input(description, row=2):
    return {
        "id": "spatial",
        "name": "Spatial transcriptomics data",
        "description": description,
        "position": {"x": 40, "y": 40 + ROW * row},
    }


PREP = lambda col, row: step("prep", "st-prep", col, row, ["spatial"])
QC = lambda col, row: step("qc", "st-qc", col, row, ["prep"],
                           [("prep", "spatial", "spatial"), ("prep", "metadata", "metadata")])
META = ("prep", "metadata", "metadata")
QCD = ("qc", "spatial", "spatial")


def domains():
    steps = [
        PREP(1, 2),
        QC(2, 2),
        step("domains", "st-domains", 3, 2, ["qc", "prep"], [QCD, META]),
        step("svg", "st-svg", 4, 1, ["qc", "prep"], [QCD, META]),
        step("compare", "st-compare", 4, 3, ["domains", "qc", "prep"],
             [QCD, ("domains", "labels", "labels"), META],
             {"LABEL_COLUMN": "domain", "CONDITION_COLUMN": "tissue"}),
        step("report", "st-report", 5, 2, ["prep", "qc", "domains", "svg", "compare"],
             [META, ("qc", "qc", "qc"), ("domains", "labels", "domains"), ("svg", "svg", "svg"),
              ("compare", "compare", "compare")],
             {"REPORT_TITLE": "Spatial Domain Mapping & Condition Comparison"}),
    ]
    return {
        "name": "Spatial Domain Mapping & Condition Comparison",
        "summary": "Visium/Visium HD: QC, BANKSY spatial domains, spatially variable genes, DE between conditions.",
        "description": (
            "Maps the tissue domains of sequencing-based spatial transcriptomics sections (10x Visium, "
            "Visium HD bins, Slide-seq) and compares conditions. Reads Space Ranger or AnnData input "
            "(st-prep), filters and normalizes spots (st-qc), finds spatial domains shared across samples "
            "with BANKSY (Singhal et al. 2024) and reports their marker genes and agreement with any "
            "annotation, ranks spatially variable genes by Moran's I (squidpy), tests domain composition "
            "and pseudobulk differential expression per domain between conditions (PyDESeq2), and writes "
            "an HTML report with tables."),
        "inputs": [spatial_input(
            "A folder of Space Ranger outputs (one per sample), Visium HD binned outputs, AnnData .h5ad "
            "or SpatialData .zarr files, plus an optional samples.csv (sample_id, path, condition, ...) "
            "and annotations.csv (sample_id, obs_id, annotation).")],
        "processors": steps,
        "outputs": [
            output("report_out", "Report", "report", "report", "derivatives/spatial-domains/report", 6, 1),
            output("tables_out", "Tables", "report", "tables", "derivatives/spatial-domains/tables", 6, 2),
            output("domains_out", "Spatial domains", "domains", "labels", "derivatives/spatial-domains/domains", 6, 3),
            output("svg_out", "Spatially variable genes", "svg", "svg", "derivatives/spatial-domains/svg", 6, 4),
            output("compare_out", "Condition comparison", "compare", "compare",
                   "derivatives/spatial-domains/compare", 6, 5),
            output("qc_spatial_out", "QC'd AnnData", "qc", "spatial", "", 6, 6, default=False),
        ],
    }


def deconvolution(variant=None):
    steps = [
        PREP(1, 2),
        QC(2, 2),
        step("deconvolution", "cell2location", 3, 2, ["qc", "prep", "reference"],
             [QCD, META, ("reference", None, "reference")],
             {"CELL_TYPE_COLUMN": "cell_type"}, variant=variant),
        step("niches", "st-niches", 4, 2, ["deconvolution", "qc", "prep"],
             [QCD, ("deconvolution", "labels", "labels"), META],
             {"LABEL_COLUMN": "colocation_group", "LABEL": "colocation-group"}),
        step("report", "st-report", 5, 2, ["prep", "qc", "deconvolution", "niches"],
             [META, ("qc", "qc", "qc"), ("deconvolution", "labels", "deconvolution"),
              ("niches", "niches", "niches")],
             {"REPORT_TITLE": "Cell-type Deconvolution & Niches"}),
    ]
    gpu = variant == "gpu"
    return {
        "name": "Cell-type Deconvolution & Niches" + (" (GPU)" if gpu else ""),
        "summary": ("Visium + scRNA-seq reference: cell2location on GPU, co-location groups, niches." if gpu else
                    "Visium + scRNA-seq reference: cell2location abundances per spot, co-location groups, niches."),
        "description": (
            "Estimates the cell-type composition of every Visium spot from a single-cell reference and "
            "maps how cell types organize in the tissue. Reads Space Ranger or AnnData input (st-prep), "
            "filters and normalizes spots (st-qc), runs cell2location (Kleshchevnikov et al. 2022) with "
            "reference signatures estimated from the scRNA-seq reference, reports per-spot cell "
            "abundances, the dominant type per spot and co-location groups, scores neighbourhood "
            "enrichment and cellular niches of each spot's strongest co-location group (squidpy), and "
            "writes an HTML report with tables." + (" Runs cell2location's GPU variant (CUDA PyTorch, the "
            "tutorial's 30,000 epochs) on a GPU compute node." if gpu else " Runs cell2location's CPU variant "
            "(5,000 epochs); use the GPU workflow where a GPU node is available.")),
        "inputs": [
            spatial_input("A folder of Space Ranger outputs (one per sample) or AnnData .h5ad files, "
                          "plus an optional samples.csv.", row=1),
            {"id": "reference", "name": "scRNA-seq reference",
             "description": "An AnnData .h5ad of single-cell RNA-seq from the same tissue: raw counts, "
                            "a cell-type column (CELL_TYPE_COLUMN, default cell_type), gene symbols.",
             "position": {"x": 40, "y": 40 + ROW * 3}},
        ],
        "processors": steps,
        "outputs": [
            output("report_out", "Report", "report", "report", "derivatives/deconvolution/report", 6, 1),
            output("tables_out", "Tables", "report", "tables", "derivatives/deconvolution/tables", 6, 2),
            output("abundance_out", "Cell-type abundances", "deconvolution", "labels",
                   "derivatives/deconvolution/cell2location", 6, 3),
            output("model_out", "Reference signatures & model", "deconvolution", "model",
                   "derivatives/deconvolution/model", 6, 4),
            output("niches_out", "Niches", "niches", "niches", "derivatives/deconvolution/niches", 6, 5),
        ],
    }


def profiling():
    steps = [
        PREP(1, 2),
        QC(2, 2),
        step("celltype", "st-celltype", 3, 2, ["qc", "prep"], [QCD, META]),
        step("niches", "st-niches", 4, 1, ["celltype", "qc", "prep"],
             [QCD, ("celltype", "labels", "labels"), META],
             {"LABEL_COLUMN": "cell_type", "LABEL": "cell-type"}),
        step("ccc", "st-ccc", 4, 3, ["celltype", "qc", "prep"],
             [QCD, ("celltype", "labels", "labels"), META],
             {"LABEL_COLUMN": "cell_type", "LABEL": "cell-type"}),
        step("report", "st-report", 5, 2, ["prep", "qc", "celltype", "niches", "ccc"],
             [META, ("qc", "qc", "qc"), ("celltype", "labels", "celltype"),
              ("celltype", "figures", "celltype-figures"), ("niches", "niches", "niches"),
              ("ccc", "ccc", "ccc")],
             {"REPORT_TITLE": "Single-cell Spatial Profiling"}),
    ]
    return {
        "name": "Single-cell Spatial Profiling",
        "summary": "Xenium/MERSCOPE/CosMx: QC, clustering and cell typing, niches, ligand-receptor signalling.",
        "description": (
            "Profiles imaging-based single-cell spatial transcriptomics (10x Xenium, Vizgen MERSCOPE, "
            "NanoString CosMx). Reads the platform's cell-by-gene output (st-prep), filters and "
            "normalizes cells (st-qc), clusters cells across samples and labels them from canonical "
            "or user-supplied marker sets (st-celltype), scores neighbourhood enrichment, co-occurrence "
            "and cellular niches (st-niches, squidpy), infers ligand-receptor communication between cell "
            "types and in space with LIANA+ (st-ccc), and writes an HTML report with tables."),
        "inputs": [spatial_input(
            "A folder with one Xenium, MERSCOPE or CosMx output folder per sample (cell-by-gene matrix "
            "and cell metadata), or AnnData .h5ad / SpatialData .zarr files, plus an optional "
            "samples.csv and markers.csv.")],
        "processors": steps,
        "outputs": [
            output("report_out", "Report", "report", "report", "derivatives/spatial-profiling/report", 6, 1),
            output("tables_out", "Tables", "report", "tables", "derivatives/spatial-profiling/tables", 6, 2),
            output("celltype_out", "Cell types", "celltype", "labels", "derivatives/spatial-profiling/cell-types", 6, 3),
            output("niches_out", "Niches", "niches", "niches", "derivatives/spatial-profiling/niches", 6, 4),
            output("ccc_out", "Cell-cell communication", "ccc", "ccc", "derivatives/spatial-profiling/ccc", 6, 5),
            output("qc_spatial_out", "QC'd AnnData", "qc", "spatial", "", 6, 6, default=False),
        ],
    }


def main():
    out = ROOT / "workflow"
    out.mkdir(exist_ok=True)
    for name, wf in (("spatial-domain-mapping", domains()),
                     ("cell-type-deconvolution-niches", deconvolution()),
                     ("cell-type-deconvolution-niches-gpu", deconvolution("gpu")),
                     ("single-cell-spatial-profiling", profiling())):
        assert len(wf["summary"].encode()) <= 100, (name, len(wf["summary"].encode()))
        (out / f"{name}.json").write_text(json.dumps(wf, indent=2) + "\n")
        print(f"wrote workflow/{name}.json ({len(wf['processors'])} steps)")


if __name__ == "__main__":
    main()
