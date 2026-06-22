Name:           alienware-m15-rgb
Version:        0.1.0
Release:        1%{?dist}
Summary:        Native Linux per-key RGB control for the Alienware m15 R2 keyboard

License:        GPL-3.0-or-later
URL:            https://github.com/Louisreed/alienware-m15-rgb
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz#/%{name}-%{version}.tar.gz

BuildArch:      noarch
BuildRequires:  python3-devel
BuildRequires:  python3-setuptools
BuildRequires:  python3-pip
Requires:       python3
Recommends:     ImageMagick

%description
Controls the Alienware m15 R2 per-key RGB keyboard (Darfon 0d62:0a1c) directly
over hidraw, using the reverse-engineered AlienFX API_V5 protocol. Supports
solid colours, palettes, wallpaper matching, firmware effects and brightness,
with an optional GNOME top-bar menu.

%prep
%autosetup

%build
%py3_build

%install
%py3_install
install -Dm0644 udev/99-alienware-m15-rgb.rules \
  %{buildroot}%{_udevrulesdir}/99-alienware-m15-rgb.rules

%files
%license LICENSE
%doc README.md docs/PROTOCOL.md
%{python3_sitelib}/alienware_m15_rgb/
%{python3_sitelib}/alienware_m15_rgb-*.egg-info/
%{_bindir}/alienware-m15-rgb
%{_udevrulesdir}/99-alienware-m15-rgb.rules

%changelog
* Mon Jun 22 2026 Louis Reed - 0.1.0-1
- Initial package.
