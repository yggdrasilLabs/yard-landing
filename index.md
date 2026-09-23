---
layout: home
title: yard
permalink: /
---

yard is a command-line tool for deploying data pipelines from YAML. You write
one file per job, run `yard plan` to see what would change, and `yard apply`
to make the change. Providers such as AWS Glue and Airflow are plugins that
yard downloads and runs as separate processes.

If you have used Terraform or Terragrunt, most of this will be familiar:
declarative config, a plan and apply cycle, state that records what was
deployed, and providers that live outside the core binary. The differences
are that the config describes ETL jobs (sources, transforms, a sink) rather
than cloud resources, and that directories carry context the way they do in
Terragrunt, so account and region settings are written once and inherited.

## Install

{% include install-tabs.html %}

Prebuilt binaries for macOS and Linux are also on [GitHub Releases]({{ site.releases_url }}).
The [quickstart]({% link _start/quickstart.md %}) goes from an empty directory
to a deployed Glue job.

## Job files

A job file says which plugin handles it, where the data comes from, what to do
with it, and where it goes. Which account and region it deploys to, and which
bucket the script lands in, come from the directory it sits in.

```yaml
# aws/dev/us-east-1/orders.yaml
type: glue
plugin_version: "0.1.0"
plugin_source: "https://github.com/sean-mca/yard-plugins/releases/download/v0.1.0/yard-plugin-glue-0.1.0-aarch64-apple-darwin"
role: arn:aws:iam::123456789012:role/GlueJobExecutionRole

sources:
  - name: orders
    type: s3
    format: parquet
    path: s3://data-lake/raw/orders/

transforms:
  - type: filter
    source: orders
    output: active_orders
    condition: F.col("status") != "cancelled"

sink:
  source: active_orders
  type: s3
  format: parquet
  path: s3://data-lake/curated/orders/
  mode: overwrite
```

yard merges the job with the context from its parent directories and sends
the result to the plugin. For Glue, the plugin turns it into a PySpark script,
uploads the script to S3, and creates or updates the Glue job.

The built-in transforms are `sql`, `filter`, `select`, `rename`,
`drop_columns`, `add_column`, `join`, `aggregate`, and `window`, plus
`mask_pii` for redacting PII columns. If none of those fit, `body` appends
your own Python to the generated script and `job_file` replaces it entirely.
The [configuration reference]({% link _reference/reference-configuration.md %})
lists every field.

## Plan and apply

`yard plan` asks each job's plugin for the script it would generate, hashes
that together with the merged config, and compares the hash with what was last
applied. The output lists the jobs it would create, update, or destroy. Nothing
changes until you run `yard apply`.

```console
$ yard plan
Downloading yard-plugin-glue v0.1.0...
Done.

--- Plan for my-project ---

  + Create job [orders]

$ yard apply --auto-approve
Applying...
  + Created: orders

State updated successfully.
```

State and locks are kept per job, so two people or two CI runs deploying
different jobs do not block each other. `--target` limits a run to one job and
`--dir` to one directory. `--dry-run` and `--auto-approve` are there for CI.

## Project layout

A project is a directory tree with `yard.yaml` at the root. Directories for
accounts and regions each hold a context file, `account.yaml` or
`region.yaml`, that applies to every job underneath it. Job files refer to
context values with `${account.id}`, `${region.id}`, and so on.

```
my-project/
  yard.yaml              # project name, state backend
  aws/
    dev/
      account.yaml       # applies to every job below
      us-east-2/
        region.yaml
        orders.yaml
        customers.yaml
    prod/
      account.yaml
      us-east-1/
        region.yaml
        orders.yaml
```

The same `orders.yaml` works in dev and prod because the account and region
details come from the directories, not from the job file.

## Plugins

The yard binary has no provider code in it. For each operation it starts the
plugin binary, writes one JSON request to stdin, reads one JSON response from
stdout, and the plugin exits. yard handles the rest: reading the config tree,
working out diffs, locking, and downloading plugin binaries from GitHub
Releases the first time a job needs them. Their checksums go in `yard.lock`,
which you commit.

A plugin implements six operations:

| Operation | What it does |
|-----------|--------------|
| `validate` | Check the job config and return field-level errors |
| `codegen` | Turn the job config into an artifact, such as a PySpark script |
| `deploy` | Upload the artifact and create or update the cloud resource |
| `destroy` | Delete the resources recorded from a previous deploy |
| `verify` | Report whether each recorded resource still exists |
| `schema` | Describe the config fields the plugin accepts |

Two plugins exist so far, both in the [yard-plugins]({{ site.plugins_url }})
repository:

| Plugin | Language | What it deploys |
|--------|----------|-----------------|
| `yard-plugin-glue` | Rust | AWS Glue ETL jobs. Generates PySpark from the sources, transforms, and sink, uploads it to S3, and creates or updates the Glue job. |
| `yard-plugin-airflow` | Python | Airflow DAG files uploaded to S3, with schedule, dataset, S3, SQS, and API triggers. |

There is a Rust SDK, `yard-plugin-sdk`, that handles the protocol for you, but
it is not required. The Airflow plugin is a single Python file with no SDK.
[Build a plugin]({% link _plugins/how-to-build-a-plugin.md %}) walks through
both.

## CLI

| Command | Purpose |
|---------|---------|
| `yard init` | Scaffold a new project |
| `yard validate` | Check every job definition |
| `yard plan` | Show what would change |
| `yard apply` | Deploy changes, with confirmation |
| `yard show <job>` | Print the generated script |
| `yard list targets` | List deployable targets as JSON |
| `yard destroy [job]` | Tear down deployed jobs |
| `yard force-unlock <job>` | Remove a stale lock |

The [CLI reference]({% link _reference/reference-cli.md %}) has every flag.

## License

yard is written in Rust and released under the
[Business Source License 1.1]({{ site.github_url }}/blob/main/LICENSE).
