---
title: "EMR provider"
permalink: "/docs/reference/providers/emr/"
layout: "post"
order: 4
source: "https://github.com/sean-mca/yard/blob/main/docs/reference/providers/emr.md"
---

> **Moved.** As of yard v2.0, the EMR provider is a plugin distributed separately from the yard CLI. The compiled-in EMR provider was removed in v2.0.

No EMR plugin has been published yet. When one ships it will live alongside the Glue and Airflow plugins in the [yard-plugins](https://github.com/sean-mca/yard-plugins) repository and be referenced from a job file with `type: emr` plus `plugin_version` and `plugin_source`.

To build one yourself, follow [build a plugin]({% link _plugins/how-to-build-a-plugin.md %}).

For upgrading from v1.x, see the [v2.0 migration guide]({% link _howto/reference-migrations-v2.0.md %}).

---

<small>This page is generated from [the repository](https://github.com/sean-mca/yard/blob/main/docs/reference/providers/emr.md). Edit it there.</small>
