#!/bin/sh
set -eu
[ "$(id -u)" -eq 0 ] || { echo 'Ejecuta este script con sudo.' >&2; exit 1; }
if [ -f /etc/udev/rules.d/72-logigian64.rules ] && grep -q 'Managed by LogiGian64 Linux' /etc/udev/rules.d/72-logigian64.rules; then
    rm -- /etc/udev/rules.d/72-logigian64.rules
fi
if [ -f /etc/modules-load.d/logigian64-uinput.conf ] && [ "$(cat /etc/modules-load.d/logigian64-uinput.conf)" = uinput ]; then
    rm -- /etc/modules-load.d/logigian64-uinput.conf
fi
udevadm control --reload-rules
udevadm trigger --subsystem-match=input
udevadm trigger --subsystem-match=misc
udevadm trigger --subsystem-match=hidraw
echo 'Reglas retiradas. Desconecta y conecta los perifericos. Los perfiles se conservan.'
