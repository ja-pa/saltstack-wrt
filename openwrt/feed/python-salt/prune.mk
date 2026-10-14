# Salt 3008.3 / Turris minion: explicit package-relative removal list.
# No runtime whitelist: custom modules may still be synced from a master.
# Keep shared helpers, all optional minion subsystems, and import exceptions.
# Passed as command-line arguments to prune.py; a sufficiently large list can
# exceed the build host's command-line size limit. Use a manifest if it outgrows it.
SALT_PRUNE_PATHS:=

# Unused cloud drivers and deployment assets (keep shared cloud Python helpers)
SALT_PRUNE_PATHS += \
	cloud/clouds \
	cloud/deploy

# REST API implementations (keep netapi package initializer)
SALT_PRUNE_PATHS += \
	netapi/rest_cherrypy \
	netapi/rest_tornado \
	netapi/rest_wsgi.py

# proxy plugins; imported modules are excluded below
SALT_PRUNE_PATHS += \
	proxy/deltaproxy.py \
	proxy/dummy.py

# runners plugins; imported modules are excluded below
SALT_PRUNE_PATHS += \
	runners/auth.py \
	runners/batch.py \
	runners/cache.py \
	runners/cluster.py \
	runners/config.py \
	runners/doc.py \
	runners/error.py \
	runners/event.py \
	runners/fileserver.py \
	runners/git_pillar.py \
	runners/http.py \
	runners/jobs.py \
	runners/manage.py \
	runners/match.py \
	runners/mine.py \
	runners/net.py \
	runners/network.py \
	runners/pillar.py \
	runners/pki.py \
	runners/queue.py \
	runners/reactor.py \
	runners/resource.py \
	runners/salt.py \
	runners/saltutil.py \
	runners/sdb.py \
	runners/ssh.py \
	runners/survey.py \
	runners/test.py \
	runners/winrepo.py

# wheel plugins; imported modules are excluded below
SALT_PRUNE_PATHS += \
	wheel/config.py \
	wheel/error.py \
	wheel/file_roots.py \
	wheel/key.py \
	wheel/minions.py \
	wheel/pillar_roots.py

# modules: other OS/package managers and excluded integrations
SALT_PRUNE_PATHS += \
	modules/aix_group.py \
	modules/aix_shadow.py \
	modules/aixpkg.py \
	modules/at_solaris.py \
	modules/chocolatey.py \
	modules/cloud.py \
	modules/debconfmod.py \
	modules/debian_ip.py \
	modules/debian_service.py \
	modules/debuild_pkgbuild.py \
	modules/dpkg_lowpkg.py \
	modules/dummyproxy_pkg.py \
	modules/dummyproxy_service.py \
	modules/kernelpkg_linux_apt.py \
	modules/kernelpkg_linux_yum.py \
	modules/linux_lvm.py \
	modules/mac_assistive.py \
	modules/mac_desktop.py \
	modules/mac_group.py \
	modules/mac_keychain.py \
	modules/mac_pkgutil.py \
	modules/mac_portspkg.py \
	modules/mac_power.py \
	modules/mac_service.py \
	modules/mac_shadow.py \
	modules/mac_softwareupdate.py \
	modules/mac_sysctl.py \
	modules/mac_system.py \
	modules/mac_timezone.py \
	modules/mac_user.py \
	modules/mac_xattr.py \
	modules/macdefaults.py \
	modules/macpackage.py \
	modules/mysql.py \
	modules/pacmanpkg.py \
	modules/pkgin.py \
	modules/pkgng.py \
	modules/pkgutil.py \
	modules/postgres.py \
	modules/pw_group.py \
	modules/pw_user.py \
	modules/rbac_solaris.py \
	modules/rdp.py \
	modules/reg.py \
	modules/rest_pkg.py \
	modules/rest_service.py \
	modules/rh_ip.py \
	modules/rh_service.py \
	modules/rpm_lowpkg.py \
	modules/rpmbuild_pkgbuild.py \
	modules/saltcloudmod.py \
	modules/smf_service.py \
	modules/solaris_fmadm.py \
	modules/solaris_group.py \
	modules/solaris_shadow.py \
	modules/solaris_system.py \
	modules/solaris_user.py \
	modules/solarisipspkg.py \
	modules/solarispkg.py \
	modules/systemd_service.py \
	modules/upstart_service.py \
	modules/vsphere.py \
	modules/win_appx.py \
	modules/win_auditpol.py \
	modules/win_autoruns.py \
	modules/win_certutil.py \
	modules/win_dacl.py \
	modules/win_disk.py \
	modules/win_dism.py \
	modules/win_dns_client.py \
	modules/win_dsc.py \
	modules/win_dsc_resource.py \
	modules/win_event.py \
	modules/win_firewall.py \
	modules/win_groupadd.py \
	modules/win_iis.py \
	modules/win_ip.py \
	modules/win_lgpo.py \
	modules/win_lgpo_reg.py \
	modules/win_license.py \
	modules/win_network.py \
	modules/win_ntp.py \
	modules/win_path.py \
	modules/win_pki.py \
	modules/win_powercfg.py \
	modules/win_psget.py \
	modules/win_servermanager.py \
	modules/win_service.py \
	modules/win_shadow.py \
	modules/win_shortcut.py \
	modules/win_smtp_server.py \
	modules/win_snmp.py \
	modules/win_status.py \
	modules/win_system.py \
	modules/win_task.py \
	modules/win_timezone.py \
	modules/win_useradd.py \
	modules/win_wua.py \
	modules/win_wusa.py \
	modules/winrepo.py \
	modules/yumpkg.py \
	modules/zoneadm.py \
	modules/zonecfg.py \
	modules/zypperpkg.py

# states: other OS/package managers and excluded integrations
SALT_PRUNE_PATHS += \
	states/chocolatey.py \
	states/cloud.py \
	states/debconfmod.py \
	states/lvm.py \
	states/mac_assistive.py \
	states/mac_keychain.py \
	states/mac_xattr.py \
	states/macdefaults.py \
	states/macpackage.py \
	states/pkgng.py \
	states/postgres_cluster.py \
	states/postgres_database.py \
	states/postgres_extension.py \
	states/postgres_group.py \
	states/postgres_initdb.py \
	states/postgres_language.py \
	states/postgres_privileges.py \
	states/postgres_schema.py \
	states/postgres_tablespace.py \
	states/postgres_user.py \
	states/reg.py \
	states/win_appx.py \
	states/win_certutil.py \
	states/win_dacl.py \
	states/win_dism.py \
	states/win_dns_client.py \
	states/win_dsc_resource.py \
	states/win_firewall.py \
	states/win_iis.py \
	states/win_lgpo.py \
	states/win_lgpo_reg.py \
	states/win_license.py \
	states/win_network.py \
	states/win_path.py \
	states/win_pki.py \
	states/win_powercfg.py \
	states/win_servermanager.py \
	states/win_shortcut.py \
	states/win_smtp_server.py \
	states/win_snmp.py \
	states/win_system.py \
	states/win_task.py \
	states/win_wua.py \
	states/win_wusa.py \
	states/winrepo.py

# Conservative import exceptions (not removed):
# modules/aptpkg.py <- states/pkgrepo.py
# modules/mac_brew_pkg.py <- utils/rsax931.py
# modules/win_file.py <- utils/win_lgpo_reg.py
# modules/win_pkg.py <- states/pkg.py
# runners/state.py <- modules/state.py
