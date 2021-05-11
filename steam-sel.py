#!/usr/bin/python3
import os
import sys
import subprocess

from operator import attrgetter

import re
import json

from xdg import BaseDirectory

from appinfolazy import AppinfoLazyDecoder
import vdf

#
# CONFIGURATION
#

# Your main Steam installation.
main_library = BaseDirectory.xdg_data_home + "/Steam"

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

# This is your user ID to be substituted in $main_library/userdata/<id>.
# We need this because the launch options are stored below the userdata directory.
# If set to None, the script will try to use the "MostRecent" user, which we read
# from $main_library/config/loginusers.vdf
steam_user_id = None

# This is the script name. It is used as a subdirectory of $XDG_RUNTIME_DIR
# for storing temporary files. It must be the same in the corresponding loader script.
script_name = "steam-sel"

#
# END CONFIGURATION
#

# This is horrendous, but Steam apparently behaves this way,
# so I guess we will have to do the same. I'm deeply sorry.
def escape_path(path):
    return "'" + path.replace("'","'\\''") + "'"

apps = {}

# If steam_user_id is None, try to figure it out
if steam_user_id is None:
    with open(main_library + "/config/loginusers.vdf", "r") as loginusers_file:
        loginusers = vdf.load(loginusers_file)
    for userid, userdata in loginusers["users"].items():
        if int(userdata["MostRecent"]) == 1:
            # also we have to remove the higher 32 bits, for some reason
            steam_user_id = int(userid) & (1 << 32) - 1
            print(userid, userdata)

print("steam_user_id =", steam_user_id)
if type(steam_user_id) is not int:
    print("steam_user_id is not an int, abort")
    exit(1)

# Create appinfo.vdf decoder
with open(main_library + "/appcache/appinfo.vdf", "rb") as appinfo_file:
    appinfo_raw = appinfo_file.read()
appinfo_decoder = AppinfoLazyDecoder(appinfo_raw)

# Load the main Steam config file. It contains the game <-> compatibility tool mappings.
with open(main_library + "/config/config.vdf", "r") as config_file:
    config_data = vdf.load(config_file)

# Load the user config file. It contains the per-game launch options.
with open(main_library + "/userdata/" + str(steam_user_id) + "/config/localconfig.vdf", "r") as user_config_file:
    user_config = vdf.load(user_config_file)

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
            self.appstate = vdf.load(appmanifest_file)["AppState"]

        self.name = self.appstate["name"]
        self.installdir = os.path.realpath(steamapps + "/common/" + self.appstate["installdir"])

        self.compat_tool = None
        if self.appid in compat_appid_to_name:
            try:
                self.compat_tool = CompatTool(self)
            except FileNotFoundError:
                print(self.appid, self.name, "is a compatibility tool but has no toolmanifest.vdf")

    def __repr__(self):
        return "\033[35m * \033[33m" + self.name + "\033[35m (" + str(self.appid) + "), " + self.installdir + "\033[0m"

class CompatTool:
    def __init__(self, app):
        self.app = app

        with open(app.installdir + "/toolmanifest.vdf") as toolmanifest_file:
            toolmanifest = vdf.load(toolmanifest_file)["manifest"]

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
        d = vdf.load(f)
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

for app in sorted(apps.values(), key=attrgetter("name")):
    print(app)

def get_compat_tool_name_for_app(appid):
    try:
        return config_data['InstallConfigStore']['Software']['Valve']['Steam']['CompatToolMapping'][str(appid)]['name'] or None
    except KeyError:
        return None

# FIXME: appinfo should be embedded in app
# also, we don't need to laod all apps, only the one requested + compatibility tools
class LaunchEntry:
    def __init__(self, entry_id, app, appinfo, launch_config, launch_oslist, compat_tool=None, launch_options = None):
        self.id = entry_id

        self.type = launch_config[b"type"].decode() if b"type" in launch_config else "none"

        self.description = launch_config[b"description"].decode() if b"description" in launch_config else app.name

        # Get the OS list from the launch config, if unavailable default to the app's.
        try:
            self.oslist = parse_oslist(launch_config[b"config"][b"oslist"].decode())
        except KeyError:
            self.oslist = parse_oslist(appinfo[b"common"][b"oslist"].decode())

        # Same for the architecture.
        try:
            self.osarch = launch_config[b"config"][b"osarch"]
        except KeyError:
            self.osarch = appinfo[b"common"].get(b"osarch") or b""

        # We need some more parsing, because some entries have it in a string, other in integer form.
        if type(self.osarch) is bytes:
            self.osarch = int(self.osarch) if self.osarch else None
        else:
            self.osarch = self.osarch.data

        # Get the beta key, if any.
        try:
            self.betakey = launch_config[b"config"][b"betakey"].decode()
        except KeyError:
            self.betakey = None

        # Get the working dir and executable name, which will be processed shortly after.
        try:
            self.workingdir = launch_config[b"workingdir"].decode()
        except KeyError:
            self.workingdir = None

        self.executable = launch_config[b"executable"].decode()

        # When running windows software on anything but windows, replace backslashes with the regular ones.
        if "windows" in (self.oslist or launch_oslist) and current_os != "windows":
            if self.workingdir:
                self.workingdir = self.workingdir.replace("\\", "/")
            self.executable = self.executable.replace("\\", "/")

        # Prepend the app install dir to the working dir, and default to it.
        if self.workingdir:
            self.workingdir = app.installdir + "/" + self.workingdir
        else:
            self.workingdir = app.installdir

        # Build the command.
        self.cmd = escape_path(app.installdir + "/" + self.executable)

        # It seems we have to escape the backslashes.
        # I would like that to be the last stealth idiocy I have to deal with.
        if b"arguments" in launch_config:
            self.cmd += " " + launch_config[b"arguments"].decode().replace("\\","\\\\")

        # I have no idea what other verbs there may be. Steam seems to only use this one.
        if compat_tool:
            self.cmd = compat_tool.get_command("waitforexitandrun", self.cmd)

        if launch_options:
            if "%command%" in launch_options:
                self.cmd = launch_options.replace("%command%", self.cmd)
            else:
                self.cmd = self.cmd + " " + launch_options

    def as_dict(self):
        return { "id": self.id,
                 "type": self.type,
                 "description": self.description,
                 "oslist": list(self.oslist),
                 "osarch": self.osarch,
                 "betakey": self.betakey,
                 "workingdir": self.workingdir,
                 "executable": self.executable,
                 "cmd": self.cmd,
                 }

    def __repr__(self):
        return self.id
        #return repr(self.as_dict())

def get_commands(appid, get_all=False):
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

    launch_options = user_config["UserLocalConfigStore"]["Software"]["Valve"]["Steam"]["Apps"][str(appid)].get("LaunchOptions")
    print("Launch options:", repr(launch_options))
    appinfo = appinfo_decoder.decode(appid)["sections"][b"appinfo"]

    ignored_betakey = {}
    ignored_oslist = {}
    ignored_osarch = {}
    for launch_config_id, launch_config in appinfo[b"config"][b"launch"].items():
        launch_entry = LaunchEntry(int(launch_config_id), app, appinfo, launch_config, launch_oslist, compat_tool, launch_options)

        # Ignore launch entries associated with beta keys.
        # TODO support betas ?
        if not get_all and launch_entry.betakey:
            ignored_betakey[launch_entry.betakey] = ignored_betakey.get(launch_entry.betakey, 0) + 1
            continue

        # Ignore entries not corresponding to the launch OS (which may be altered by a compatibility tool).
        if not get_all and launch_entry.oslist and not launch_entry.oslist & launch_oslist:
            ignored_oslist[",".join(launch_entry.oslist)] = ignored_oslist.get(",".join(launch_entry.oslist), 0) + 1
            continue

        # Ignore entries from the wrong architecture. Yes, this includes 32-bit ones on a 64-bit OS.
        # Yes, many games including a 32-bit build usually have a "64-bit" entry to circumvent this.
        # Thanks Valve.
        if not get_all and launch_entry.osarch is not None and launch_entry.osarch != current_osarch:
            ignored_osarch[launch_entry.osarch] = ignored_osarch.get(launch_entry.osarch, 0) + 1
            continue

        yield (int(launch_config_id), launch_entry)

    if ignored_betakey:
        print("Ignored entries with beta keys: " + repr(ignored_betakey))
    if ignored_oslist:
        print("Ignored entries with OS: " + repr(ignored_oslist))
    if ignored_osarch:
        print("Ignored entries with arch: " + repr(ignored_osarch))

if __name__ == "__main__":
    if len(sys.argv) == 2:
        entries = get_commands(int(sys.argv[1]))
        print(json.dumps(dict([(k, v.as_dict()) for k,v in entries])))

        for entry_id, entry in entries:
            print(entry)

    elif len(sys.argv) == 3:
        appid = int(sys.argv[1])
        launch_id = int(sys.argv[2])

        entries = dict(get_commands(appid))
        entry = entries[launch_id]

        print(json.dumps(entry.as_dict()))

        d = BaseDirectory.get_runtime_dir() + "/" + script_name
        if not os.path.isdir(d):
            os.mkdir(d)
        p = d + "/" + str(appid)
        with open(p, "w") as f:
            f.write("\n".join([
                "#!/bin/bash",
                "cd " + escape_path(entry.workingdir),
                entry.cmd,
                '']))
        os.chmod(p, 0o755)
        #subprocess.run(["steam", "-applaunch", str(appid)])
