Name:           winebox
Version:        0.1.0
Release:        1%{?dist}
Summary:        Sandboxed Wine orchestrator for Linux using Bubblewrap
License:        MIT
BuildArch:      noarch
Source0:        %{name}-%{version}-linux-noarch.tar.gz

Requires:       python3 >= 3.11
Requires:       bubblewrap
Requires:       python3-typer
Requires:       python3-rich
Requires:       python3-tomli-w
Requires:       python3-platformdirs
Requires:       python3-gobject
Requires:       gtk4
Requires:       libadwaita
Recommends:     wine

%description
WineBox isolates Windows applications and games in per-prefix Bubblewrap
sandboxes with configurable hardware permissions, runner management, and a
GTK4 + Libadwaita desktop GUI.

%prep
%autosetup -n %{name}-%{version}

%install
mkdir -p %{buildroot}%{python3_sitelib}
cp -a src/winebox %{buildroot}%{python3_sitelib}/
find %{buildroot}%{python3_sitelib}/winebox -name "__pycache__" -type d -exec rm -rf {} +

mkdir -p %{buildroot}%{_bindir}
cat > %{buildroot}%{_bindir}/winebox <<'EOF'
#!/usr/bin/python3
from winebox.interface.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
EOF
chmod 0755 %{buildroot}%{_bindir}/winebox

install -Dm644 packaging/linux/id.winebox.WineBox.desktop \
  %{buildroot}%{_datadir}/applications/id.winebox.WineBox.desktop
install -Dm644 packaging/linux/id.winebox.WineBox.svg \
  %{buildroot}%{_datadir}/icons/hicolor/scalable/apps/id.winebox.WineBox.svg

%files
%{_bindir}/winebox
%{python3_sitelib}/winebox
%{_datadir}/applications/id.winebox.WineBox.desktop
%{_datadir}/icons/hicolor/scalable/apps/id.winebox.WineBox.svg
