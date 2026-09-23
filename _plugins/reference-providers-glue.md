---
title: "Glue provider"
permalink: "/docs/reference/providers/glue/"
layout: "post"
order: 3
source: "https://github.com/sean-mca/yard/blob/main/docs/reference/providers/glue.md"
---

> **Moved.** As of yard v2.0, the Glue provider is a plugin distributed separately from the yard CLI.

The Glue provider is `yard-plugin-glue`, a Rust plugin built on `yard-plugin-sdk` and maintained in the [yard-plugins](https://github.com/sean-mca/yard-plugins) repository. See its README for the accepted `providers.glue` fields, the generated PySpark, and local testing against a Glue emulator.

Reference it from a job file with `type: glue` plus `plugin_version` and `plugin_source` pointing at a [yard-plugins release](https://github.com/sean-mca/yard-plugins/releases).

For upgrading from v1.x, see the [v2.0 migration guide]({% link _howto/reference-migrations-v2.0.md %}).

---

<small>This page is generated from [the repository](https://github.com/sean-mca/yard/blob/main/docs/reference/providers/glue.md). Edit it there.</small>
