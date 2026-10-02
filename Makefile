# Installs MintToys the way the Debian package lays it out; debian/rules runs it with
# DESTDIR. The Python package goes to a directory of its own rather than dist-packages, as
# Debian's Python policy asks of an application, and the launchers point there.

PREFIX ?= /usr
LIBDIR = $(PREFIX)/lib/minttoys
LIBEXECDIR = $(PREFIX)/libexec/minttoys
DATADIR = $(PREFIX)/share
SYSCONFDIR ?= /etc

SUBSTITUTE = sed -e 's|@LIBDIR@|$(LIBDIR)|g' -e 's|@LIBEXECDIR@|$(LIBEXECDIR)|g'

all:

check:
	PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider

install:
	find minttoys -name '*.py' -exec install -D -m 644 {} $(DESTDIR)$(LIBDIR)/{} \;
	install -d $(DESTDIR)$(PREFIX)/bin $(DESTDIR)$(LIBEXECDIR)
	$(SUBSTITUTE) data/launchers/minttoys.in > $(DESTDIR)$(PREFIX)/bin/minttoys
	$(SUBSTITUTE) data/launchers/minttoys-settings.in > $(DESTDIR)$(PREFIX)/bin/minttoys-settings
	$(SUBSTITUTE) data/launchers/minttoysd.in > $(DESTDIR)$(LIBEXECDIR)/minttoysd
	$(SUBSTITUTE) data/launchers/minttoys-tray.in > $(DESTDIR)$(LIBEXECDIR)/minttoys-tray
	chmod 755 $(DESTDIR)$(PREFIX)/bin/minttoys $(DESTDIR)$(PREFIX)/bin/minttoys-settings \
		$(DESTDIR)$(LIBEXECDIR)/minttoysd $(DESTDIR)$(LIBEXECDIR)/minttoys-tray
	install -d $(DESTDIR)$(SYSCONFDIR)/xdg/autostart $(DESTDIR)$(DATADIR)/dbus-1/services
	for entry in data/autostart/*.desktop.in; do \
		$(SUBSTITUTE) $$entry > $(DESTDIR)$(SYSCONFDIR)/xdg/autostart/$$(basename $$entry .in); \
	done
	$(SUBSTITUTE) data/dbus/io.github.konabe_studio.MintToys.service.in \
		> $(DESTDIR)$(DATADIR)/dbus-1/services/io.github.konabe_studio.MintToys.service
	install -d $(DESTDIR)$(DATADIR)/applications
	$(SUBSTITUTE) data/applications/io.github.konabe_studio.MintToys.desktop.in \
		> $(DESTDIR)$(DATADIR)/applications/io.github.konabe_studio.MintToys.desktop
	cd data && find icons -name '*.svg' -exec install -D -m 644 {} $(DESTDIR)$(DATADIR)/{} \;
	install -D -m 644 -t $(DESTDIR)$(DATADIR)/man/man1 data/man/*.1

.PHONY: all check install
