# Licensing

> **Stub.** This page will be expanded in the documentation rework. It records the
> licensing posture and where the authoritative artifacts live.

## The project's own license

Architectonic is published under the **MIT License** — see [`LICENSE`](../../LICENSE) at the
repository root. You may use, modify, and distribute it, including for commercial purposes and
integration into commercial products, subject only to preserving the copyright and permission
notice.

The SPDX identifier for the project is `MIT`. The license file rides in every artifact adopters
receive: the source tree, the Docker image (`/app/LICENSE`), and any published Python
wheel/sdist (`license-files`).

## Third-party components

Architectonic bundles, links, or invokes third-party components, each under its own license. All
are compatible with MIT redistribution — the stack is permissive (MIT/BSD/Apache/ISC/PSF), with a
few weak-copyleft components used at arm's length or unmodified, and no strong-copyleft component
linked into the project's own code.

The authoritative, generated list is [`THIRD-PARTY-NOTICES.md`](../../THIRD-PARTY-NOTICES.md) at
the repository root (shipped in the image and the source tree). It leads with the corresponding-
source pointers for the copyleft and weak-copyleft components and then lists the full permissive
inventory.

### Notable components

- **PlantUML** (diagram rendering) is GPLv3. It is bundled as the unmodified official jar and
  invoked as a **separate process** (`java -jar`), so under the GPLv3 aggregation clause it does
  not affect the license of Architectonic's own code. The corresponding-source offer is in the
  notices file.
- **Graphviz** (EPL-1.0) and the **cvss** library (LGPLv3+) are weak-copyleft, used unmodified /
  dynamically imported; their notices and source pointers are in the notices file.
- The bundled **JRE** is OpenJDK (GPLv2 with the Classpath Exception). A custom JRE can be
  supplied at runtime via the `ARCH_JAVA` environment variable without changing the default.

## How the inventory stays honest

The per-ecosystem inventories under [`licenses/`](../../licenses/) are generated and gated in CI:

- `tools/check_licenses.py --ecosystem python|npm --check` regenerates the inventory and fails on
  drift, or on any denied/unknown/unacknowledged-review license.
- `tools/generate_notices.py --check` fails if `THIRD-PARTY-NOTICES.md` is stale relative to the
  inventories.

After changing dependencies, run the `--write` variants and commit the regenerated files.

*Not legal advice.* The classifications encode compatibility with MIT redistribution; genuinely
ambiguous cases are flagged for review.
