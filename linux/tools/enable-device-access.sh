#!/bin/sh
set -eu
if [ "$(id -u)" -ne 0 ]; then
    echo 'Ejecuta: sudo bash /opt/logigian64-linux/tools/enable-device-access.sh "$USER"' >&2
    exit 1
fi
account=${1:-${SUDO_USER:-}}
if [ -z "$account" ] || [ "$account" = root ] || ! id "$account" >/dev/null 2>&1; then
    echo 'Indica el usuario normal que ejecutara LogiGian64.' >&2
    exit 1
fi
getent group logigian64 >/dev/null || groupadd --system logigian64
usermod -a -G logigian64 "$account"
install -d /etc/udev/rules.d /etc/modules-load.d
cat > /etc/udev/rules.d/72-logigian64.rules <<'RULES'
# Managed by LogiGian64 Linux. Read physical inputs; write only uinput and G502 HID++.
SUBSYSTEM=="input", KERNEL=="event*", ENV{ID_INPUT_KEYBOARD}=="1", GROUP="logigian64", MODE="0640"
SUBSYSTEM=="input", KERNEL=="event*", ENV{ID_INPUT_MOUSE}=="1", GROUP="logigian64", MODE="0640"
SUBSYSTEM=="misc", KERNEL=="uinput", GROUP="logigian64", MODE="0660", OPTIONS+="static_node=uinput"
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="046d", ATTRS{idProduct}=="c08b", GROUP="logigian64", MODE="0660"
RULES
printf 'uinput\n' > /etc/modules-load.d/logigian64-uinput.conf
modprobe uinput
udevadm control --reload-rules
udevadm trigger --subsystem-match=input
udevadm trigger --subsystem-match=misc
udevadm trigger --subsystem-match=hidraw
echo 'Permisos instalados. Cierra la sesion y vuelve a entrar. Ejecuta la interfaz como usuario normal.'
