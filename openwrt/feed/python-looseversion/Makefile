include $(TOPDIR)/rules.mk

PKG_NAME:=python-looseversion
PKG_VERSION:=1.3.0
PKG_RELEASE:=1
PYPI_NAME:=looseversion
PKG_HASH:=ebde65f3f6bb9531a81016c6fef3eb95a61181adc47b7f949e9c0ea47911669e
PKG_LICENSE:=PSF-2.0
PKG_LICENSE_FILES:=LICENSE
PKG_BUILD_DEPENDS:=python-hatchling/host
HOST_BUILD_DEPENDS:=python3/host python-build/host python-installer/host python-hatchling/host
include $(TOPDIR)/feeds/packages/lang/python/pypi.mk
include $(INCLUDE_DIR)/package.mk
include $(INCLUDE_DIR)/host-build.mk
include $(TOPDIR)/feeds/packages/lang/python/python3-package.mk
include $(TOPDIR)/feeds/packages/lang/python/python3-host-build.mk

define Package/python3-looseversion
  SECTION:=lang
  CATEGORY:=Languages
  SUBMENU:=Python
  TITLE:=Loose version comparison
  DEPENDS:=+python3-light
endef

$(eval $(call Py3Package,python3-looseversion))
$(eval $(call BuildPackage,python3-looseversion))
$(eval $(call BuildPackage,python3-looseversion-src))
$(eval $(call HostBuild))
