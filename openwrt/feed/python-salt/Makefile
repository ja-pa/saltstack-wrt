include $(TOPDIR)/rules.mk
PKG_NAME:=python-salt
PKG_VERSION:=3008.3
PKG_RELEASE:=10
PYPI_NAME:=salt
PKG_HASH:=4bfa995ecde1491916bc9fd0abebf38d39eaca24c1e99e29c5046b97b8754f30
PKG_LICENSE:=Apache-2.0
PKG_LICENSE_FILES:=LICENSE
PKG_BUILD_DEPENDS:=python-looseversion/host python-packaging/host python-importlib-metadata/host
include $(TOPDIR)/feeds/packages/lang/python/pypi.mk
include $(INCLUDE_DIR)/package.mk
include $(TOPDIR)/feeds/packages/lang/python/python3-package.mk
include $(CURDIR)/prune.mk

define Package/python3-salt
  SECTION:=lang
  CATEGORY:=Languages
  SUBMENU:=Python
  TITLE:=Salt shared Python runtime (TCP only)
  URL:=https://saltproject.io
  DEPENDS:=+python3 +python3-looseversion +python3-packaging \
    +python3-tornado +python3-msgpack +python3-jinja2 +python3-yaml \
    +python3-distro +python3-cryptography +python3-requests +python3-dateutil \
    +python3-psutil +python3-jmespath
endef

define Package/python3-salt/description
  Shared Python runtime for the Salt minion with TCP transport support.
  Provides the Salt libraries used by the minion and OpenWrt add-ons.
endef

define Package/salt-minion
  SECTION:=admin
  CATEGORY:=Administration
  TITLE:=Salt minion for OpenWrt
  DEPENDS:=+python3-salt
endef

define Package/salt-minion/description
  Salt minion for remote execution and configuration management on OpenWrt.
  Includes salt-minion, salt-call, and a procd init script.
  Requires a Salt master configured for TCP transport.
endef

define Package/minion-opkg
  SECTION:=admin
  CATEGORY:=Administration
  TITLE:=Salt minion opkg provider
  DEPENDS:=+salt-minion +python3-salt +opkg
  EXTRA_DEPENDS:=salt-minion (= $(PKG_VERSION)-r$(PKG_RELEASE)), python3-salt (= $(PKG_VERSION)-r$(PKG_RELEASE))
endef

define Package/minion-opkg/description
  OpenWrt opkg provider for Salt package management functions and states.
  Supports managing router packages through the Salt minion.
endef

define Package/minion-uci
  SECTION:=admin
  CATEGORY:=Administration
  TITLE:=Salt minion UCI execution and states
  DEPENDS:=+salt-minion +python3-salt +uci
  EXTRA_DEPENDS:=salt-minion (= $(PKG_VERSION)-r$(PKG_RELEASE)), python3-salt (= $(PKG_VERSION)-r$(PKG_RELEASE))
endef

define Package/minion-uci/description
  Salt execution modules and states for OpenWrt UCI configuration.
  Includes UCI operations and declarative wrt_config states with automatic
  commit support.
endef

define Package/minion-service
  SECTION:=admin
  CATEGORY:=Administration
  TITLE:=Salt minion procd service provider
  DEPENDS:=+salt-minion +python3-salt
  # Runtime tools from Turris; compiling the procd recipe also builds its
  # unrelated uxc/blockd variant and kernel dependencies absent from the SDK.
  EXTRA_DEPENDS:=procd, ubus, salt-minion (= $(PKG_VERSION)-r$(PKG_RELEASE)), python3-salt (= $(PKG_VERSION)-r$(PKG_RELEASE))
endef

define Package/minion-service/description
  OpenWrt service provider for Salt using procd and ubus.
  Supports Salt service management functions and states.
endef

# Integrations covered by the ARM suite and booted procd lifecycle tests.
define Package/minion-openwrt
  SECTION:=admin
  CATEGORY:=Administration
  TITLE:=Salt minion OpenWrt integrations (metapackage)
  DEPENDS:=+salt-minion +minion-opkg +minion-uci +minion-service
  EXTRA_DEPENDS:=salt-minion (= $(PKG_VERSION)-r$(PKG_RELEASE)), minion-opkg (= $(PKG_VERSION)-r$(PKG_RELEASE)), minion-uci (= $(PKG_VERSION)-r$(PKG_RELEASE)), minion-service (= $(PKG_VERSION)-r$(PKG_RELEASE))
endef

define Package/minion-openwrt/description
  Installs the Salt minion and all OpenWrt integrations: opkg package
  management, UCI configuration, and procd service management.
endef

# Patch 030 enables discovery of OpenWrt's adjacent .pyc files.
define Package/python3-salt/install
	$(INSTALL_DIR) $(1)$(PYTHON3_PKG_DIR)
	$(CP) $(PKG_INSTALL_DIR)$(PYTHON3_PKG_DIR)/* $(1)$(PYTHON3_PKG_DIR)/
	$(HOST_PYTHON3_BIN) ./files/prune.py $(1)$(PYTHON3_PKG_DIR)/salt $(SALT_PRUNE_PATHS)
	$(call Python3/CompileAll,$(1))
	mv $(1)$(PYTHON3_PKG_DIR)/salt/client/ssh/ssh_py_shim.py $(1)$(PYTHON3_PKG_DIR)/salt/client/ssh/ssh_py_shim.txt
	$(call Python3/DeleteSourceFiles,$(1))
endef

define Package/minion-opkg/install
	$(INSTALL_DIR) $(1)$(PYTHON3_PKG_DIR)/salt/modules
	$(INSTALL_DATA) ./files/opkg.py $(1)$(PYTHON3_PKG_DIR)/salt/modules/opkg.py
	$(call Python3/CompileAll,$(1))
	$(call Python3/DeleteSourceFiles,$(1))
endef

define Package/minion-openwrt/install
	$(INSTALL_DIR) $(1)
endef

define Package/minion-uci/install
	$(INSTALL_DIR) $(1)$(PYTHON3_PKG_DIR)/salt/modules $(1)$(PYTHON3_PKG_DIR)/salt/states
	$(INSTALL_DATA) ./files/uci.py $(1)$(PYTHON3_PKG_DIR)/salt/modules/uci.py
	$(INSTALL_DATA) ./files/uci_state.py $(1)$(PYTHON3_PKG_DIR)/salt/states/uci.py
	$(INSTALL_DIR) $(1)$(PYTHON3_PKG_DIR)/salt/utils
	$(INSTALL_DATA) ./files/wrt_uci.py $(1)$(PYTHON3_PKG_DIR)/salt/utils/wrt_uci.py
	$(INSTALL_DATA) ./files/wrt_config.py $(1)$(PYTHON3_PKG_DIR)/salt/modules/wrt_config.py
	$(INSTALL_DATA) ./files/wrt_config_state.py $(1)$(PYTHON3_PKG_DIR)/salt/states/wrt_config.py
	$(call Python3/CompileAll,$(1))
	$(call Python3/DeleteSourceFiles,$(1))
endef

define Package/minion-service/install
	$(INSTALL_DIR) $(1)$(PYTHON3_PKG_DIR)/salt/modules $(1)/etc/salt/minion.d
	$(INSTALL_DATA) ./files/openwrt_service.py $(1)$(PYTHON3_PKG_DIR)/salt/modules/openwrt_service.py
	$(INSTALL_DATA) ./files/service-provider.conf $(1)/etc/salt/minion.d/20-openwrt-service.conf
	$(call Python3/CompileAll,$(1))
	$(call Python3/DeleteSourceFiles,$(1))
endef

define Package/salt-minion/conffiles
/etc/salt/minion
/etc/salt/minion.d/
/etc/salt/pki/minion/
endef

define Package/salt-minion/install
	$(INSTALL_DIR) $(1)/usr/bin $(1)/etc/init.d $(1)/etc/salt/minion.d $(1)/etc/salt/pki/minion
	chmod 700 $(1)/etc/salt/pki/minion
	$(INSTALL_BIN) $(PKG_INSTALL_DIR)/usr/bin/salt-minion $(1)/usr/bin/
	$(INSTALL_BIN) $(PKG_INSTALL_DIR)/usr/bin/salt-call $(1)/usr/bin/
	$(call Python3/FixShebang,$(1)/usr/bin/*)
	$(INSTALL_BIN) ./files/salt-minion.init $(1)/etc/init.d/salt-minion
	$(INSTALL_CONF) ./files/minion $(1)/etc/salt/minion
endef

$(eval $(call Py3Package,python3-salt))
$(eval $(call BuildPackage,python3-salt))
$(eval $(call BuildPackage,salt-minion))
$(eval $(call BuildPackage,minion-opkg))
$(eval $(call BuildPackage,minion-uci))
$(eval $(call BuildPackage,minion-service))
$(eval $(call BuildPackage,minion-openwrt))
