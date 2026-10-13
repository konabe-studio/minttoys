# Installs TuxToys the way the Debian package lays it out; debian/rules runs it with
# DESTDIR. The Python package goes to a directory of its own rather than dist-packages, as
# Debian's Python policy asks of an application, and the launchers point there.
#
# Building compiles the translations in po/ into build/: the gettext catalogues, and the
# desktop entries with their translated names. A checkout uses build/locale too, so
# `make mo` is enough to see TuxToys in another language before installing it.

PREFIX ?= /usr
LIBDIR = $(PREFIX)/lib/tuxtoys
LIBEXECDIR = $(PREFIX)/libexec/tuxtoys
DATADIR = $(PREFIX)/share
SYSCONFDIR ?= /etc

SUBSTITUTE = sed -e 's|@LIBDIR@|$(LIBDIR)|g' -e 's|@LIBEXECDIR@|$(LIBEXECDIR)|g'

LINGUAS = $(shell cat po/LINGUAS)
POT ?= po/tuxtoys.pot
MO = $(LINGUAS:%=build/locale/%/LC_MESSAGES/tuxtoys.mo)
DESKTOP = $(patsubst data/%.desktop.in,build/%.desktop,$(wildcard data/*/*.desktop.in))
POLICY = build/polkit/io.github.konabe_studio.TuxToys.hosts.policy

all: mo $(DESKTOP) $(POLICY)

mo: $(MO)

build/locale/%/LC_MESSAGES/tuxtoys.mo: po/%.po
	install -d $(@D)
	msgfmt --check --check-format -o $@ $<

build/%.desktop: data/%.desktop.in po/LINGUAS $(LINGUAS:%=po/%.po)
	install -d $(@D)
	msgfmt --desktop --template=$< -d po -o $@

# The polkit action Hosts File Editor saves through, its texts from the catalogues.
$(POLICY): tuxtoys/modules/hosts/policy.py $(MO)
	install -d $(@D)
	python3 -m tuxtoys.modules.hosts.policy build/locale $(LIBEXECDIR)/tuxtoys-hosts-save > $@

# For maintainers: the template from the sources, then every translation merged with it.
pot:
	xgettext --language=Python --from-code=UTF-8 --add-comments=TRANSLATORS: --keyword=N_ \
		--add-location=file --package-name=tuxtoys \
		--msgid-bugs-address=https://github.com/konabe-studio/tuxtoys/issues \
		-o $(POT) $$(find tuxtoys -name '*.py' | LC_ALL=C sort)
	xgettext --language=Desktop --join-existing --add-location=file \
		-o $(POT) data/*/*.desktop.in

update-po: pot
	for lang in $(LINGUAS); do \
		msgmerge --update --backup=none --previous po/$$lang.po $(POT); \
	done

check:
	PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider

install: all
	find tuxtoys -name '*.py' -exec install -D -m 644 {} $(DESTDIR)$(LIBDIR)/{} \;
	install -d $(DESTDIR)$(PREFIX)/bin $(DESTDIR)$(LIBEXECDIR)
	$(SUBSTITUTE) data/launchers/tuxtoys.in > $(DESTDIR)$(PREFIX)/bin/tuxtoys
	$(SUBSTITUTE) data/launchers/tuxtoys-settings.in > $(DESTDIR)$(PREFIX)/bin/tuxtoys-settings
	$(SUBSTITUTE) data/launchers/tuxtoysd.in > $(DESTDIR)$(LIBEXECDIR)/tuxtoysd
	$(SUBSTITUTE) data/launchers/tuxtoys-tray.in > $(DESTDIR)$(LIBEXECDIR)/tuxtoys-tray
	$(SUBSTITUTE) data/launchers/tuxtoys-locksmith.in > $(DESTDIR)$(LIBEXECDIR)/tuxtoys-locksmith
	$(SUBSTITUTE) data/launchers/tuxtoys-save-template.in \
		> $(DESTDIR)$(LIBEXECDIR)/tuxtoys-save-template
	$(SUBSTITUTE) data/launchers/tuxtoys-always-on-top.in \
		> $(DESTDIR)$(LIBEXECDIR)/tuxtoys-always-on-top
	$(SUBSTITUTE) data/launchers/tuxtoys-new-from-template.in \
		> $(DESTDIR)$(LIBEXECDIR)/tuxtoys-new-from-template
	$(SUBSTITUTE) data/launchers/tuxtoys-image-resizer.in \
		> $(DESTDIR)$(LIBEXECDIR)/tuxtoys-image-resizer
	$(SUBSTITUTE) data/launchers/tuxtoys-rename.in \
		> $(DESTDIR)$(LIBEXECDIR)/tuxtoys-rename
	$(SUBSTITUTE) data/launchers/tuxtoys-hosts-save.in \
		> $(DESTDIR)$(LIBEXECDIR)/tuxtoys-hosts-save
	$(SUBSTITUTE) data/launchers/tuxtoys-hosts-editor.in \
		> $(DESTDIR)$(LIBEXECDIR)/tuxtoys-hosts-editor
	chmod 755 $(DESTDIR)$(PREFIX)/bin/tuxtoys $(DESTDIR)$(PREFIX)/bin/tuxtoys-settings \
		$(DESTDIR)$(LIBEXECDIR)/tuxtoysd $(DESTDIR)$(LIBEXECDIR)/tuxtoys-tray \
		$(DESTDIR)$(LIBEXECDIR)/tuxtoys-locksmith $(DESTDIR)$(LIBEXECDIR)/tuxtoys-save-template \
		$(DESTDIR)$(LIBEXECDIR)/tuxtoys-always-on-top \
		$(DESTDIR)$(LIBEXECDIR)/tuxtoys-new-from-template \
		$(DESTDIR)$(LIBEXECDIR)/tuxtoys-image-resizer \
		$(DESTDIR)$(LIBEXECDIR)/tuxtoys-rename \
		$(DESTDIR)$(LIBEXECDIR)/tuxtoys-hosts-save \
		$(DESTDIR)$(LIBEXECDIR)/tuxtoys-hosts-editor
	install -d $(DESTDIR)$(SYSCONFDIR)/xdg/autostart $(DESTDIR)$(DATADIR)/dbus-1/services
	for entry in build/autostart/*.desktop; do \
		$(SUBSTITUTE) $$entry > $(DESTDIR)$(SYSCONFDIR)/xdg/autostart/$$(basename $$entry); \
	done
	$(SUBSTITUTE) data/dbus/io.github.konabe_studio.TuxToys.service.in \
		> $(DESTDIR)$(DATADIR)/dbus-1/services/io.github.konabe_studio.TuxToys.service
	install -d $(DESTDIR)$(DATADIR)/applications
	$(SUBSTITUTE) build/applications/io.github.konabe_studio.TuxToys.desktop \
		> $(DESTDIR)$(DATADIR)/applications/io.github.konabe_studio.TuxToys.desktop
	for lang in $(LINGUAS); do \
		install -D -m 644 build/locale/$$lang/LC_MESSAGES/tuxtoys.mo \
			$(DESTDIR)$(DATADIR)/locale/$$lang/LC_MESSAGES/tuxtoys.mo; \
	done
	cd data && find icons -name '*.svg' -exec install -D -m 644 {} $(DESTDIR)$(DATADIR)/{} \;
	install -D -m 644 -t $(DESTDIR)$(DATADIR)/man/man1 data/man/*.1
	install -D -m 644 -t $(DESTDIR)$(DATADIR)/polkit-1/actions $(POLICY)

clean:
	rm -rf build

.PHONY: all mo pot update-po check install clean
