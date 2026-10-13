#!/usr/bin/env python3
"""
Checks whether an AEM instance has the latest uploaded version of each package installed and, optionally, installs the missing versions.
"""
import argparse
import os
import re
import select
import sys
import termios
import tty
import requests

DEFAULT_HOST = 'localhost:4502'
DEFAULT_USER = 'admin:admin'
PACKAGES_ROOT = '/etc/packages'

def read_arguments():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='examples:\n'
               '  %(prog)s --dryrun\n'
               '  %(prog)s --host author.example.com:4502 -u user:pass -p com.example.aem')
    parser.add_argument('--host', default=DEFAULT_HOST,
                        help='AEM host in the format host:port (default: %(default)s)')
    parser.add_argument('-u', '--user', default=DEFAULT_USER,
                        help='Credentials in the format user:pass (default: %(default)s)')
    parser.add_argument('-p', '--path',
                        help='A package sub-path (eg: "adobe" will search for packages under /etc/packages/adobe)')
    parser.add_argument('-d', '--dryrun', action='store_true',
                        help='Only list the packages that are not installed, without installing them')
    args = parser.parse_args()
    if ':' not in args.user:
        parser.error('--user must be in the format user:pass')
    if not re.fullmatch(r'[\w.-]+(:\d+)?', args.host):
        parser.error('--host must be in the format host:port')
    return args


def get_packages(host, credentials):
    """
    Queries the Package Manager for all the packages.
    """
    url = 'http://{0}/crx/packmgr/list.jsp'.format(host)
    try:
        response = requests.get(url, auth=credentials, timeout=60)
    except requests.RequestException as e:
        sys.exit('Could not reach AEM: {0}'.format(e))
    if response.status_code != 200:
        sys.exit('Failed to list packages: HTTP {0}'.format(response.status_code))
    try:
        return response.json()['results']
    except (ValueError, KeyError):
        sys.exit('Unexpected response from AEM (wrong credentials?)')


def filter_by_path(packages, path):
    if not path:
        return packages
    prefix = '{0}/{1}'.format(PACKAGES_ROOT, path.strip('/'))
    return [p for p in packages if p.get('path', '').startswith(prefix + '/')]


def version_key(version):
    """
    Sorts numeric parts numerically; a version with a qualifier (e.g. 1.0-SNAPSHOT) is lower than its release.
    """
    release, _, qualifier = (version or '').partition('-')
    numbers = tuple(int(n) for n in re.findall(r'\d+', release))
    return numbers, qualifier == '', qualifier


def is_installed(package):
    return bool(package.get('lastUnpacked'))


def find_outdated(packages):
    """
    Returns (group, name, greatest version, installed versions, path) for each package whose greatest version is not installed.
    """
    by_package = {}
    for package in packages:
        if '.snapshot' in package.get('path', ''):
            continue
        by_package.setdefault((package.get('group', ''), package['name']), []).append(package)

    result = []
    for (group, name), versions in sorted(by_package.items()):
        greatest = max(versions, key=lambda p: version_key(p.get('version')))
        if not is_installed(greatest):
            installed = sorted((p.get('version') for p in versions if is_installed(p)), key=version_key)
            result.append((group, name, greatest.get('version'), installed, greatest['path']))
    return result


def install_package(host, credentials, path):
    """
    Installs the package stored at the given repository path.
    """
    url = 'http://{0}/crx/packmgr/service/.json{1}?cmd=install'.format(host, path)
    try:
        response = requests.post(url, auth=credentials, timeout=600)
        data = response.json()
    except (requests.RequestException, ValueError) as e:
        print('\033[91mFailed\033[0m: {0}'.format(e))
        return
    if response.status_code == 200 and data.get('success'):
        print('\033[92mDone\033[0m')
    else:
        print('\033[91mFailed\033[0m: {0}'.format(data.get('msg', 'HTTP {0}'.format(response.status_code))))


def ask(prompt, valid):
    """
    Waits for a single keypress among `valid` and returns it, or None if Escape is pressed.
    """
    sys.stdout.write(prompt)
    sys.stdout.flush()
    if not sys.stdin.isatty():
        while True:
            key = (sys.stdin.readline()[:1] or '\x1b').lower()
            if key in valid or key == '\x1b':
                return None if key == '\x1b' else key
    fd = sys.stdin.fileno()
    previous = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        while True:
            key = os.read(fd, 1).decode(errors='ignore').lower()
            if key == '\x03':
                raise KeyboardInterrupt
            if key == '\x1b':
                # Drain the rest of an escape sequence (arrow keys, etc.); a lone Escape has nothing following
                if select.select([fd], [], [], 0.05)[0]:
                    os.read(fd, 8)
                    continue
                return None
            if key in valid:
                sys.stdout.write(key + '\n')
                return key
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, previous)


def main():
    args = read_arguments()
    credentials = tuple(args.user.split(':', 1))

    packages = filter_by_path(get_packages(args.host, credentials), args.path)
    outdated = find_outdated(packages)

    for group, name, greatest, installed, _ in outdated:
        print('{0}/{1}{2}{3}: v{4} not installed (installed: {5})'.format(
            group, color.BOLD, name, color.END, greatest, ', '.join(installed) if installed else 'none'))
    print('\n{0} of {1} packages from {2} have a greater version not installed'.format(
        len(outdated), len({(p.get('group'), p['name']) for p in packages}),
        PACKAGES_ROOT + ('/' + args.path.strip('/') if args.path else '')), file=sys.stderr)

    if outdated and not args.dryrun:
        install_all = False
        for group, name, greatest, _, path in outdated:
            if not install_all:
                answer = ask('\n{0}/{1}{2}{3} v{4}\nInstall the package? (y/n/a/esc): '.format(
                    group, color.BOLD, name, color.END, greatest), 'yna')
                if answer is None:
                    print('Exiting')
                    sys.exit(0)
                if answer == 'a':
                    install_all = True
                elif answer == 'n':
                    print('\033[93mSkipping ' + path + '\033[0m')
                    continue
            print('Installing ' + path)
            install_package(args.host, credentials, path)
    sys.exit(1 if outdated and args.dryrun else 0)


if __name__ == '__main__':
    main()
