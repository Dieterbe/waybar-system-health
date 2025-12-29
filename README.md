# waybar-system-health

Script for waybar to detect problems with your Linux system.

* If all is well, takes up only a single character: `✓`.
* If there are problems, tells you concisely, with all the details in the tooltip.

- If you found yourself previously using waybar modules like `systemd-failed-units` or `disk` and thinking "why do these need to take up space in my waybar when everything is fine?", then maybe this is for you.
- If you wish you had more linux system monitoring modules in waybar, then maybe this is for you.

## Currently supported
- Disk: configurable mountpoint capacity thresholds
- Btrfs: device stats and scrub errors
- systemd: overall status and unit failures
- journal: errors
- SMART: device health summaries via `smartctl --scan-open` and `smartctl -a`

## More things to add in the future
- old pacnew/pacsave files
- outdated system

## Screenshots
### If status is OK

![screenshot if status is OK](screenshot-ok.png)

### If status is Critical

![screenshot if status is critical](screenshot-critical.png)

## Configuration

(if you don't know what `$XDG_CONFIG_HOME` is, it's usually `~/.config`)

### Global pattern ignores

You can include per-module ignore rules in a file at `$XDG_CONFIG_HOME/waybar-system-health/ignore`.
e.g. something like this:
```
# Ignore noisy firmware/ACPI messages (common on many laptops)
journal:ACPI (Error|BIOS Error)
journal:ucsi_acpi .* (unknown error|UCSI_GET_PDOS failed)
# Ignore basically empty line
journal:kernel: 

# Intel VMD (00:0e.0) sometimes triggers a harmless AHCI probe failure; VMD driver is used.
journal:\bahci\s+0000:00:0e\.0:\s+probe with driver ahci failed with error -12\b

# Ignore an NVMe namespace that's intentionally missing SMART support
smart:/dev/nvme1n1
```

### Smart module

The SMART module requires `smartctl` from the `smartmontools` package. 
You also need elevated privileges.  To my knowledge the best (secure, simple and working across many device types) method to do this, is to hardcode
just the needed commands in your sudo config.
To do this, run `sudo visudo -f /etc/sudoers.d/smartctl` and paste this:
```
# Allow scanning disks
Cmnd_Alias SMART_SCAN = /usr/sbin/smartctl --scan-open

# Allow read-only dumps for common device nodes
Cmnd_Alias SMART_READ = \
  /usr/sbin/smartctl -a /dev/sd[a-z], \
  /usr/sbin/smartctl -a /dev/nvme[0-9], \
  /usr/sbin/smartctl -a /dev/nvme[0-9]n[0-9]

# Replace "dieter" with your user, or use a group like %wheel
dieter ALL=(root) NOPASSWD:NOEXEC: SMART_SCAN, SMART_READ
```
If you get messages in your journal like "conversation failed" and "auth could not identify password for..." then your sudo rules don't match the exact commands needed.

## Disk configuration

Mountpoints and thresholds are configured via a JSON file at `$XDG_CONFIG_HOME/waybar-system-health/disk.json`
(overridable with `WAYBAR_SYSTEM_HEALTH_DISK`). The file contains a list of objects:
```
[
  {
    "path": "/",
    "warn": 80,
    "critical": 90
  },
  {
    "path": "/home",
    "warn": 85,
    "critical": 95
  }
]
```
Values are percentages of used space; `warn` cannot exceed `critical`. When the config is missing an entry, the Disk module will emit a warning reminding you to configure it.

## Waybar configuration
Something like...
```
  "custom/system-health": {
  "exec": "~/code/waybar-system-health/waybar-system-health.py",
  "return-type": "json",
  "interval": 30,
  "format": "{}",
  "tooltip": true
},
```
And the css:
```
#custom-system-health.critical {
    color: red;
    font-weight: bolder;
}
#custom-system-health.ok {
    color: green;
}
#custom-system-health.warning {
    color: yellow;
    font-weight: bolder;
}
```
