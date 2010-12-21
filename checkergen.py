#! /usr/bin/env python

"""
usage: checkergen.py [-h] [-c] [-d] [-e dir] [-f] [--fmt {bmp,tga,jpg,png}]
                     [path]

Generate flashing checkerboard patterns for display or export as a series of
images, intended for use in psychophysics experiments. Enters interactive
command line mode if no options are specified.

positional arguments:
  path                  checkergen project file to open

optional arguments:
  -h, --help              show this help message and exit
  -c, --cmd               enter command line mode regardless of other options
  -d, --display           displays the animation on the screen
  -e dir, --export dir    export the animation to the specified directory
  -f, --fullscreen        animation displayed in fullscreen mode
  --fmt {bmp,tga,jpg,png} image format for animation to be exported as
"""

import core
import cli

args = cli.PARSER.parse_args()
msg = cli.process_args(args)

if msg != None:
    print msg

if args.display_flag:
    core.display_anim(args.proj, args.fullscreen)
    # Threading not supported on Mac OSX, have to find some other way.
    #
    # display_thread = threading.Thread(target=display_anim,
    #                                   name='display_thread',
    #                                   args=[copy.deepcopy(args.proj), 
    #                                         args.fullscreen])
    # display_thread.start()
if args.export_flag:
    core.export_anim(args.proj, args.export_dir, args.export_fmt)
if args.cmd_mode:
    mycmd = cli.CkgCmd()
    mycmd.intro = cli.CMD_INTRO
    mycmd.prompt = cli.CMD_PROMPT
    mycmd.cur_proj = args.proj
    mycmd.cmdloop()
