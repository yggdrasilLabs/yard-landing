---
title: "Migrating to v2.0"
permalink: "/docs/reference/migrations/v2.0/"
layout: "post"
order: 3
source: "https://github.com/sean-mca/yard/blob/main/docs/reference/migrations/v2.0.md"
---

v2.0 moves all provider logic out of the yard binary and into plugin binaries. Providers are now separate executables that yard downloads and runs on demand via JSON-over-stdio. The Glue and Airflow plugins live in the [yard-plugins](https://github.com/sean-mca/yard-plugins) repository. This is a breaking change -- existing `job.yaml` files must declare their plugin version and download source.

## TL;DR breaking changes

| Area | v1.x | v2.0 | Notes |
|------|------|------|-------|
| Provider resolution | Compiled-in Glue/EMR/Bash providers | Plugin binaries (`yard-plugin-glue`, `yard-plugin-airflow`) | Plugins ship from the `yard-plugins` repo and release independently of yard |
| Job config | `type: glue` (no other fields needed) | `type: glue` + `plugin_version` + `plugin_source` required | Two new required fields per job |
| First run | `yard plan` just works | `yard plan` auto-downloads plugin binary on first use | Binary cached at `.yard/plugins/` |
| Validation | Built-in provider config checks | Plugin `schema()` drives validation | Provider-specific field validation moves to the plugin |
| Codegen | Built-in PySpark generation | Plugin `codegen()` operation | Script generation is provider-specific |
| DAG generation | Built-in Airflow DAG codegen | Moved to `yard-plugin-airflow` | `yard show dag` no longer available |
| Dependencies | `aws-sdk-glue`, `aws-sdk-emr`, `tera` compiled in | Removed from yard binary | Smaller binary, fewer transitive deps |
| `yard show dag` | Shows generated DAG Python | Removed | DAG generation is now plugin responsibility |

## Step-by-step upgrade

### Step 1: Update job.yaml files

Add `plugin_version` and `plugin_source` to every job file. The `type:` field stays the same -- you are adding two fields, not changing the type.

**Before (v1.x):**

```yaml
# job.yaml
type: glue
role: arn:aws:iam::123456789012:role/my-glue-role
sources:
  - name: orders
    type: s3
    path: s3://my-bucket/raw/orders/
    format: parquet
transforms:
  - type: filter
    source: orders
    output: orders_paid
    condition: F.col("status") == "paid"
sink:
  source: orders_paid
  type: s3
  path: s3://my-bucket/curated/orders_paid/
  format: parquet
  mode: overwrite
```

**After (v2.0):**

```yaml
# job.yaml
type: glue
plugin_version: "0.1.0"
plugin_source: "https://github.com/sean-mca/yard-plugins/releases/download/v0.1.0/yard-plugin-glue-0.1.0-aarch64-apple-darwin"
role: arn:aws:iam::123456789012:role/my-glue-role
sources:
  - name: orders
    type: s3
    path: s3://my-bucket/raw/orders/
    format: parquet
transforms:
  - type: filter
    source: orders
    output: orders_paid
    condition: F.col("status") == "paid"
sink:
  source: orders_paid
  type: s3
  path: s3://my-bucket/curated/orders_paid/
  format: parquet
  mode: overwrite
```

The `plugin_source` URL uses template placeholders that yard expands at download time:

| Placeholder | Expands to | Values |
|-------------|------------|--------|
| `${name}` | `yard-plugin-<job type>` | `yard-plugin-glue` for `type: glue` |
| `${version}` | Value of `plugin_version` | `0.1.0` |
| `${os}` | `std::env::consts::OS` | `macos`, `linux` |
| `${arch}` | `std::env::consts::ARCH` | `aarch64`, `x86_64` |

`${os}` is the Rust `consts` spelling, **not** the target triple: it expands to
`macos` / `linux`, never `apple-darwin` / `unknown-linux-gnu`. Plugin release
assets must be named to match, or the first `yard plan` 404s.
> **Known limitation (v2.0).** Placeholder templating is **not currently usable
> inside a `<job>.yaml`**. yard runs `${...}` context interpolation over the whole
> job file before parsing it, so a `plugin_source` containing `${version}`,
> `${os}` or `${arch}` fails to resolve with
> `Missing Variable: Could not find 'version' in the provided context`. This
> applies to YAML comments too. Until that is fixed, write the fully expanded
> URL for the platform you are on:
>
> ```yaml
> plugin_source: "https://github.com/sean-mca/yard-plugins/releases/download/v0.1.0/yard-plugin-glue-0.1.0-aarch64-apple-darwin"
> ```
>
> The placeholder expansion itself works correctly once a template reaches the
> downloader -- it is only the job-file interpolation pass that rejects it.

There is no EMR plugin yet, so `type: emr` jobs cannot be deployed on v2.0 until one is published. See [providers/emr.md]({% link _plugins/reference-providers-emr.md %}).

### Step 2: First plan/apply

Run `yard plan` after updating your job files. On first use, yard auto-downloads the plugin binary:

```
$ yard plan
Downloading yard-plugin-glue v0.1.0...
Done.

Plan: 1 to create, 0 to update, 0 to destroy
```

The binary is cached at `.yard/plugins/yard-plugin-glue-0.1.0-<arch>-<os>` (e.g. `...-aarch64-macos`) and reused on subsequent runs. No re-download unless the version changes.

yard also writes a `yard.lock` file in your project root. This file records the SHA-256 checksum of each downloaded plugin binary (trust on first use). The checksum is verified on every subsequent run.

### Step 3: Verify

Run `yard plan` to confirm everything works. If you see this error:

```
Error: provider 'glue' is now a plugin -- add plugin_version and plugin_source
to your job.yaml, see docs/reference/migrations/v2.0.md
```

It means one or more job files are missing the `plugin_version` and `plugin_source` fields. Update them per Step 1.

### Step 4: DAG users

Airflow DAG generation is no longer built into yard and the `yard show dag` command has been removed. DAGs are now produced by `yard-plugin-airflow`, which renders a DAG file and uploads it to S3. It is a job type like any other, with `plugin_version` and `plugin_source` pointing at a [yard-plugins release](https://github.com/sean-mca/yard-plugins/releases). The `airflow:` block that v1.x read from job files is ignored by core now; the plugin's README lists the fields it expects.

### Step 5: Team rollout

Commit `yard.lock` to version control. This file uses a TOFU (trust on first use) model:

1. The first team member to run `yard plan` downloads the plugin and records its checksum.
2. Other team members on the same platform verify against that checksum automatically.
3. Team members on different platforms (e.g. macOS vs. Linux) accumulate their platform-specific checksums in the same lock file.

The lock file grows organically as your team uses yard across platforms. No manual checksum management needed.

## See also

- [Plugin author guide]({% link _plugins/how-to-build-a-plugin.md %}) -- how to build a provider plugin from scratch

---

<small>This page is generated from [the repository](https://github.com/sean-mca/yard/blob/main/docs/reference/migrations/v2.0.md). Edit it there.</small>
