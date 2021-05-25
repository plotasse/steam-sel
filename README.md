# Some salt for your Steam machine

## Why

Have you ever tried running an alternative option for a game, such as, say, a
Vulkan version, or a config tool, without going through the Steam UI ? Well,
you can't. Not without this horrendous script. If you're interested, please
proceed below.

## Disclaimer

You know how Steam randomly deletes files from people's disks ? Well this
probably will do so as well. Or maybe not. The only written files should be in
`$XDG_RUNTIME_DIR`, so as long as it's set (and it *should* check for it to be
set), everything should be fine. Unless the script generates a faulty game
startup command. Or your favorite game devs do. Whatever, you've been warned.

## Install

- Put steam-sel-loader in your PATH, and add it to the launch options for the
  games you want to run with it.
  * If you have no launch option for the game, the line is `steam-sel-loader
    %command%`. 
  * If you have launch options that include `%command%`, add `steam-sel-loader
    ` before the rest
  * Otherwise, add `steam-sel-loader %command% ` before your launch arguments.

- Python dependencies
  * this thing https://github.com/ValvePython/vdf (AUR: python-vdf)
  * this one here https://freedesktop.org/wiki/Software/pyxdg/ (Arch: python-pyxdg)

- I have no idea how to use setup tools so (don't) enjoy this mess until I get
  around to making this installable. It seems a symbolic link from somewhere in your
  PATH to `steam-sel` in the cloned repository does work.

## Usage
- Run `./steam-sel` to see a list of your games.
- Run `./steam-sel <appid>` to view the available options for a specific game.
- Run `./steam-sel <appid> <launch entry id>` to run your desired command
  thing.  Make sure to have `steam-sel-loader` in the launch options for the
  game as specified above.
- If nothing works, feel free to ask me. Not sure I'll be of a great help but whatever.
- Here is the built-in help:
```text
usage: steam-sel [-h] [-n] [--analyze] [app] [config]

positional arguments:
  app            Steam AppId or name of the game to run. Name matching is
                 case-insensitive and does not require the full name. Without
                 this argument, list the installed games.
  config         Identifier of the launch config to use. Can be a numeric
                 index or a type (default, server, config,…). When
                 unspecified, list the available configs for app.

optional arguments:
  -h, --help     show this help message and exit
  -n, --dry-run  Display the command instead of running it
  --analyze      Analyze all the games and report which are unlaunchable and
                 which have multiple configurations.
```


## How this works

- The python script tries to mimic the black magic from the Steam client which
  generates the commands for launching the games. This is the hardest part.

- Once you have choosen a command it writes a bash file (Steam uses bash to run
  every game, please don't blame me) to `$XDG_RUNTIME_DIR/steam-sel/<appid>`,
  then it calls `steam +applaunch <appid>`.

- Steam runs the game and here the magic happens: the `steam-sel-loader`
  script, which you have set in the launch options for the game, finds the file
  written previously. It runs it and then deletes it. That's all.

- If you run the game through any normal means, such as the Steam GUI, a `steam://`
  URL or whatever, `steam-sel-loader` will see that there is nothing in
  `$XDG_RUNTIME_DIR/steam-sel/<appid>`, so it will just run the `%command%`
  passed by Steam.

- This does not override any compatibility tool and tries to behave exactly as
  Steam would normally do. If you were to run a game through proton without the
  compatibility options set, Steam would not provide the necessary environment
  variables and whatever the Valve devs had flying through their minds when
  designing this.

- The idea could probably be expanded upon to provide custom commands and whatnot.

- Also it should not conflict with your other launch options, whatever, enjoy.
