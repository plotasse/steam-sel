#!/usr/bin/python3
import os
import re
from xdg.BaseDirectory import xdg_data_home
from steamfiles import acf
import appinfo2 as appinfo

#
# CONFIGURATION
#

# Your main Steam installation.
main_library = xdg_data_home + "/Steam"

# Your OS, according to Steam.
# Should be either linux, macos or windows.
# This script probably only works on linux anyway.
current_os = "linux"

# Your architecture, according to Steam.
# Should be either 32 or 64.
# AFAIK Steam is not even supported on i686 anymore, but whatever.
current_osarch = 64

# This is where we can find some info on compatibility tools.
# Change only if you know what you're doing. I don't.
steamplay_manifests_appid = 891390

#
# END CONFIGURATION
#

libraries = [main_library]

# Try and find other library folders.
# I think they are also available in main_library/config/config.vdf.
try:
    with open(main_library + "/steamapps/libraryfolders.vdf") as f:
        d = acf.load(f)
        for k, v in d["LibraryFolders"].items():
            if k.isdigit():
                libraries.append(v)
except FileNotFoundError:
    print("libraryfolders.vdf not found")

print(libraries)

apps = {}

# This is horrendous, but Steam apparently behaves this way,
# so I guess we will have to do the same. I'm deeply sorry.
def escape_path(path):
    return "'" + path.replace("'","'\\''") + "'"

class CompatTool:
    def __init__(self, app):
        self.app = app

        with open(app.installdir + "/toolmanifest.vdf") as toolmanifest_file:
            toolmanifest = acf.load(toolmanifest_file)["manifest"]

        self.commandline = toolmanifest["commandline"]
        try:
            self.require_tool_appid = int(toolmanifest["require_tool_appid"])
        except KeyError:
            self.require_tool_appid = None

    def get_command(self, verb, cmd):
        cmd = escape_path(self.app.installdir) + self.commandline.replace("%verb%", verb) + " " + cmd
        if self.require_tool_appid:
            cmd = apps[self.require_tool_appid].compat_tool.get_command(verb, cmd)
        return cmd

class App:
    def __init__(self, steamapps, appid):
        self.appid = appid

        with open(steamapps + "/appmanifest_" + str(self.appid) + ".acf") as appmanifest_file:
            self.appstate = acf.load(appmanifest_file)["AppState"]

        self.name = self.appstate["name"]
        self.installdir = steamapps + "/common/" + self.appstate["installdir"]

        try:
            self.compat_tool = CompatTool(self)
        except FileNotFoundError:
            self.compat_tool = None

    def __repr__(self):
        return "<App, appid=" + str(self.appid) + ", name=" + self.name + ", installdir=" + self.installdir + ">"

manifest_re = re.compile("^appmanifest_([0-9]+)\\.acf$")
for l in libraries:
    steamapps = l + "/steamapps"
    for e in os.listdir(steamapps):
        m = manifest_re.match(e)
        if m:
            appid = int(m.group(1))
            apps[appid] = App(steamapps, appid)

# Load the apps we need from appinfo.vdf
apps_to_load = {steamplay_manifests_appid}

# TODO use the requested app
apps_to_load = apps_to_load.union({211820,1566410, 1145360, 70300, 400})

for appid, app in apps.items():
    if app.compat_tool:
        print("Found compatibility tool:", app)
        # TODO only load the compatibility tool associated with the requested app
        apps_to_load.add(appid)

with open(main_library + "/appcache/appinfo.vdf", "rb") as appinfo_file:
    appinfo_data = appinfo.load(appinfo_file, apps=apps_to_load)

# Load the main Steam config file. It contains the game <-> compatibility tool mappings.
with open(main_library + "/config/config.vdf", "r") as config_file:
    config_data = acf.load(config_file)

def parse_oslist(oslist):
    return set(oslist.split(",")) if oslist else set()

def get_compat_tool_name(appid):
    try:
        return config_data['InstallConfigStore']['Software']['Valve']['Steam']['CompatToolMapping'][str(appid)]['name'] or None
    except KeyError:
        return None

def get_compat_tool_appinfo(name):
    return appinfo_data[steamplay_manifests_appid]["sections"][b"appinfo"][b"extended"][b"compat_tools"][name.encode()]

def get_compat_tool_appid_by_name(name):
    return int(get_compat_tool_appinfo(name)[b"appid"][1]) if name else None

def get_commands(appid):
    app = apps[appid]

    compat_name = get_compat_tool_name(appid)
    compat_appid = get_compat_tool_appid_by_name(compat_name)
    compat_app = apps.get(compat_appid)

    print(app)
    print(compat_name)

    launch_oslist = {current_os}
    if compat_app:
        # FIXME this is ugly. this data should be in CompatTool.
        # but...... appinfo is not loaded yet when CompatTools are made.
        compat_appinfo = get_compat_tool_appinfo(compat_name)
        compat_from_oslist = parse_oslist(compat_appinfo[b"from_oslist"].decode())
        compat_to_oslist = parse_oslist(compat_appinfo[b"to_oslist"].decode())
        if current_os not in compat_to_oslist:
            print("WARNING: Current OS:", current_os, "is not supported by", compat_tool_name, compat_to_oslist)

        launch_oslist = compat_from_oslist

    print("! launch_oslist =", launch_oslist)

    # TODO replace backslashes in executable if windows
    # TODO working directory
    # TODO parse os, architecture, and find correct launch config instead of using b"0"
    # TODO custom launch options
    appinfo = appinfo_data[appid]["sections"][b"appinfo"]

    ignored_betakey = {}
    ignored_oslist = {}
    ignored_osarch = {}
    for launch_config in appinfo[b"config"][b"launch"].values():
        # Ignore launch entries associated with beta keys
        # TODO support betas ?
        try:
            betakey = launch_config[b"config"][b"betakey"].decode()
            ignored_betakey[betakey] = ignored_betakey.get(betakey, 0) + 1
            continue
        except KeyError:
            pass
        try:
            oslist = parse_oslist(launch_config[b"config"][b"oslist"].decode())
        except KeyError:
            oslist = parse_oslist(appinfo[b"common"][b"oslist"].decode())

        if oslist and not oslist & launch_oslist:
            ignored_oslist[",".join(oslist)] = ignored_oslist.get(",".join(oslist), 0) + 1
            continue

        try:
            osarch = launch_config[b"config"][b"osarch"]
        except KeyError:
            osarch = appinfo[b"common"].get(b"osarch") or b""

        if type(osarch) is bytes:
            osarch = int(osarch) if osarch else None
        else:
            osarch = osarch.data

        if osarch is not None and osarch != current_osarch:
            ignored_osarch[osarch] = ignored_osarch.get(osarch, 0) + 1
            continue

        option_type = launch_config[b"type"].decode() if b"type" in launch_config else "default"
        option_description = launch_config[b"description"].decode() if b"description" in launch_config else app.name

        cmd = escape_path(app.installdir + "/" + launch_config[b"executable"].decode())
        if b"arguments" in launch_config:
            cmd += " " + launch_config[b"arguments"].decode()
        if compat_app:
            cmd = compat_app.compat_tool.get_command("waitforexitandrun", cmd)
        yield oslist, osarch, option_type, option_description
        yield cmd
        yield ""
    if ignored_betakey:
        yield "Ignored entries with beta keys: " + repr(ignored_betakey)
    if ignored_oslist:
        yield "Ignored entries with OS: " + repr(ignored_oslist)
    if ignored_osarch:
        yield "Ignored entries with arch: " + repr(ignored_osarch)

for i in [211820,1566410, 1145360, 70300, 400]:
    cmds = get_commands(i)
    for cmd in cmds:
        print("->", cmd)
    print()
