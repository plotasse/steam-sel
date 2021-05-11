#!/usr/bin/python3
import os
import re
from xdg.BaseDirectory import xdg_data_home
from steamfiles import acf
from appinfolazy import AppinfoLazyDecoder

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

# This is horrendous, but Steam apparently behaves this way,
# so I guess we will have to do the same. I'm deeply sorry.
def escape_path(path):
    return "'" + path.replace("'","'\\''") + "'"

apps = {}

# Create appinfo.vdf decoder
with open(main_library + "/appcache/appinfo.vdf", "rb") as appinfo_file:
    appinfo_raw = appinfo_file.read()
appinfo_decoder = AppinfoLazyDecoder(appinfo_raw)

# Load the main Steam config file. It contains the game <-> compatibility tool mappings.
with open(main_library + "/config/config.vdf", "r") as config_file:
    config_data = acf.load(config_file)

# Load the compatibility tool name <-> appid mappings.
compat_tools_info = appinfo_decoder.decode(steamplay_manifests_appid)["sections"][b"appinfo"][b"extended"][b"compat_tools"]
compat_appid_to_name = {}
compat_name_to_appid = {}
for name, data in compat_tools_info.items():
    name = name.decode()
    appid = data[b"appid"].data
    compat_appid_to_name[appid] = name
    compat_name_to_appid[name] = appid

print(compat_appid_to_name)

def get_compat_tool_appinfo(name):
    return compat_tools_info[name.encode()]

def parse_oslist(oslist):
    return set(oslist.split(",")) if oslist else set()

class App:
    def __init__(self, steamapps, appid):
        self.appid = appid

        with open(steamapps + "/appmanifest_" + str(self.appid) + ".acf") as appmanifest_file:
            self.appstate = acf.load(appmanifest_file)["AppState"]

        self.name = self.appstate["name"]
        self.installdir = os.path.realpath(steamapps + "/common/" + self.appstate["installdir"])

        self.compat_tool = None
        if self.appid in compat_appid_to_name:
            try:
                self.compat_tool = CompatTool(self)
            except FileNotFoundError:
                print(self.appid, self.name, "is a compatibility tool but has no toolmanifest.vdf")

    def __repr__(self):
        return "<App, appid=" + str(self.appid) + ", name=" + self.name + ", installdir=" + self.installdir + ">"

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

        compat_appinfo = get_compat_tool_appinfo(compat_appid_to_name[self.app.appid])
        self.from_oslist = parse_oslist(compat_appinfo[b"from_oslist"].decode())
        self.to_oslist = parse_oslist(compat_appinfo[b"to_oslist"].decode())

    def get_command(self, verb, cmd):
        cmd = escape_path(self.app.installdir) + self.commandline.replace("%verb%", verb) + " " + cmd
        # FIXME ? compatibility tool stacking ignores the lower {from,to}_oslist.
        # Then again, I have no idea if Steam itself even cares.
        if self.require_tool_appid:
            cmd = apps[self.require_tool_appid].compat_tool.get_command(verb, cmd)
        return cmd

#
# Find Steam libraries
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

manifest_re = re.compile("^appmanifest_([0-9]+)\\.acf$")
for l in libraries:
    steamapps = l + "/steamapps"
    for e in os.listdir(steamapps):
        m = manifest_re.match(e)
        if m:
            appid = int(m.group(1))
            apps[appid] = App(steamapps, appid)

for appid, app in apps.items():
    if app.compat_tool:
        print("Found compatibility tool:", app)

def get_compat_tool_name_for_app(appid):
    try:
        return config_data['InstallConfigStore']['Software']['Valve']['Steam']['CompatToolMapping'][str(appid)]['name'] or None
    except KeyError:
        return None

def get_commands(appid):
    app = apps[appid]

    compat_name = get_compat_tool_name_for_app(appid)
    compat_appid = compat_name_to_appid.get(compat_name)
    compat_tool = apps[compat_appid].compat_tool if compat_appid else None

    print(app)
    print(compat_name)

    launch_oslist = {current_os}
    if compat_tool:
        if current_os not in compat_tool.to_oslist:
            print("WARNING: Current OS:", current_os, "is not supported by", compat_tool_name, compat_to_oslist)

        launch_oslist = compat_tool.from_oslist

    print("! launch_oslist =", launch_oslist)

    # TODO working directory
    # TODO custom launch options
    appinfo = appinfo_decoder.decode(appid)["sections"][b"appinfo"]

    ignored_betakey = {}
    ignored_oslist = {}
    ignored_osarch = {}
    for launch_config_id, launch_config in appinfo[b"config"][b"launch"].items():
        launch_config_id = int(launch_config_id)
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

        executable = launch_config[b"executable"].decode()
        if "windows" in (oslist or launch_oslist) and current_os != "windows":
            executable = executable.replace("\\","/")

        cmd = escape_path(app.installdir + "/" + executable)
        if b"arguments" in launch_config:
            cmd += " " + launch_config[b"arguments"].decode()
        if compat_tool:
            cmd = compat_tool.get_command("waitforexitandrun", cmd)
        yield launch_config_id, oslist, osarch, option_type, option_description
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
