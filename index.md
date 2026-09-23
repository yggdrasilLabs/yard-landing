---
layout: home
title: yard
permalink: /
---

yard is a command-line tool for deploying data pipelines from YAML. You write
one file per job, run `yard plan` to see what would change, and `yard apply`
to make the change. Providers are plugins that yard downloads and runs as
separate processes; yard itself creates nothing in your account.

If you have used Terraform or Terragrunt, most of this will be familiar:
declarative config, a plan and apply cycle, state that records what was
deployed, and providers that live outside the core binary. The differences
are that the config describes data jobs rather than cloud resources, and that
directories carry context the way they do in Terragrunt, so account and
region settings are written once and inherited.

## Install

{% include install-tabs.html %}

Prebuilt binaries for macOS and Linux are also on [GitHub Releases]({{ site.releases_url }}).
The [quickstart]({% link _start/quickstart.md %}) goes from an empty directory
to a deployed Glue job.

## Job files

A job file has three fields that belong to yard: `type`, which names the
plugin, and `plugin_version` and `plugin_source`, which say which release of
it to download. Everything else in the file is defined by the plugin, so a
job's shape depends on what it targets. Which account and region it deploys
to, and the provider settings that go with them, come from the directory it
sits in.

Here is a job for a Glue plugin, which describes a Spark job as sources,
transforms, and a sink:

```yaml
# aws/dev/us-east-1/orders.yaml
type: glue
plugin_version: "0.1.0"
plugin_source: "https://<plugin-release-url>/yard-plugin-glue-0.1.0-aarch64-macos"
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

A job for an Airflow plugin would carry a schedule and a list of tasks
instead, with no sources or sinks at all.

yard merges the job with the context from its parent directories and sends
the result to the plugin. The plugin turns it into whatever its target needs,
typically a generated script that it uploads and a job it creates or updates.
Anything the plugin needs beyond the job file, such as an execution role or a
bucket for scripts, is listed in the plugin's documentation and has to exist
before you apply. The [configuration reference]({% link _reference/reference-configuration.md %})
documents the fields yard itself parses, including the source, transform, and
sink model that script-generating plugins use.

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

`yard show <job>` prints what the plugin generated, so you can read it before
it goes anywhere. State and locks are kept per job, so two people or two CI
runs deploying different jobs do not block each other. `--target` limits a run to one job and
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
working out diffs, locking, and downloading plugin binaries from the URL each
job declares the first time they are needed. Their checksums go in
`yard.lock`, which you commit.

A plugin implements six operations:

| Operation | What it does |
|-----------|--------------|
| `validate` | Check the job config and return field-level errors |
| `codegen` | Turn the job config into an artifact, such as a PySpark script |
| `deploy` | Upload the artifact and create or update the cloud resource |
| `destroy` | Delete the resources recorded from a previous deploy |
| `verify` | Report whether each recorded resource still exists |
| `schema` | Describe the config fields the plugin accepts |

Plugins are published and documented separately from yard. Each one says
which job type it registers, which `providers.<type>` fields it accepts, and
which credentials and resources it needs. Those docs, not these, are where to
look for provider specifics.

There is a Rust SDK, `yard-plugin-sdk`, that handles the protocol for you, but
it is not required; the protocol is small enough to implement in any language.
[Build a plugin]({% link _plugins/how-to-build-a-plugin.md %}) walks through
it in Rust and in Python.

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
