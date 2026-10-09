include $(TOPDIR)/rules.mk
PKG_NAME:=python-importlib-metadata
PKG_VERSION:=8.7.0
PKG_RELEASE:=1
PYPI_NAME:=importlib_metadata
PKG_HASH:=d13b81ad223b890aa16c5471f2ac3056cf76c5f10f82d6f9292f0b415f389000
PKG_LICENSE:=Apache-2.0
PKG_LICENSE_FILES:=LICENSE
PKG_BUILD_DEPENDS:=python-setuptools-scm/host
HOST_BUILD_DEPENDS:=python3/host python-build/host python-installer/host python-setuptools-scm/host python-zipp/host
include $(TOPDIR)/feeds/packages/lang/python/pypi.mk
include $(INCLUDE_DIR)/package.mk
include $(INCLUDE_DIR)/host-build.mk
include $(TOPDIR)/feeds/packages/lang/python/python3-package.mk
include $(TOPDIR)/feeds/packages/lang/python/python3-host-build.mk

define Package/python3-importlib-metadata
  SECTION:=lang
  CATEGORY:=Languages
  SUBMENU:=Python
  TITLE:=Python distribution metadata
  DEPENDS:=+python3-light +python3-zipp
endef
$(eval $(call Py3Package,python3-importlib-metadata))
$(eval $(call BuildPackage,python3-importlib-metadata))
$(eval $(call BuildPackage,python3-importlib-metadata-src))
$(eval $(call HostBuild))
