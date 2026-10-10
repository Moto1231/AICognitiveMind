## 2.0.0

* `brilliant-ble` and `brilliant-msg` are no longer bundled into this package's
  output. This meta-package now simply re-exports them and lets npm resolve them at
  install time, matching the Python and Dart meta-packages. The published bundle
  drops from roughly 1 MB to under 100 bytes, and dependency updates reach users
  without a new release of this package
* Breaking only for consumers loading the UMD build via a plain `<script>` tag: they
  must now load `brilliant-ble` and `brilliant-msg` first and expose them as the
  `brilliantBle` and `brilliantMsg` globals. Bundler and ESM consumers are unaffected
* Dependency ranges raised to `brilliant-ble ^1.1.0` and `brilliant-msg ^3.0.0`
* TypeScript pinned to an exact version so declaration output cannot shift with a
  minor compiler release

## 1.1.0

* Rebundles `brilliant-msg` 2.1.0 — the Halo firmware 0.8.8 true-up. `RxTap` now emits Halo's native tap kind (`single`/`double`/`triple`) directly instead of inferring it from timing, and the `tap.lua` and `sprite.lua` device libraries are updated to match
* `brilliant-msg` dependency floor raised to `^2.1.0`

Note: `brilliant-sdk` bundles `brilliant-ble` and `brilliant-msg` into its `dist/` output, so picking up a dependency update requires a new release of this package rather than just a re-install.

Releases before 1.1.0 predate this changelog; see the `brilliant-ble` and `brilliant-msg` changelogs for the corresponding history.
