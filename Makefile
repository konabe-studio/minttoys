# Installs MintToys the way the Debian package lays it out; debian/rules runs it with
# DESTDIR. The Python package goes to a directory of its own rather than dist-packages, as
# Debian's Python policy asks of an application, and the launchers point there.
#
# Building compiles the translations in po/ into build/: the gettext catalogues, and the
# desktop entries with their translated names. A checkout uses build/locale too, so
# `make mo` is enough to see MintToys in another language before installing it.

PREFIX ?= /usr
LIBDIR = $(PREFIX)/lib/minttoys
LIBEXECDIR = $(PREFIX)/libexec/minttoys
DATADIR = $(PREFIX)/share
SYSCONFDIR ?= /etc

SUBSTITUTE = sed -e 's|@LIBDIR@|$(LIBDIR)|g' -e 's|@LIBEXECDIR@|$(LIBEXECDIR)|g'

LINGUAS = $(shell cat po/LINGUAS)
POT ?= po/minttoys.pot
MO = $(LINGUAS:%=build/locale/%/LC_MESSAGES/minttoys.mo)
DESKTOP = $(patsubst data/%.desktop.in,build/%.desktop,$(wildcard data/*/*.desktop.in))

all: mo $(DESKTOP)

mo: $(MO)

build/locale/%/LC_MESSAGES/minttoys.mo: po/%.po
	install -d $(@D)
	msgfmt --check --check-format -o $@ $<

build/%.desktop: data/%.desktop.in po/LINGUAS $(LINGUAS:%=po/%.po)
	install -d $(@D)
	msgfmt --desktop --template=$< -d po -o $@

# For maintainers: the template from the sources, then every translation merged with it.
pot:
	xgettext --language=Python --from-code=UTF-8 --add-comments=TRANSLATORS: \
		--add-location=file --package-name=minttoys \
		--msgid-bugs-address=https://github.com/konabe-studio/minttoys/issues \
		-o $(POT) $$(find minttoys -name '*.py' | LC_ALL=C sort)
	xgettext --language=Desktop --join-existing --add-location=file \
		-o $(POT) data/*/*.desktop.in

update-po: pot
	for lang in $(LINGUAS); do \
		msgmerge --update --backup=none --previous po/$$lang.po $(POT); \
	done

check:
	PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider

install: all
	find minttoys -name '*.py' -exec install -D -m 644 {} $(DESTDIR)$(LIBDIR)/{} \;
	install -d $(DESTDIR)$(PREFIX)/bin $(DESTDIR)$(LIBEXECDIR)
	$(SUBSTITUTE) data/launchers/minttoys.in > $(DESTDIR)$(PREFIX)/bin/minttoys
	$(SUBSTITUTE) data/launchers/minttoys-settings.in > $(DESTDIR)$(PREFIX)/bin/minttoys-settings
	$(SUBSTITUTE) data/launchers/minttoysd.in > $(DESTDIR)$(LIBEXECDIR)/minttoysd
	$(SUBSTITUTE) data/launchers/minttoys-tray.in > $(DESTDIR)$(LIBEXECDIR)/minttoys-tray
	chmod 755 $(DESTDIR)$(PREFIX)/bin/minttoys $(DESTDIR)$(PREFIX)/bin/minttoys-settings \
		$(DESTDIR)$(LIBEXECDIR)/minttoysd $(DESTDIR)$(LIBEXECDIR)/minttoys-tray
	install -d $(DESTDIR)$(SYSCONFDIR)/xdg/autostart $(DESTDIR)$(DATADIR)/dbus-1/services
	for entry in build/autostart/*.desktop; do \
		$(SUBSTITUTE) $$entry > $(DESTDIR)$(SYSCONFDIR)/xdg/autostart/$$(basename $$entry); \
	done
	$(SUBSTITUTE) data/dbus/io.github.konabe_studio.MintToys.service.in \
		> $(DESTDIR)$(DATADIR)/dbus-1/services/io.github.konabe_studio.MintToys.service
	install -d $(DESTDIR)$(DATADIR)/applications
	$(SUBSTITUTE) build/applications/io.github.konabe_studio.MintToys.desktop \
		> $(DESTDIR)$(DATADIR)/applications/io.github.konabe_studio.MintToys.desktop
	for lang in $(LINGUAS); do \
		install -D -m 644 build/locale/$$lang/LC_MESSAGES/minttoys.mo \
			$(DESTDIR)$(DATADIR)/locale/$$lang/LC_MESSAGES/minttoys.mo; \
	done
	cd data && find icons -name '*.svg' -exec install -D -m 644 {} $(DESTDIR)$(DATADIR)/{} \;
	install -D -m 644 -t $(DESTDIR)$(DATADIR)/man/man1 data/man/*.1

clean:
	rm -rf build

.PHONY: all mo pot update-po check install clean
