"""Adjust SDK-only build machinery, never package definitions or local feed."""
from pathlib import Path
import sys

sdk = Path(sys.argv[1])
target = sys.argv[2]
assert target in ('omnia', 'x86_64')
path = sdk / 'package/Makefile'
text = path.read_text()
text = text.replace('package-y += kernel/linux\n', '')
marker = '-include $(TMP_DIR)/.packagedeps\n'
assert marker in text, 'Unsupported SDK package build infrastructure'
# The unselected blockd sibling contributes autofs to fstools' dependencies.
# Apply the filter after generated metadata is loaded so regeneration is safe.
override = '$(curdir)/feeds/base/fstools/compile := $(filter-out $(curdir)/kernel/linux/compile,$($(curdir)/feeds/base/fstools/compile))\n'
if override not in text:
    text = text.replace(marker, marker + override)
path.write_text(text)
if target == 'x86_64':
    # Preserve Salt's unpruned installation for its own source-file audit.
    path = sdk / 'include/package.mk'
    text = path.read_text()
    original = 'ifneq ($(CONFIG_AUTOREMOVE),)'
    replacement = 'ifneq ($(if $(filter python-salt,$(PKG_NAME)),,$(CONFIG_AUTOREMOVE)),)'
    assert original in text or replacement in text, 'Unsupported SDK autoremove infrastructure'
    path.write_text(text.replace(original, replacement))
