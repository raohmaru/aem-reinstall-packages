# AEM Check Packages

Python command-line utility to detect Adobe Experience Manager (AEM) packages whose latest uploaded version is not installed. Sometimes AEM does not install the newest version of a package after a deployment and keeps an older version installed. This tool lists those packages and, optionally, installs the missing versions.

## Prerequisites

- Python 3.6 or higher

## Installation

1. Clone or download this repository:
   ```bash
   git clone <repository-url>
   cd aem-reinstall-packages
   ```

2. Install required dependencies:
   ```bash
   pip3 install -r requirements.txt
   ```

3. Verify the installation:
   ```bash
   python3 aem-check-packages.py -h
   ```

## Usage

Check a local AEM instance with default credentials and install the missing packages interactively:

```bash
python3 aem-check-packages.py
```

This connects to `localhost:4502` using `admin:admin`, lists every package whose greatest version is not installed, and asks whehter to install a package or skip it.

Only list the packages (no installation):

```bash
python3 aem-check-packages.py --dryrun
```

Check a specific package group:

```bash
python3 aem-check-packages.py  -p com.example.aem
```

Check a packages on a remote instance:

```bash
python3 aem-check-packages.py --host author.example.com:4502 -u myuser:mypassword
```

Example output:

```
com.example.aem/example-base-config: v12.8.0.001 not installed (installed: 12.7.0.012)
com.example.aem/example-ui.apps: v12.8.0.001 not installed (installed: none)

2 of 10 packages from /etc/packages/com.example.aem have a greater version not installed
```

## Command-Line Options

| Option | Description |
|--------|-------------|
| `-h`, `--help` | Show help message and exit |
| `-d`, `--dryrun` | Only list the packages that are not installed, without installing them |
| `--host HOST` | AEM instance host and port (format: `host:port`, default: `localhost:4502`) |
| `-p PATH`, `--path PATH` | Target a specific package subdirectory (e.g., `adobe` searches `/etc/packages/adobe`) |
| `-u USER`, `--user USER` | AEM credentials (format: `username:password`, default: `admin:admin`) |

## How It Works

- Packages are read from the Package Manager (`/crx/packmgr/list.jsp`); package snapshots are ignored.
- Versions of the same package (group and name) are compared numerically, so `1.10.0` is greater than `1.9.0`.
- A package is considered installed when the Package Manager reports that it has been unpacked.
- Installation is done with `/crx/packmgr/service/.json<package path>?cmd=install`.

## Important Notes

⚠️ **Warning**: Without `--dryrun`, this tool **installs** packages on the target instance. Run it with `--dryrun` first if unsure.

⚠️ **Permissions**: Ensure your user account has sufficient permissions to list and install packages in AEM.
