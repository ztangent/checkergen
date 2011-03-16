"""Defines command-line-interface for checkergen."""

import os
import sys
if os.name == 'posix':
    import readline
import argparse
import cmd
import shlex

import core
import priority
import eyetracking
from graphics import locations
from utils import *

CMD_PROMPT = '(ckg) '
CMD_EOF_STRING = 'Ctrl-D'
if sys.platform == 'win32':
    CMD_EOF_STRING = 'Ctrl-Z + Enter'
CMD_INTRO = '\n'.join(["Enter 'help' for a list of commands.",
                       "Enter 'quit' or {0} to exit.".format(CMD_EOF_STRING)])

def store_tuple(nargs, sep, typecast=None, castargs=[]):
    """Returns argparse action that stores a tuple."""
    class TupleAction(argparse.Action):
        def __call__(self, parser, args, values, option_string=None):
            vallist = values.split(sep)
            if len(vallist) != nargs:
                msg = ("argument '{f}' should be a list of " + 
                       "{nargs} values separated by '{sep}'").\
                       format(f=self.dest,nargs=nargs,sep=sep)
                raise argparse.ArgumentError(self, msg)
            if typecast != None:
                for n, val in enumerate(vallist):
                    try:
                        val = typecast(*([val] + castargs))
                        vallist[n] = val
                    except (ValueError, TypeError):
                        msg = ("element '{val}' of argument '{f}' " +
                               "is of the wrong type").\
                               format(val=vallist[n],f=self.dest)
                        raise argparse.ArgumentError(self, msg)
            setattr(args, self.dest, tuple(vallist))
    return TupleAction

# The main parser invoked at the command-line
PARSER = argparse.ArgumentParser(
    description='''Generate flashing checkerboard patterns for display
                   or export as a series of images, intended for use in
                   psychophysics experiments. Enters interactive command
                   line mode if no options are specified.''')

PARSER.add_argument('-c', '--cmd', dest='cmd_mode', action='store_true',
                    help='enter command line mode regardless of other options')
PARSER.add_argument('-d', '--display',
                    dest='display_flag', action='store_true',
                    help='displays the animation on the screen')
PARSER.add_argument('-e', '--export', dest='export_dur', metavar='DUR',
                    help='export DUR seconds of the project animation')
PARSER.add_argument('-f', '--fullscreen', action='store_true',
                    help='animation displayed in fullscreen mode')
# PARSER.add_argument('--fmt', dest='export_fmt', choices=core.EXPORT_FMTS,
#                     help='image format for animation to be exported as')
PARSER.add_argument('--dir', dest='export_dir', 
                    default=os.getcwd(), metavar='PATH',
                    help='''destination directory for export
                            (default: current working directory)''')
PARSER.add_argument('path', metavar='project', nargs='?', type=file,
                    help='checkergen project file to open')

def process_args(args):
    """Further processes the arguments returned by the main parser."""

    if args.export_dur != None:
        args.export_flag = True
    else:
        args.export_flag = False

    if not args.display_flag and not args.export_flag:
        args.cmd_mode = True

    if args.path != None:
        if not os.path.isfile(args.path):
            msg = 'error: path specified is not a file'
            return msg
        args.proj = core.CkgProj(path=args.path)
        os.chdir(os.path.dirname(os.path.abspath(args.path)))
        try:
            args.group = args.proj.groups[0]
        except IndexError:
            args.group = None
    else:
        args.proj = None
        args.group = None
        if args.display_flag or args.export_flag:
            msg = 'error: no project file specified for display or export'
            return msg

class CmdParserError(Exception):
    """To be raised when CmdParser encounters an error."""
    pass

class CmdParser(argparse.ArgumentParser):
    """Override ArgumentParser so that it doesn't exit the program."""
    def error(self, msg):
        raise CmdParserError(msg)
        
class CkgCmd(cmd.Cmd):

    @staticmethod
    def yn_parse(s):
        if s in ['y', 'Y', 'yes', 'YES', 'Yes']:
            return True
        elif s in ['n', 'N', 'no', 'NO', 'No']:
            return False
        else:
            msg = "only 'y','n' or variants accepted"
            raise ValueError(msg)

    def save_check(self, msg=None):
        """Checks and prompts the user to save if necessary."""
        if self.cur_proj == None:
            return
        if not self.cur_proj.is_dirty():
            return
        if msg == None:
            msg = 'Would you like to save the current project first? (y/n)'
        print msg
        while True:
            try:
                if self.__class__.yn_parse(raw_input()):
                    self.do_save('')
                break
            except TypeError:
                print str(sys.exc_value)
            except EOFError:
                return True

    def do_new(self, line):
        """Creates new project with given name (can contain whitespace)."""
        name = line.strip().strip('"\'')
        if len(name) == 0:
            name = 'untitled'
        if self.save_check():
            return
        self.cur_proj = core.CkgProj(name=name)
        print 'project \'{0}\' created'.format(self.cur_proj.name)

    def do_open(self, line):
        """Open specified project file."""
        path = line.strip().strip('"\'') 
        if len(path) == 0:
            print 'error: no path specified'
            return
        if self.save_check():
            return
        try:
            self.cur_proj = core.CkgProj(path=path)
        except (core.FileFormatError, IOError):
            print "error:", str(sys.exc_value)
            return
        os.chdir(os.path.dirname(os.path.abspath(path)))
        try:
            self.cur_group = self.cur_proj.groups[0]
        except IndexError:
            self.cur_group = None
        print 'project \'{0}\' loaded'.format(self.cur_proj.name)

    def do_close(self, line):
        """Prompts the user to save, then closes current project."""
        if self.cur_proj == None:
            print 'no project to close'
            return
        if self.save_check():
            return
        self.cur_proj = None
        print 'project closed'

    def do_save(self, line):
        """Saves the current project to the specified path."""
        if self.cur_proj == None:
            print 'no project to save'
            return
        path = line.strip().strip('"\'') 
        if len(path) == 0:
            path = os.getcwd()
        path = os.path.abspath(path)
        if os.path.isdir(path):
            path = os.path.join(path, 
                                '.'.join([self.cur_proj.name, core.CKG_FMT]))
        elif os.path.isdir(os.path.dirname(path)):
            pass
        else:
            print 'error: specified directory does not exist'
            return
        # project save will add file extension if necessary
        try:
            path = self.cur_proj.save(path)
        except IOError:
            print "error:", str(sys.exc_value)
            return
        print 'project saved to "{0}"'.format(path)

    set_parser = CmdParser(add_help=False, prog='set',
                          description='''Sets various project settings.''')
    set_parser.add_argument('--name', help='''project name, always the same as
                                              the filename without
                                              the extension''')
    set_parser.add_argument('--fps', type=to_decimal,
                            help='''number of animation frames
                                    rendered per second''')
    set_parser.add_argument('--res', action=store_tuple(2, ',', int),
                            help='animation canvas size/resolution in pixels',
                            metavar='WIDTH,HEIGHT')
    set_parser.add_argument('--bg', metavar='COLOR', type=to_color,
                            help='''background color of the canvas
                                    (color format: R,G,B,
                                    component range from 0-255)''')
    # set_parser.add_argument('--fmt', dest='export_fmt', 
    #                         choices=core.EXPORT_FMTS,
    #                         help='''image format for animation
    #                                 to be exported as''')
    set_parser.add_argument('--pre', type=to_decimal, metavar='SECONDS',
                              help='''time in seconds a blank screen will
                                      be shown before any display groups''')
    set_parser.add_argument('--post', type=to_decimal, metavar='SECONDS',
                              help='''time in seconds a blank screen will
                                      be shown after all display groups''')
    set_parser.add_argument('--cross_cols', metavar='COLOR1,COLOR2',
                            action=store_tuple(2, ',', to_color, [';']),
                            help='''fixation cross coloration
                                    (color format: R;G;B, 
                                    component range from 0-255)''')
    set_parser.add_argument('--cross_times', metavar='TIME1,TIME2',
                           action=store_tuple(2, ',', to_decimal),
                           help='''time in seconds each cross color
                                   will be displayed''')

    def help_set(self):
        self.__class__.set_parser.print_help()

    def do_set(self, line):
        if self.cur_proj == None:
            print 'no project open, automatically creating project...'
            self.do_new('')
        try:
            args = self.__class__.set_parser.parse_args(shlex.split(line))
        except (CmdParserError, ValueError):
            print "error:", str(sys.exc_value)
            self.__class__.set_parser.print_usage()
            return
        names = public_dir(args)
        noflags = True
        for name in names:
            val = getattr(args, name)
            if val != None:
                setattr(self.cur_proj, name, val)
                noflags = False
        if noflags:
            print "no options specified, please specify at least one"
            self.__class__.set_parser.print_usage()

    mkgrp_parser = CmdParser(add_help=False, prog='mkgrp',
                             formatter_class=
                             argparse.ArgumentDefaultsHelpFormatter,
                             description='''Makes a new display group
                                            with the given parameters.''')
    mkgrp_parser.add_argument('pre', type=to_decimal, default=0, nargs='?',
                              help='''time in seconds a blank screen will
                                      be shown before shapes are displayed''')
    mkgrp_parser.add_argument('disp', type=to_decimal,
                              nargs='?', default='Infinity',
                              help='''time in seconds shapes will be 
                                      displayed''')
    mkgrp_parser.add_argument('post', type=to_decimal, default=0, nargs='?',
                              help='''time in seconds a blank screen will
                                      be shown after shapes are displayed''')

    def help_mkgrp(self):
        self.__class__.mkgrp_parser.print_help()

    def do_mkgrp(self, line):
        """Makes a display group with the given parameters."""
        if self.cur_proj == None:
            print 'no project open, automatically creating project...'
            self.do_new('')
        try:
            args = self.__class__.mkgrp_parser.parse_args(shlex.split(line))
        except (CmdParserError, ValueError):
            print "error:", str(sys.exc_value)
            self.__class__.mkgrp_parser.print_usage()
            return
        group_dict = dict([(name, getattr(args, name)) for 
                           name in public_dir(args)])
        new_group = core.CkgDisplayGroup(**group_dict)
        new_id = self.cur_proj.add_group(new_group)
        print "display group", new_id, "added"
        self.cur_group = new_group
        print "group", new_id, "is now the current display group"

    edgrp_parser = CmdParser(add_help=False, prog='edgrp',
                          description='''Edits attributes of display groups
                                         specified by ids.''')
    edgrp_parser.add_argument('idlist', nargs='+', metavar='id', type=int,
                              help='ids of display groups to be edited')
    edgrp_parser.add_argument('--pre', type=to_decimal, metavar='SECONDS',
                              help='''time in seconds a blank screen will
                                      be shown before shapes are displayed''')
    edgrp_parser.add_argument('--disp', type=to_decimal, metavar='SECONDS',
                              help='''time in seconds shapes will be 
                                      displayed''')
    edgrp_parser.add_argument('--post', type=to_decimal, metavar='SECONDS',
                              help='''time in seconds a blank screen will
                                      be shown after shapes are displayed''')
    def help_edgrp(self):
        self.__class__.edgrp_parser.print_help()

    def do_edgrp(self, line):
        """Edits attributes of checkerboards specified by ids."""
        if self.cur_proj == None:
            print 'please create or open a project first'
            return
        try:
            args = self.__class__.edgrp_parser.parse_args(shlex.split(line))
        except (CmdParserError, ValueError):
            print "error:", str(sys.exc_value)
            self.__class__.edgrp_parser.print_usage()
            return
        # Remove duplicates and ascending sort
        args.idlist = sorted(set(args.idlist))
        for x in args.idlist[:]:
            if x >= len(self.cur_proj.groups) or x < 0:
                args.idlist.remove(x)
                print "checkerboard", x, "does not exist"
        if args.idlist == []:
            return
        names = public_dir(args)
        names.remove('idlist')
        noflags = True
        for name in names:
            val = getattr(args, name)
            if val != None:
                for x in args.idlist:
                    self.cur_proj.set_group_attr(x, name, val)
                noflags = False
        if noflags:
            print "no options specified, please specify at least one"
            self.__class__.edgrp_parser.print_usage()

    rmgrp_parser = CmdParser(add_help=False, prog='rmgrp',
                             description='''Removes display groups specified
                                            by ids.''')
    rmgrp_parser.add_argument('idlist', nargs='*', metavar='id', type=int,
                              help='ids of display groups to be removed')
    rmgrp_parser.add_argument('-a', '--all', action='store_true',
                              help='remove all groups from the project')

    def help_rmgrp(self):
        self.__class__.rmgrp_parser.print_help()

    def do_rmgrp(self, line):
        """Removes display groups specified by ids"""
        if self.cur_proj == None:
            print 'please create or open a project first'
            return
        elif self.cur_group == None:
            print 'current project has no groups to remove'
            return
        try:
            args = self.__class__.rmgrp_parser.parse_args(shlex.split(line))
        except (CmdParserError, ValueError):
            print "error:", str(sys.exc_value)
            self.__class__.rmgrp_parser.print_usage()
            return
        rmlist = []
        if args.all:
            for group in self.cur_proj.groups[:]:
                self.cur_proj.del_group(group)
            print "all display groups removed"
            return
        elif len(args.idlist) == 0:
            print "please specify at least one id"
        # Remove duplicates and ascending sort
        args.idlist = sorted(set(args.idlist))
        for x in args.idlist:
            if x >= len(self.cur_proj.groups) or x < 0:
                print "display group", x, "does not exist"
                continue
            rmlist.append(self.cur_proj.groups[x])
            print "display group", x, "removed"
        for group in rmlist:
            self.cur_proj.del_group(group)
        # Remember to point self.cur_group somewhere sane
        if self.cur_group not in self.cur_proj.groups:
            if len(self.cur_proj.groups) == 0:
                self.cur_group = None
            else:
                self.cur_group = self.cur_proj.groups[0]
                print "group 0 is now the current display group"

    chgrp_parser = CmdParser(add_help=False, prog='chgrp',
                             description='''Changes display group that is 
                                            currently active for editing.
                                            Prints current group id if 
                                            no group id is specified''')
    chgrp_parser.add_argument('gid', metavar='id', type=int, nargs='?',
                              help='id of display group to be made active')

    def help_chgrp(self):
        self.__class__.chgrp_parser.print_help()

    def do_chgrp(self, line):
        """Changes group that is currently active for editing."""
        if self.cur_proj == None:
            print 'please create or open a project first'
            return
        elif self.cur_group == None:
            print 'current project has no groups that can be made active'
            return
        try:
            args = self.__class__.chgrp_parser.parse_args(shlex.split(line))
        except (CmdParserError, ValueError):
            print "error:", str(sys.exc_value)
            self.__class__.chgrp_parser.print_usage()
            return
        if args.gid == None:
            print "group",\
                self.cur_proj.groups.index(self.cur_group),\
                "is the current display group"
        elif args.gid >= len(self.cur_proj.groups) or args.gid < 0:
            print "group", args.gid, "does not exist"
        else:
            self.cur_group = self.cur_proj.groups[args.gid]
            print "group", args.gid, "is now the current display group"

    mk_parser = CmdParser(add_help=False, prog='mk',
                          description='''Makes a new checkerboard in the 
                                         current group with the given 
                                         parameters.''')
    mk_parser.add_argument('dims', action=store_tuple(2, ',', to_decimal),
                           help='''width,height of checkerboard in no. of 
                                   unit cells''')
    mk_parser.add_argument('init_unit', action=store_tuple(2, ',', to_decimal),
                           help='width,height of initial unit cell in pixels')
    mk_parser.add_argument('end_unit', action=store_tuple(2, ',', to_decimal),
                           help='width,height of final unit cell in pixels')
    mk_parser.add_argument('position', action=store_tuple(2, ',', to_decimal),
                           help='x,y position of checkerboard in pixels')
    mk_parser.add_argument('anchor', choices=sorted(locations.keys()),
                           help='''location of anchor point of checkerboard
                                   (choices: %(choices)s)''',
                           metavar='anchor')
    mk_parser.add_argument('cols', action=store_tuple(2, ',', to_color, [';']),
                           help='''color1,color2 of the checkerboard
                                   (color format: R;G;B, 
                                   component range from 0-255)''')
    mk_parser.add_argument('freq', type=to_decimal,
                           help='frequency of color reversal in Hz')
    mk_parser.add_argument('phase', type=to_decimal, nargs='?', default='0',
                           help='initial phase of animation in degrees')

    def help_mk(self):
        self.__class__.mk_parser.print_help()

    def do_mk(self, line):
        """Makes a checkerboard with the given parameters."""
        if self.cur_proj == None:
            print 'no project open, automatically creating project...'
            self.do_new('')
        if self.cur_group == None:
            print 'automatically adding display group...'
            self.do_mkgrp('')
        try:
            args = self.__class__.mk_parser.parse_args(shlex.split(line))
        except (CmdParserError, ValueError):
            print "error:", str(sys.exc_value)
            self.__class__.mk_parser.print_usage()
            return
        shape_dict = dict([(name, getattr(args, name)) for 
                           name in public_dir(args)])
        new_shape = core.CheckerBoard(**shape_dict)
        new_id = self.cur_proj.add_shape_to_group(self.cur_group, new_shape)
        print "checkerboard", new_id, "added"

    ed_parser = CmdParser(add_help=False, prog='ed',
                          description='''Edits attributes of checkerboards
                                         specified by ids.''')
    ed_parser.add_argument('idlist', nargs='+', metavar='id', type=int,
                           help='''ids of checkerboards in the current 
                                   group to be edited''')
    ed_parser.add_argument('--dims', action=store_tuple(2, ',', to_decimal),
                           help='checkerboard dimensions in unit cells',
                           metavar='WIDTH,HEIGHT')
    ed_parser.add_argument('--init_unit',
                           action=store_tuple(2, ',', to_decimal),
                           help='initial unit cell dimensions in pixels',
                           metavar='WIDTH,HEIGHT')
    ed_parser.add_argument('--end_unit',
                           action=store_tuple(2, ',', to_decimal),
                           help='final unit cell dimensions in pixels',
                           metavar='WIDTH,HEIGHT')
    ed_parser.add_argument('--position',
                           action=store_tuple(2, ',', to_decimal),
                           help='position of checkerboard in pixels',
                           metavar='X,Y')
    ed_parser.add_argument('--anchor', choices=sorted(locations.keys()),
                           help='''location of anchor point of checkerboard
                                   (choices: %(choices)s)''',
                           metavar='LOCATION')
    ed_parser.add_argument('--cols', metavar='COLOR1,COLOR2',
                           action=store_tuple(2, ',', to_color, [';']),
                           help='''checkerboard colors (color format:
                                   R;G;B, component range 
                                   from 0-255)''')
    ed_parser.add_argument('--freq', type=to_decimal,
                           help='frequency of color reversal in Hz')
    ed_parser.add_argument('--phase', type=to_decimal,
                           help='initial phase of animation in degrees')

    def help_ed(self):
        self.__class__.ed_parser.print_help()

    def do_ed(self, line):
        """Edits attributes of checkerboards specified by ids."""
        if self.cur_proj == None:
            print 'please create or open a project first'
            return
        elif self.cur_group == None:
            print 'current project has no groups, please create one first'
            return
        try:
            args = self.__class__.ed_parser.parse_args(shlex.split(line))
        except (CmdParserError, ValueError):
            print "error:", str(sys.exc_value)
            self.__class__.ed_parser.print_usage()
            return
        # Remove duplicates and ascending sort
        args.idlist = sorted(set(args.idlist))
        for x in args.idlist[:]:
            if x >= len(self.cur_group.shapes) or x < 0:
                args.idlist.remove(x)
                print "checkerboard", x, "does not exist"
        if args.idlist == []:
            return
        names = public_dir(args)
        names.remove('idlist')
        noflags = True
        for name in names:
            val = getattr(args, name)
            if val != None:
                for x in args.idlist:
                    self.cur_proj.set_shape_attr(self.cur_group, x, name, val)
                noflags = False
        if noflags:
            print "no options specified, please specify at least one"
            self.__class__.ed_parser.print_usage()

    rm_parser = CmdParser(add_help=False, prog='rm',
                          description='''Removes checkerboards specified
                                         by ids.''')
    rm_parser.add_argument('idlist', nargs='*', metavar='id', type=int,
                           help='''ids of checkerboards in the current group
                                   to be removed''')
    rm_parser.add_argument('-a', '--all', action='store_true',
                           help='''remove all checkerboards in the 
                                   current group''')

    def help_rm(self):
        self.__class__.rm_parser.print_help()

    def do_rm(self, line):
        """Removes checkerboards specified by ids"""
        if self.cur_proj == None:
            print 'please create or open a project first'
            return
        elif self.cur_group == None:
            print 'current project has no groups, no boards to remove'
            return
        try:
            args = self.__class__.rm_parser.parse_args(shlex.split(line))
        except (CmdParserError, ValueError):
            print "error:", str(sys.exc_value)
            self.__class__.rm_parser.print_usage()
            return
        rmlist = []
        if args.all:
            for shape in self.cur_group.shapes:
                self.cur_proj.del_shape_from_group(self.cur_group, shape)
            print "all checkerboards removed"
            return
        elif len(args.idlist) == 0:
            print "please specify at least one id"
        # Remove duplicates and ascending sort
        args.idlist = sorted(set(args.idlist))
        for x in args.idlist:
            if x >= len(self.cur_group.shapes) or x < 0:
                print "checkerboard", x, "does not exist"
                continue
            rmlist.append(self.cur_group.shapes[x])
            print "checkerboard", x, "removed"
        for shape in rmlist:
            self.cur_proj.del_shape_from_group(self.cur_group, shape)

    ls_parser = CmdParser(add_help=False, prog='ls',
                          description='''Lists project, display group and
                                         checkerboard settings. If no group ids
                                         are specified, all display groups 
                                         are listed.''')
    ls_parser.add_argument('gidlist', nargs='*', metavar='gid', type=int,
                           help='''ids of the display groups to be listed''')
    ls_group = ls_parser.add_mutually_exclusive_group()
    ls_group.add_argument('-s', '--settings', action='store_true',
                           help='list only project settings')
    ls_group.add_argument('-g', '--groups', action='store_true',
                           help='list only display groups')

    def help_ls(self):
        self.__class__.ls_parser.print_help()

    def do_ls(self, line):
        """Lists project, display group and checkerboard settings."""

        def ls_str(s, seps=[',',';']):
            """Special space-saving output formatter."""
            if type(s) in [tuple, list]:
                if len(seps) > 1:
                    newseps = seps[1:]
                else:
                    newseps = seps
                return seps[0].join([ls_str(i, newseps) for i in s])
            else:
                return str(s)

        if self.cur_proj == None:
            print 'please create or open a project first'
            return
        try:
            args = self.__class__.ls_parser.parse_args(shlex.split(line))
        except (CmdParserError, ValueError):
            print "error:", str(sys.exc_value)
            self.__class__.ls_parser.print_usage()
            return
        
        # Remove duplicates and ascending sort
        args.gidlist = sorted(set(args.gidlist))

        if len(self.cur_proj.groups) == 0:
            if len(args.gidlist) > 0:
                print 'this project has no display groups that can be listed'
            args.settings = True
        else:
            for gid in args.gidlist[:]:
                if gid >= len(self.cur_proj.groups) or gid < 0:
                    args.gidlist.remove(gid)
                    print 'display group', gid, 'does not exist'
            if args.gidlist == []:
                args.gidlist = range(len(self.cur_proj.groups))
            else:
                # If any (valid) groups are specified
                # don't show project settings
                args.groups = True

        if not args.groups:
            print 'PROJECT SETTINGS'.center(70,'*')
            print \
                'name'.rjust(16),\
                'fps'.rjust(7),\
                'resolution'.rjust(14),\
                'bg color'.rjust(18)
                # 'format'.rjust(7)
            print \
                ls_str(self.cur_proj.name).rjust(16),\
                ls_str(self.cur_proj.fps).rjust(7),\
                ls_str(self.cur_proj.res).rjust(14),\
                ls_str(self.cur_proj.bg).rjust(18)
                # ls_str(self.cur_proj.export_fmt).rjust(7)
            print \
                'pre-display'.rjust(26),\
                'post-display'.rjust(26)
            print \
                ls_str(self.cur_proj.pre).rjust(26),\
                ls_str(self.cur_proj.post).rjust(26)
            print \
                'cross colors'.rjust(26),\
                'cross times'.rjust(26)
            print \
                ls_str(self.cur_proj.cross_cols).rjust(26),\
                ls_str(self.cur_proj.cross_times).rjust(26)


        if not args.settings and not args.groups:
            # Insert empty line if both groups and project 
            # settings are listed
            print ''

        if not args.settings:
            for i, n in enumerate(args.gidlist):
                if i != 0:
                    # Print newline seperator between each group
                    print ''
                group = self.cur_proj.groups[n]
                print 'GROUP {n}'.format(n=n).center(70,'*')
                print \
                    'pre-display'.rjust(20),\
                    'display'.rjust(20),\
                    'post-display'.rjust(20)
                print \
                    ls_str(group.pre).rjust(20),\
                    ls_str(group.disp).rjust(20),\
                    ls_str(group.post).rjust(20)
                if len(group.shapes) > 0:
                    print \
                        ''.rjust(2),\
                        'shape id'.rjust(8),\
                        'dims'.rjust(10),\
                        'init_unit'.rjust(14),\
                        'end_unit'.rjust(14),\
                        'position'.rjust(14)
                    for m, shape in enumerate(group.shapes):
                        print \
                            ''.rjust(2),\
                            ls_str(m).rjust(8),\
                            ls_str(shape.dims).rjust(10),\
                            ls_str(shape.init_unit).rjust(14),\
                            ls_str(shape.end_unit).rjust(14),\
                            ls_str(shape.position).rjust(14)
                    print '\n',\
                        ''.rjust(2),\
                        'shape id'.rjust(8),\
                        'colors'.rjust(27),\
                        'anchor'.rjust(12),\
                        'freq'.rjust(6),\
                        'phase'.rjust(7)
                    for m, shape in enumerate(group.shapes):
                        print \
                            ''.rjust(2),\
                            ls_str(m).rjust(8),\
                            ls_str(shape.cols).rjust(27),\
                            ls_str(shape.anchor).rjust(12),\
                            ls_str(shape.freq).rjust(6),\
                            ls_str(shape.phase).rjust(7)

    display_parser = CmdParser(add_help=False, prog='display',
                               description='''Displays the animation in a
                                              window or in fullscreen.''')
    display_parser.add_argument('-b', '--block', metavar='PATH',
                                help='''read flags and dislay group order from
                                        specified file, ignore other flags''')
    display_parser.add_argument('-f', '--fullscreen', action='store_true',
                                help='sets fullscreen mode, ESC to quit')
    display_parser.add_argument('-p', '--priority', metavar='LEVEL',
                                help='''set priority while displaying,
                                        higher priority results in
                                        less dropped frames (choices:
                                        0-3, low, normal, high,
                                        realtime)''')
    display_parser.add_argument('-r', '--repeat', metavar='N', type=int,
                                help='''repeatedly display specified display
                                        groups N number of times''')
    display_parser.add_argument('-pt', '--phototest', action='store_true',
                                help='''draw white test rectangle in topleft
                                        corner of screen when groups become
                                        visible for a photodiode to detect''')
    display_parser.add_argument('-pb', '--photoburst', action='store_true',
                                help='''make checkerboards only draw first
                                        color for one frame to facilitate
                                        testing with a photodiode''')
    display_parser.add_argument('-lt', '--logtime', action='store_true',
                                help='output frame timestamps to a log file')
    display_parser.add_argument('-ld', '--logdur', action='store_true',
                                help='output frame durations to a log file')
    display_parser.add_argument('-ss', '--sigser', action='store_true',
                                help='''send signals through the serial port 
                                        when shapes are being displayed''')
    display_parser.add_argument('-sp', '--sigpar', action='store_true',
                                help='''send signals through the parallel port 
                                        when shapes are being displayed''')
    display_parser.add_argument('-fpbs', metavar='M', type=int, default=0,
                                help='''unique signal corresponding to a
                                        checkerboard is sent after the board
                                        undergoes M color flips (default:
                                        disabled, M=0)''')
    display_parser.add_argument('-et', '--eyetrack', action='store_true',
                                help='''use eyetracking to ensure that subject
                                        fixates on the cross in the center''')
    display_parser.add_argument('-eu', '--etuser', action='store_true',
                                help='''allow user to select eyetracking video
                                        source from a dialog''')
    display_parser.add_argument('-ev', '--etvideo', metavar='path',
                                help='''path (with no spaces) to eyetracking
                                        video file to be used as the source''')
    display_parser.add_argument('-ta', '--tryagain', metavar='I',
                                type=int, default=0,
                                help='''append groups during which subject
                                        failed to fixate up to I times to the
                                        list of groups to be displayed
                                        (default: disabled, I=0)''')
    display_parser.add_argument('-tb', '--trybreak', metavar='J', type=int,
                                help='''used with --tryagain, append a wait
                                        screen to the list of groups to be
                                        displayed after every J groups have
                                        been appended to the list (default:
                                        J=total number of groups)''')
    display_parser.add_argument('idlist', nargs='*', metavar='id', type=int,
                                help='''list of display groups to be displayed
                                        in the specified order (default: order
                                        by id, i.e. group 0 is first)''')
                                
    def help_display(self):
        self.__class__.display_parser.print_help()

    def do_display(self, line):
        """Displays the animation in a window or in fullscreen"""
        if self.cur_proj == None:
            print 'please create or open a project first'
            return

        try:
            args = self.__class__.display_parser.parse_args(shlex.split(line))
        except (CmdParserError, ValueError):
            print "error:", str(sys.exc_value)
            self.__class__.display_parser.print_usage()
            return

        if args.block != None:
            blkpath = args.block
            try:
                blkdict = core.CkgProj.readblk(blkpath)
                flags = blkdict['flags']
                try:
                    args = self.__class__.\
                        display_parser.parse_args(shlex.split(flags))
                    args.idlist = blkdict['idlist']
                except (CmdParserError, ValueError):
                    print 'error: invalid flags stored in block file'
                    return
            except IOError:
                print "error:", str(sys.exc_value)
                return
        else:
            blkpath = None

        groupq = []
        if len(args.idlist) > 0:
            for i in set(args.idlist):
                if i >= len(self.cur_proj.groups) or i < -1:
                    print 'error: group', i, 'does not exist'
                    return
            for i in args.idlist:
                if i == -1:
                    groupq.append(core.CkgWaitScreen(res=
                                                          self.cur_proj.res))
                else:
                    groupq.append(self.cur_proj.groups[i])
        else:
            groupq = list(self.cur_proj.groups)
        if args.repeat != None:
            groupq = list(groupq * args.repeat)

        if args.eyetrack and eyetracking.available:
            if not eyetracking.is_calibrated():
                try:
                    self.do_calibrate('',True)
                except eyetracking.EyetrackingError:
                    print "error:", str(sys.exc_value)
                    return

        if args.priority != None:
            if not priority.available:
                print "error: setting priority not avaible on", sys.platform
                print "continuing..."
            else:
                if args.priority.isdigit():
                    args.priority = int(args.priority)
                try:
                    priority.set(args.priority)
                except ValueError:
                    print "error:", str(sys.exc_value)
                    print "continuing..."

        try:
            fail_idlist = self.cur_proj.display(fullscreen=args.fullscreen,
                                                logtime=args.logtime,
                                                logdur=args.logdur,
                                                sigser=args.sigser,
                                                sigpar=args.sigpar,
                                                fpbs=args.fpbs,
                                                phototest=args.phototest,
                                                photoburst=args.photoburst,
                                                eyetrack=args.eyetrack,
                                                etuser=args.etuser,
                                                etvideo=args.etvideo,
                                                tryagain=args.tryagain,
                                                trybreak=args.trybreak,
                                                groupq=groupq)
        except (IOError, NotImplementedError, eyetracking.EyetrackingError):
            print "error:", str(sys.exc_value)
            if args.priority != None:
                try:
                    priority.set('normal')
                except:
                    pass
            return

        if args.priority != None:
            try:
                priority.set('normal')
            except:
                pass

        # Append list of ids of failed groups to block file
        if fail_idlist != None and blkpath != None:
            try:
                core.CkgProj.addtoblk(blkpath, fail_idlist,
                                      len(self.cur_proj.groups))
            except IOError:
                print "error:", str(sys.exc_value)
                return

    export_parser = CmdParser(add_help=False, prog='export',
                              description='''Exports animation as an image
                                             sequence (in a folder) to the
                                             specified directory.''')
    # export_parser.add_argument('--fmt', dest='export_fmt',
    #                            choices=core.EXPORT_FMTS,
    #                            help='image format for export')
    export_parser.add_argument('-n','--nofolder',
                               dest='folder', action='store_false',
                               help='''force images not to exported in 
                                       a containing folder''')
    export_parser.add_argument('-r', '--repeat', metavar='N', type=int,
                                help='''repeatedly export specified display
                                        groups N number of times''')
    export_parser.add_argument('duration', nargs='?',
                               type=to_decimal, default='Infinity',
                               help='''number of seconds of the animation
                                       that should be exported (default:
                                       as long as the entire animation)''')
    export_parser.add_argument('dir', nargs='?', default=os.getcwd(),
                               help='''destination directory for export
                                       (default: current working directory)''')
    export_parser.add_argument('idlist', nargs='*', metavar='id', type=int,
                               help='''list of display groups to be exported
                                       in the specified order (default: order
                                       by id, i.e. group 0 is first)''')

    def help_export(self):
        self.__class__.export_parser.print_help()

    def do_export(self, line):
        """Exports animation an image sequence to the specified directory."""
        if self.cur_proj == None:
            print 'please create or open a project first'
            return

        try:
            args = self.__class__.export_parser.parse_args(shlex.split(line))
        except (CmdParserError, ValueError):
            print "error:", str(sys.exc_value)
            self.__class__.export_parser.print_usage()
            return        

        if len(args.idlist) > 0:
            for i in set(args.idlist):
                if i >= len(self.cur_proj.groups) or i < 0:
                    print 'error: group', i, 'does not exist'
                    return
            groupq = [self.cur_proj.groups[i] for i in args.idlist]
        else:
            groupq = list(self.cur_proj.groups)
        if args.repeat != None:
            groupq = list(groupq * args.repeat)

        try:
            self.cur_proj.export(export_dir=args.dir,
                                 export_duration=args.duration,
                                 groupq=groupq,
                                 folder=args.folder)
        except IOError:
            print "error:", str(sys.exc_value)
            return
        except core.FrameOverflowError:
            print "warning:", str(sys.exc_value)
            print "Are you sure you want to continue?"
            while True:
                try:
                    if self.__class__.yn_parse(raw_input()):
                        self.cur_proj.export(export_dir=args.dir,
                                             export_duration=args.duration,
                                             groupq=groupq,
                                             export_fmt=None,
                                             folder=args.folder,
                                             force=True)
                        break
                    else:
                        return
                except TypeError:
                    print str(sys.exc_value)
                except EOFError:
                    return

        print "Export done."

    mkblks_parser = CmdParser(add_help=False, prog='mkblks',
                              description='''Generates randomized experimental
                                             blocks from display groups and
                                             saves each as a CSV file.''')
    mkblks_parser.add_argument('-n','--nofolder',
                               dest='folder', action='store_false',
                               help='''force block files not to be saved in 
                                       a containing folder''')
    mkblks_parser.add_argument('-d','--dir', default=os.getcwd(),
                               help='''where to save block files
                                       (default: current working directory)''')
    mkblks_parser.add_argument('length', type=int,
                               help='''no. of repeated trials in a block''')
    mkblks_parser.add_argument('flags', nargs='?', default='',
                               help='''flags passed to the display command
                                       that should be used when the block
                                       file is run (enclose in quotes and use
                                       '+' or '++' in place of '-' or '--')''')

    def help_mkblks(self):
        self.__class__.mkblks_parser.print_help()

    def do_mkblks(self, line):
        """Generates randomized experimental blocks from display groups."""
        if self.cur_proj == None:
            print 'please create or open a project first'
            return

        try:
            args = self.__class__.mkblks_parser.parse_args(shlex.split(line))
        except (CmdParserError, ValueError):
            print "error:", str(sys.exc_value)
            self.__class__.mkblks_parser.print_usage()
            return

        args.flags = args.flags.replace('+','-')
        try:
            disp_args = self.__class__.display_parser.\
                parse_args(shlex.split(args.flags))
        except (CmdParserError, ValueError):
            print "error: invalid flags to display command"
            print str(sys.exc_value)
            self.__class__.display_parser.print_usage()
            return        

        try:
            self.cur_proj.mkblks(args.length,
                                 path=args.dir,
                                 folder=args.folder,
                                 flags=args.flags)
        except IOError:
            print "error:", str(sys.exc_value)
            return

        print "Experimental blocks generated."

    def do_calibrate(self, line, query=False):
        """Calibrate subject for eyetracking, or load a calibration file."""
        if not eyetracking.available:
            print "error: eyetracking functionality not available"
            return
        if query:
            print "path to calibration file (leave empty for GUI tool):"
            try:
                path = raw_input().strip().strip('"\'')
            except EOFError:
                msg = "calibration cancelled"
                raise eyetracking.EyetrackingError(msg)
        else:
            path = line.strip().strip('"\'')
        if len(path) == 0:
            path = None
            if not eyetracking.is_source_ready():
                # Select default source if none has been selected
                eyetracking.select_source()
        try:
            eyetracking.calibrate(path)
        except eyetracking.EyetrackingError:
            if query:
                raise
            else:
                print "error:", str(sys.exc_value)
                return
        if len(path) > 0:
            print "calibration file successfully loaded"

    etsetup_parser = CmdParser(add_help=False, prog='etsetup',
                               description='''Set various eyetracking
                                              parameters.''')
    etsetup_parser.add_argument('-fp', '--fixperiod', type=int, metavar='MS',
                                help='''time in milliseconds subject
                                        has to stare at the same spot
                                        for fixation to be detected''')
    etsetup_parser.add_argument('-fr', '--fixrange', type=float, metavar='MM',
                                help='''distance in mm beyond which the
                                        eye position cannot change for
                                        a fixation to be detected''')
    etsetup_parser.add_argument('-s', '--size', metavar='WIDTH,HEIGHT',
                                action=store_tuple(2, ',', float),
                                help='physical screen dimensions in mm')
    etsetup_parser.add_argument('-vd', '--viewdist', type=int, metavar='MM',
                                help='''viewing distance between subject's
                                        eyes and the screen''')

    def help_etsetup(self):
        self.__class__.etsetup_parser.print_help()

    def do_etsetup(self, line):
        try:
            args = self.__class__.etsetup_parser.parse_args(shlex.split(line))
        except (CmdParserError, ValueError):
            print "error:", str(sys.exc_value)
            self.__class__.etsetup_parser.print_usage()
            return
        try:
            eyetracking.setup(viewing_distance=args.viewdist,
                              screen_dims=args.size,
                              fixation_period=args.fixperiod,
                              fixation_range=args.fixrange)
        except eyetracking.EyetrackingError:
            print "error:", str(sys.exc_value)

    def do_pwd(self, line):
        """Prints the current working directory."""
        print os.getcwd()

    def do_cd(self, line):
        """Change working directory to specified path."""
        path = line.strip().strip('"\'')
        if not os.path.isdir(path):
            print "error: specified path is not a directory"
            return
        os.chdir(path)
    
    def do_quit(self, line):
        """Quits the program."""
        if self.save_check():
            return
        return True

    def help_EOF(self):
        print "Typing {0} issues this command, which quits the program."\
            .format(CMD_EOF_STRING)

    def do_EOF(self, line):
        """Typing Ctrl-D issues this command, which quits the program."""
        print '\r'
        if self.save_check():
            return
        return True

    def help_help(self):
        print 'Prints a list of commands.'
        print "Type 'help <topic>' for more details on each command."

    def default(self, line):
        command = line.split()[0]
        print \
            "'{0}' is not a checkergen command.".format(command),\
            "Type 'help' for a list of commands"
