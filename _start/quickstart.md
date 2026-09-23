---
title: "Getting Started"
permalink: "/docs/quickstart/"
layout: "post"
order: 2
source: "https://github.com/sean-mca/yard/blob/main/docs/quickstart.md"
---

This guide walks you from zero to a deployed AWS Glue job managed by yard. It
covers prerequisites, installing yard, scaffolding a project, authoring one
job, and running `yard plan` / `yard apply` to deploy it.

If you just want to skim, the shortest possible path is:

```bash
brew install sean-mca/yard/yard
mkdir my-project && cd my-project && yard init
# edit yard.yaml + add one <job>.yaml, then:
yard validate
yard plan
yard apply
```

The rest of this document explains each step.

---

## Prerequisites

### Rust toolchain (source builds only)

If you install yard with Homebrew or a release binary, skip this section.

Building from source needs `cargo`. The workspace uses Rust **edition 2024**,
which requires **Rust 1.85 or newer**. CI builds against `stable` on
`ubuntu-latest` (see `.github/workflows/ci.yml`), so any recent stable release
works.

If you don't have Rust installed:

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
# then restart your shell, or:
source "$HOME/.cargo/env"
```

Verify:

```bash
cargo --version   # cargo 1.85 or newer
rustc --version   # rustc 1.85 or newer
```

### AWS credentials (for the `glue` and `emr` providers)

yard does not ship its own credential manager — it uses the standard AWS SDK
default credential chain (env vars → `~/.aws/credentials` → IMDS → SSO). Any
one of these works:

- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN` exported
  in your shell.
- `aws configure --profile <name>` followed by `export AWS_PROFILE=<name>`.
- An EC2 / ECS / Lambda instance role.
- `aws sso login` against a configured SSO profile.

Verify credentials resolve:

```bash
aws sts get-caller-identity
```

Your caller identity needs permission to:

- **S3:** `PutObject`, `GetObject`, `DeleteObject`, `HeadBucket`, `ListBucket`
  on the script bucket and (if used) the state bucket.
- **Glue:** `CreateJob`, `UpdateJob`, `DeleteJob`, `GetJob`, `StartJobRun`,
  and `PassRole` for the Glue execution role referenced in each job file.
- **EMR** (only if using the EMR provider): `AddJobFlowSteps`,
  `DescribeStep`, `CancelSteps` on the target cluster.

If you plan to use AssumeRole (for cross-account deploys), yard also reads
`YARD_AWS_ASSUME_ROLE`, `YARD_AWS_SESSION_NAME`, and `YARD_AWS_EXTERNAL_ID`
env vars — see [configuration]({% link _reference/reference-configuration.md %}#yard-cli-environment-variables).

### S3 bucket(s)

You need at least one S3 bucket that yard can write generated PySpark scripts
to. This is the `providers.glue.script_bucket` (or
`providers.emr.script_bucket`) in `yard.yaml`. The bucket must exist before
you run `yard apply` — yard does not create it for you.

If you also want to use the S3 state backend (recommended for anything beyond
a single-developer prototype), you need a second bucket for state. Local
state is fine for getting started.

### AWS CLI (optional but useful)

Not required by yard, but handy for verifying the resources yard creates. Any
recent v2 release works:

```bash
aws --version
```

---

## Installation

### Homebrew (recommended)

Works on macOS and Linux:

```bash
brew install sean-mca/yard/yard
```

Later releases are picked up with `brew upgrade yard`.

### Release binary

Every release attaches a tarball per platform (macOS Apple Silicon and Intel,
Linux x86_64 and ARM) to [GitHub Releases](https://github.com/sean-mca/yard/releases).
Download the one for your platform, extract it, and put the `yard` binary on
your `PATH`. See [Upgrade yard]({% link _howto/how-to-upgrade-yard.md %}#from-a-github-release-binary)
for the checksum-verified procedure.

### Build from source

For contributors, or platforms without a prebuilt binary. Requires the Rust
toolchain from [Prerequisites](#rust-toolchain-source-builds-only).

```bash
git clone https://github.com/sean-mca/yard.git
cd yard
cargo build --release
```

The resulting binary is at `target/release/yard`. Either add that directory to
your `PATH` for the session:

```bash
export PATH="$PWD/target/release:$PATH"
```

or install it into `~/.cargo/bin` permanently:

```bash
cargo install --path yard-cli
```

### Verify the install

```bash
yard --version
yard --help
```

You should see the subcommands `init`, `plan`, `apply`, `show`, `validate`,
`list`, `destroy`, `force-unlock`. The `list` subcommand (added in v1.3.4)
emits `yard list targets [--json]` rows for CI matrix builders fanning out
per-account deploys; see [reference/cli.md]({% link _reference/reference-cli.md %}) for the full
flag surface.

---

## Your first job — a minimal tutorial

We will create a one-job project that filters an S3 dataset with Glue.

### 1. Scaffold the project

```bash
mkdir ~/yard-tutorial
cd ~/yard-tutorial
yard init
```

`yard init` writes a starter `yard.yaml` with a `local` state backend and
creates the state directory. After it finishes you should see:

```
Created <path>/yard.yaml
Initialized state at .yard/state
```

The generated `yard.yaml` looks like:

```yaml
project: my-yard-project

state:
  type: local
  path: .yard/state

providers:
```

### 2. Fill in the Glue provider block

Open `yard.yaml` and add a `glue:` key under `providers:` pointing at the S3
bucket where yard should upload generated scripts. Replace the placeholder
values with your own bucket and region:

```yaml
project: yard-tutorial

state:
  type: local
  path: .yard/state

providers:
  glue:
    script_bucket: my-yard-scripts-bucket
    region: us-east-1
```

Since v2.0 the fields under `providers.glue` are defined by the Glue plugin,
not by yard — see [`providers.<type>`]({% link _reference/reference-configuration.md %}#providerstype--provider-defaults)
and the [yard-plugins](https://github.com/sean-mca/yard-plugins) repository for
the full list (worker type, Glue version, bookmarks, connections, etc.). The
plugin's defaults (`script_prefix: yard-scripts/`, `glue_version: 4.0`,
`worker_type: G.1X`, `number_of_workers: 2`) are fine for this tutorial.

### 3. Add one job

Create a file `orders.yaml` next to `yard.yaml`:

```yaml
type: glue
plugin_version: "0.1.0"
plugin_source: "https://github.com/sean-mca/yard-plugins/releases/download/v0.1.0/yard-plugin-glue-0.1.0-aarch64-apple-darwin"
role: arn:aws:iam::123456789012:role/GlueJobExecutionRole

sources:
  - name: orders
    type: s3
    format: parquet
    path: s3://my-data-lake/raw/orders/

transforms:
  - type: filter
    condition: "col('status') != 'cancelled'"

sink:
  type: s3
  format: parquet
  path: s3://my-data-lake/curated/orders/
  mode: overwrite
```

`type: glue` selects the Glue provider plugin. `plugin_version` and
`plugin_source` are required on every job in v2.0: they tell yard which plugin
release to download and from where. Pick the release asset for your platform
(`aarch64-apple-darwin`, `x86_64-apple-darwin`, `x86_64-unknown-linux-gnu`,
or `aarch64-unknown-linux-gnu`) from the
[yard-plugins releases](https://github.com/sean-mca/yard-plugins/releases).

Replace the `role` ARN, the `sources[0].path`, and the `sink.path` with real
values in your account. The `role` is the IAM role Glue assumes when running
the job — it must be able to read from the source path and write to the sink
path.

Your project directory now looks like:

```
yard-tutorial/
  yard.yaml
  orders.yaml
  .yard/
    state/
```

The filename `orders.yaml` becomes the job name (`orders`) — yard discovers
job files by walking the directory tree from `yard.yaml` downward. For a
hierarchical multi-account layout (e.g. `aws/dev/us-east-2/orders.yaml`), see
the project structure section of the [README](https://github.com/sean-mca/yard/blob/main/README.md#project-structure)
and the context-inheritance rules in
[configuration]({% link _reference/reference-configuration.md %}#accountyaml--regionyaml-hierarchical-context).

### 4. Validate the job

```bash
yard validate
```

Expected output:

```
Validating project: yard-tutorial

[PASS] orders.yaml

Validation complete: 1 passed, 0 failed
```

If you mistyped a field (e.g. `type: gluue`), `yard validate` will print the
offending file, the field path, and an actionable error. Fix the job file and
re-run. Validation also runs implicitly before `plan` and `apply`, but it is
faster to iterate on.

### 5. Plan the change

```bash
yard plan
```

Expected output for a first run:

```
Downloading yard-plugin-glue v0.1.0...
Done.

--- Plan for yard-tutorial ---

  + Create job [orders]
```

The first `plan` downloads the Glue plugin binary declared in `orders.yaml`,
caches it under `.yard/plugins/`, and records its SHA-256 checksum in
`yard.lock` at the project root. Commit `yard.lock`; later runs verify the
cached binary against it and never re-download unless `plugin_version`
changes.

The `+` means "create" — yard has no existing state for `orders` and will
create it on apply. Subsequent runs after an `apply` show `No changes`
until you edit `orders.yaml`, at which point a `~ Modify` line appears with
the changed field names.

You can inspect the PySpark script the plugin generated, without deploying
anything:

```bash
yard show orders
```

This asks the plugin for its `codegen` output and prints the Python to stdout. Pipe it to a file if you want to
review it (`yard show orders > orders.py`).

### 6. Apply

```bash
yard apply
```

yard prints the same plan again and then prompts:

```
Do you want to apply these changes? (y/n)
```

Type `y` (or re-run with `--auto-approve` to skip the prompt). yard takes a
lock on the `orders` job and hands the generated script to the Glue plugin,
which:

1. Uploads it to `s3://my-yard-scripts-bucket/yard-scripts/orders.py`
   (bucket + prefix from your `providers.glue` config).
2. Calls `glue:CreateJob` to create the Glue job named `orders`.

yard then records the resources the plugin reported in
`.yard/state/orders.json` and releases the lock.

Expected output:

```
Applying...
  + Created: orders

State updated successfully.
```

That's a complete deploy.

---

## Verifying the job ran

`yard apply` creates the Glue job definition but does not execute a run — you
still control when the job runs. Verify the deploy landed in AWS:

### Check the Glue job exists

```bash
aws glue get-job --job-name orders --region us-east-1
```

You should see a `Job` payload with `Role`, `Command.ScriptLocation` pointing
at your `s3://…/yard-scripts/orders.py`, and the default `GlueVersion`,
`WorkerType`, and `NumberOfWorkers` from your `providers.glue` block.

### Check the uploaded script

```bash
aws s3 ls s3://my-yard-scripts-bucket/yard-scripts/
```

You should see `orders.py` with a recent timestamp.

### Check yard's state

```bash
cat .yard/state/orders.json
```

This is the per-job state file. It contains a `config_hash` (BLAKE3 of the
script + merged config), the `resources` list the plugin created, the plugin
version and source used, the applied timestamp, and the full merged config.

### Run the job (optional)

If you actually want Glue to execute the job:

```bash
aws glue start-job-run --job-name orders --region us-east-1
```

Then watch the run:

```bash
aws glue get-job-runs --job-name orders --region us-east-1 --max-items 1
```

Running the job exercises the PySpark script the Glue plugin generated
against your real data, not yard itself. yard's responsibility ends at the
deploy.

---

## Common setup issues

**`aws sts get-caller-identity` fails with "Unable to locate credentials."**

The AWS SDK default chain could not find credentials. Run `aws configure`
to set up `~/.aws/credentials`, or `export AWS_ACCESS_KEY_ID=…` directly,
or `aws sso login` against an SSO profile. Verify with
`aws sts get-caller-identity` before re-running yard.

**`yard plan` fails with `provider 'glue' is now a plugin -- add plugin_version and plugin_source`.**

The job file is missing the two plugin fields that v2.0 requires. Add
`plugin_version` and `plugin_source` as shown in step 3; see the
[v2.0 migration guide]({% link _howto/reference-migrations-v2.0.md %}) if you are upgrading an
existing project.

**`yard plan` fails while downloading the plugin (404 or checksum mismatch).**

A 404 means the `plugin_source` URL does not match a release asset — check the
version and the platform suffix. A checksum mismatch means the cached binary
differs from what `yard.lock` recorded; delete the entry from `yard.lock` only
if you expect the binary to have changed.

**`yard apply` fails with `providers.glue.script_bucket is required`.**

You skipped step 2 — add a `glue:` block with a `script_bucket` under
`providers:` in `yard.yaml`.

**`yard apply` fails with `Job "orders" requires a "role"`.**

The job file needs a top-level `role:` field naming the IAM role Glue should
assume. This must be an ARN, not just a role name
(`arn:aws:iam::ACCOUNT:role/ROLE_NAME`).

**`yard apply` fails with `Failed to reach S3 bucket … in …`.**

The script bucket doesn't exist, is in a different region, or your
credentials can't see it. Create it first
(`aws s3 mb s3://my-yard-scripts-bucket --region us-east-1`), or update
`providers.glue.region` to match where the bucket actually lives.

**`cargo build --release` fails with an edition / toolchain error (source builds).**

Your Rust toolchain is older than 1.85. Update with `rustup update stable`
and try again.

**A second `yard apply` hangs or reports `stale lock`.**

yard uses per-job lock files in the state backend. If a previous run was
interrupted (SIGKILL, crashed CI runner), a stale lock may remain. Remove it
with:

```bash
yard force-unlock orders
```

Then re-run `yard apply`.

**Running `yard` commands outside the project root.**

Every subcommand takes an optional trailing directory argument
(`yard plan ~/yard-tutorial`), and internally `yard` walks upward looking for
`yard.yaml`. If you see "failed to find yard.yaml", you're either not inside
a yard project or you passed the wrong directory.

---

## Next steps

You now have a working single-job yard project. From here:

- **[architecture]({% link _reference/explanation-architecture.md %})** — how the yard-cli / yard-core /
  yard-structs crates fit together, the provider trait, state
  storage, and the end-to-end data flow for `plan` / `apply`.
- **[configuration]({% link _reference/reference-configuration.md %})** — the full reference for
  `yard.yaml`, `account.yaml`, `region.yaml`, per-job fields (plugin
  selection, sources, sinks, transforms, partitioning, PII masking), and
  every environment variable the CLI reads.
- **[build a plugin]({% link _plugins/how-to-build-a-plugin.md %})** — the plugin protocol and
  the Rust SDK, for adding a provider yard does not have yet.
- **[development]({% link _contributing/contributing-development.md %})** — how to work on yard itself — build
  commands, running tests, linting, and the workspace layout.
- **README project structure** — the [hierarchical multi-account
  layout](https://github.com/sean-mca/yard/blob/main/README.md#project-structure) for teams managing many accounts
  and regions.

---

<small>This page is generated from [the repository](https://github.com/sean-mca/yard/blob/main/docs/quickstart.md). Edit it there.</small>
