# /// script
# requires-python = ">=3.12"
# dependencies = ["marimo", "marimo-lens==0.2.4", "polars", "wigglystuff==0.5.36"]
# ///

import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")


@app.cell
def imports():
    import os
    import marimo as mo
    import polars as pl
    from wigglystuff import EnvConfig
    from marimo_lens import Lens

    return EnvConfig, Lens, mo, os


@app.cell
def intro(mo):
    mo.md("""
    # Sync R2
    Configure the R2 destination. Enter model names below until the model-selection cells are added.
    """)
    return


@app.cell
def r2_settings(EnvConfig, list_of_files, mo, os, project_picker):
    # The S3 API URL is not secret, so it is a plain text field; the keys stay hidden
    r2_s3_api = mo.ui.text(
        value=os.environ.get("R2_S3_API", ""),
        placeholder="https://<account id>.eu.r2.cloudflarestorage.com/<bucket>",
        label="R2_S3_API",
        full_width=True,
    )
    r2_config = mo.ui.anywidget(EnvConfig(["R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"]))
    # The picked models' common name, such as rvt-advanced-sample, else the project id
    _common = os.path.commonprefix(list_of_files).rstrip("-_ ")
    r2_prefix = mo.ui.text(
        value=f"bimpolars/{_common or project_picker.value}",
        label="Prefix",
        full_width=True,
    )
    mo.vstack([r2_s3_api, r2_config, r2_prefix])
    return


@app.cell
def lens_widget(Lens):
    lens = Lens()
    lens
    return


if __name__ == "__main__":
    app.run()
