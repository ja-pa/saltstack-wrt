include $(TOPDIR)/rules.mk
PKG_NAME:=python-zipp
PKG_VERSION:=3.20.2
PKG_RELEASE:=1
PYPI_NAME:=zipp
PKG_HASH:=bc9eb26f4506fda01b81bcde0ca78103b6e62f991b381fec825435c836edbc29
PKG_LICENSE:=MIT
PKG_LICENSE_FILES:=LICENSE
PKG_BUILD_DEPENDS:=python-setuptools-scm/host
HOST_BUILD_DEPENDS:=python3/host python-build/host python-installer/host python-setuptools-scm/host
include $(TOPDIR)/feeds/packages/lang/python/pypi.mk
include $(INCLUDE_DIR)/package.mk
include $(INCLUDE_DIR)/host-build.mk
include $(TOPDIR)/feeds/packages/lang/python/python3-package.mk
include $(TOPDIR)/feeds/packages/lang/python/python3-host-build.mk
define Package/python3-zipp
  SECTION:=lang
  CATEGORY:=Languages
  SUBMENU:=Python
  TITLE:=Zipfile object wrapper
  DEPENDS:=+python3-light +python3-urllib
endef
$(eval $(call Py3Package,python3-zipp))
$(eval $(call BuildPackage,python3-zipp))
$(eval $(call BuildPackage,python3-zipp-src))
$(eval $(call HostBuild))
