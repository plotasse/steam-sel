# Some salt for your Steam machine

## Why

Have you ever tried running an alternative option for a game, such as, say, a
Vulkan version, or a config tool, without going through the Steam UI ? Well,
you can't. Not without this horrendous script. If you're interested, please
proceed below.

## Install

- Put steam-sel-loader in your path, and add it to the launch options for the
  games you want to run with it.
  * If you have no launch option for the game, the line is `steam-sel-loader
    %command%`. 
  * If you have launch options that include `%command%`, add `steam-sel-loader
    ` before the rest
  * Otherwise, add `steam-sel-loader %command% ` before your launch arguments.

- Python dependencies
  * this thing https://github.com/ValvePython/vdf (AUR: python-vdf)
  * this one here https://freedesktop.org/wiki/Software/pyxdg/ (Arch: python-pyxdg)
  * Good luck !

- No, seriously, I have no idea how to use setup tools so (don't) enjoy this
  mess until I get around to making this installable. 

## Usage
- Run `./steam-sel.py` to see a list of your games.
- Run `./steam-sel.py <appid>` to view the available options for a specific game.
- Run `./steam-sel.py <appid> <launch entry id>` to run your desired command
  thing.  Make sure to have `steam-sel-loader` in the launch options for the
  game as specified above.

- If nothing works, feel free to ask me. Not sure I'll be of a great help but whatever.

- Also the CLI should be better some day if I keep working on this.
  Sorry for the ugliness. Hint: `./steam-sel.py <appid> | tail -n 1 | jq`.

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
  Steam would if you had chosen the other option. If running, e.g. a game through
  proton without the compatibility options set, Steam will not provide the
  necessary environment variables and whatever the Valve devs had flying through
  their minds when designing this.

- The idea could probably be expanded upon to provide custom commands and whatnot.

- Also it should not conflict with your other launch options, whatever, enjoy.
