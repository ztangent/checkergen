#! /usr/bin/env python

"""
usage: checkergen.py [-h] [-c] [-d] [-e DUR] [-f] [--dir PATH] [project]

Generate flashing checkerboard patterns for display or export as a series of
images, intended for use in psychophysics experiments. Enters interactive
command line mode if no options are specified.

positional arguments:
  project               checkergen project file to open

optional arguments:
  -h, --help            show this help message and exit
  -c, --cmd             enter command line mode regardless of other options
  -d, --display         displays the animation on the screen
  -e DUR, --export DUR  export DUR seconds of the project animation
  -f, --fullscreen      animation displayed in fullscreen mode
  --dir PATH            destination directory for export (default: current
                        working directory)
"""

import core
import cli

args = cli.PARSER.parse_args()
msg = cli.process_args(args)

if msg != None:
    print msg

if args.export_flag:
    args.proj.export(export_dir=args.export_dir,
                     export_duration=args.export_dur)
if args.display_flag:
    args.proj.display(fullscreen=args.fullscreen)
if args.cmd_mode:
    mycmd = cli.CkgCmd()
    mycmd.intro = cli.CMD_INTRO
    mycmd.prompt = cli.CMD_PROMPT
    mycmd.cur_proj = args.proj
    mycmd.cur_group = args.group
    mycmd.cmdloop()
