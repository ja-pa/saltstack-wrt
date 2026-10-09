# Host-only replacement for the SDK's full LLVM/Rust bootstrap.
# Official Rust 1.90.0 binaries, pinned for this x86_64 -> ARMv7 musl SDK.
include $(TOPDIR)/rules.mk
PKG_NAME:=rust
PKG_VERSION:=1.90.0
PKG_RELEASE:=3
PKG_HOST_ONLY:=1
PKG_LICENSE:=Apache-2.0 MIT
PKG_SOURCE:=rustc-$(PKG_VERSION)-x86_64-unknown-linux-gnu.tar.xz
PKG_SOURCE_URL:=https://static.rust-lang.org/dist
PKG_HASH:=48c2a42de9e92fcae8c24568f5fe40d5734696a6f80e83cc6d46eef1a78f13c9
HOST_BUILD_DIR:=$(BUILD_DIR_HOST)/rustc-$(PKG_VERSION)-x86_64-unknown-linux-gnu
include $(INCLUDE_DIR)/host-build.mk
include $(INCLUDE_DIR)/package.mk

define Download/cargo
  FILE:=cargo-$(PKG_VERSION)-x86_64-unknown-linux-gnu.tar.xz
  URL:=https://static.rust-lang.org/dist
  HASH:=9853db03d68578a30972e2755c89c66aec035fec641cf8f3a7117c81eec2578d
endef
define Download/std-host
  FILE:=rust-std-$(PKG_VERSION)-x86_64-unknown-linux-gnu.tar.xz
  URL:=https://static.rust-lang.org/dist
  HASH:=663f4ab7945b392d5e5294dec1b050a66820a20e86f084ec37eeb0f2f7ff5569
endef
define Download/std-arm
  FILE:=rust-std-$(PKG_VERSION)-armv7-unknown-linux-musleabihf.tar.xz
  URL:=https://static.rust-lang.org/dist
  HASH:=072027aa8ce4ce6d053c73abc3a8bb603149533e4109dce72b36c9f0fd63d00a
endef
$(eval $(call Download,cargo))
$(eval $(call Download,std-host))
$(eval $(call Download,std-arm))

define Package/rust
  SECTION:=lang
  CATEGORY:=Languages
  SUBMENU:=Rust
  TITLE:=Pinned official Rust host compiler for Omnia SDK
  BUILDONLY:=1
endef
Host/Configure:=:
Host/Compile:=:
define Host/Install
	cd $(HOST_BUILD_DIR) && ./install.sh --prefix=$(STAGING_DIR)/host --disable-ldconfig
	for archive in cargo-$(PKG_VERSION)-x86_64-unknown-linux-gnu rust-std-$(PKG_VERSION)-x86_64-unknown-linux-gnu rust-std-$(PKG_VERSION)-armv7-unknown-linux-musleabihf; do \
		tar -xJf $(DL_DIR)/$$$$archive.tar.xz -C $(HOST_BUILD_DIR); \
		(cd $(HOST_BUILD_DIR)/$$$$archive && ./install.sh --prefix=$(STAGING_DIR)/host --disable-ldconfig) || exit 1; \
	done
endef
$(eval $(call HostBuild))
$(eval $(call BuildPackage,rust))
