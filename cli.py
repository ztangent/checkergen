"""Defines command-line-interface for checkergen."""

import os
import sys
if os.name == 'posix':
    import readline
import argparse
import cmd
import shlex
# import threading

import core
import priority
from graphics import locations
from utils import *

CMD_PROMPT = '(ckg) '
CMD_INTRO = '\n'.join(["Enter 'help' for a list of commands.",
                       "Enter 'quit' or Ctrl-D to exit."])

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
PARSER.add_argument('-e', '--export', dest='export_dir', metavar='dir',
                    help='export the animation to the specified directory')
PARSER.add_argument('-f', '--fullscreen', action='store_true',
                    help='animation displayed in fullscreen mode')
PARSER.add_argument('--fmt', dest='export_fmt', choices=core.EXPORT_FMTS,
                    help='image format for animation to be exported as')
PARSER.add_argument('path', nargs='?', type=file,
                    help='checkergen project file to open')

def process_args(args):
    """Further processes the arguments returned by the main parser."""

    if args.export_dir != None:
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
    else:
        args.proj = None
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
        if not self.cur_proj.dirty:
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
        if not os.path.isfile(path):
            print 'error: path specified is not a file'
            return
        if self.save_check():
            return
        try:
            self.cur_proj = core.CkgProj(path=path)
        except core.FileFormatError:
            print "error:", str(sys.exc_value)
            return
        except IOError:
            print "error:", str(sys.exc_value)
            return
        os.chdir(os.path.dirname(os.path.abspath(path)))
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
                                    (color format: R,G,B or name, 
                                    component range from 0-255)''')
    set_parser.add_argument('--fmt', dest='export_fmt', 
                            choices=core.EXPORT_FMTS,
                            help='''image format for animation
                                    to be exported as''')

    def help_set(self):
        self.__class__.set_parser.print_help()

    def do_set(self, line):
        if self.cur_proj == None:
            print 'no project open, automatically creating project...'
            self.do_new('')
        try:
            args = self.__class__.set_parser.parse_args(shlex.split(line))
        except CmdParserError:
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

    mk_parser = CmdParser(add_help=False, prog='mk',
                          description='''Makes a new checkerboard with the 
                                         given parameters.''')
    mk_parser.add_argument('dims', action=store_tuple(2, ',', to_decimal),
                           help='''width,height of checkerboard in no. of 
                                   unit cells''')
    mk_parser.add_argument('init_unit', action=store_tuple(2, ',', to_decimal),
                           help='width,height of initial unit cell in pixels')
    mk_parser.add_argument('end_unit', action=store_tuple(2, ',', to_decimal),
                           help='width,height of final unit cell in pixels')
    mk_parser.add_argument('position', action=store_tuple(2, ',', to_decimal),
                           help='x,y position of checkerboard in pixels')
    mk_parser.add_argument('anchor', choices=locations,
                           help='''location of anchor point of checkerboard
                                   (choices: %(choices)s)''',
                           metavar='anchor')
    mk_parser.add_argument('cols', action=store_tuple(2, ',', to_color, [';']),
                           help='''color1,color2 of the checkerboard
                                   (color format: R;G;B or name, 
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
        try:
            args = self.__class__.mk_parser.parse_args(shlex.split(line))
        except CmdParserError:
            print "error:", str(sys.exc_value)
            self.__class__.mk_parser.print_usage()
            return
        board_dict = dict([(name, getattr(args, name)) for 
                           name in public_dir(args)])
        new_board = core.CheckerBoard(**board_dict)
        self.cur_proj.boards.append(new_board)
        self.cur_proj.dirty = True
        print "checkerboard", len(self.cur_proj.boards)-1, "added"

    ed_parser = CmdParser(add_help=False, prog='ed',
                          description='''Edits attributes of checkerboards
                                         specified by ids.''')
    ed_parser.add_argument('idlist', nargs='+', metavar='id', type=int,
                           help='ids of checkerboards to be edited')
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
    ed_parser.add_argument('--anchor', choices=locations,
                           help='''location of anchor point of checkerboard
                                   (choices: %(choices)s)''',
                           metavar='LOCATION')
    ed_parser.add_argument('--cols', metavar='COLOR1,COLOR2',
                           action=store_tuple(2, ',', to_color, [';']),
                           help='''checkerboard colors (color format:
                                   R;G;B or name, component range 
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
        try:
            args = self.__class__.ed_parser.parse_args(shlex.split(line))
        except CmdParserError:
            print "error:", str(sys.exc_value)
            self.__class__.ed_parser.print_usage()
            return
        for x in args.idlist[:]:
            if x >= len(self.cur_proj.boards) or x < 0:
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
                    setattr(self.cur_proj.boards[x], name, val)
                noflags = False
        if noflags:
            print "no options specified, please specify at least one"
            self.__class__.ed_parser.print_usage()
        else:
            self.cur_proj.dirty = True

    rm_parser = CmdParser(add_help=False, prog='rm',
                          description='''Removes checkerboards specified
                                         by ids.''')
    rm_parser.add_argument('idlist', nargs='*', metavar='id', type=int,
                           help='ids of checkerboards to be removed')
    rm_parser.add_argument('-a', '--all', action='store_true',
                           help='remove all checkerboards')

    def help_rm(self):
        self.__class__.rm_parser.print_help()

    def do_rm(self, line):
        """Removes checkerboards specified by ids"""
        if self.cur_proj == None:
            print 'please create or open a project first'
            return
        try:
            args = self.__class__.rm_parser.parse_args(shlex.split(line))
        except CmdParserError:
            print "error:", str(sys.exc_value)
            self.__class__.rm_parser.print_usage()
            return
        rmlist = []
        if args.all:
            del self.cur_proj.boards[:]
            print "all checkerboards removed"
            return
        elif len(args.idlist) == 0:
            print "please specify at least one id"
        for x in args.idlist:
            if x >= len(self.cur_proj.boards) or x < 0:
                print "checkerboard", x, "does not exist"
                continue
            rmlist.append(self.cur_proj.boards[x])
            print "checkerboard", x, "removed"
        for board in rmlist:
            self.cur_proj.boards.remove(board)
        self.cur_proj.dirty = True
        del rmlist[:]

    ls_parser = CmdParser(add_help=False, prog='ls',
                          description='''Lists project settings, checkerboards
                                         and their attributes.''')
    ls_parser.add_argument('idlist', nargs='*', metavar='id', type=int,
                           help='''ids of checkerboards to be listed, all
                                   are listed if not specified''')
    ls_group = ls_parser.add_mutually_exclusive_group()
    ls_group.add_argument('-s', '--settings', action='store_true',
                           help='list only settings')
    ls_group.add_argument('-b', '--boards', action='store_true',
                           help='list only checkerboards')

    def help_ls(self):
        self.__class__.ls_parser.print_help()

    def do_ls(self, line):
        """Lists project settings, checkerboards and their attributes."""

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
        except CmdParserError:
            print "error:", str(sys.exc_value)
            self.__class__.ls_parser.print_usage()
            return

        for x in args.idlist[:]:
            if x >= len(self.cur_proj.boards) or x < 0:
                args.idlist.remove(x)
                print "checkerboard", x, "does not exist"
        if args.idlist == []:
            args.idlist = range(len(self.cur_proj.boards))
        else:
            args.boards = True

        if not args.boards:
            print \
                'name'.rjust(13),\
                'fps'.rjust(6),\
                'resolution'.rjust(12),\
                'bg color'.rjust(16),\
                'format'.rjust(7)
            print \
                ls_str(self.cur_proj.name).rjust(13),\
                ls_str(self.cur_proj.fps).rjust(6),\
                ls_str(self.cur_proj.res).rjust(12),\
                ls_str(self.cur_proj.bg).rjust(16),\
                ls_str(self.cur_proj.export_fmt).rjust(7)

        if not args.settings and not args.boards:
            print ''

        if not args.settings:
            print \
                'id'.rjust(2),\
                'dims'.rjust(10),\
                'init_unit'.rjust(14),\
                'end_unit'.rjust(14),\
                'position'.rjust(14)
            for n, board in zip(args.idlist, self.cur_proj.boards):
                print \
                    ls_str(n).rjust(2),\
                    ls_str(board.dims).rjust(10),\
                    ls_str(board.init_unit).rjust(14),\
                    ls_str(board.end_unit).rjust(14),\
                    ls_str(board.position).rjust(14)        
            print '\n',\
                'id'.rjust(2),\
                'colors'.rjust(27),\
                'anchor'.rjust(12),\
                'freq'.rjust(6),\
                'phase'.rjust(7)
            for n, board in zip(args.idlist, self.cur_proj.boards):
                print \
                    ls_str(n).rjust(2),\
                    ls_str(board.cols).rjust(27),\
                    ls_str(board.anchor).rjust(12),\
                    ls_str(board.freq).rjust(6),\
                    ls_str(board.phase).rjust(7)            

    display_parser = CmdParser(add_help=False, prog='display',
                               description='''Displays the animation in a
                                              window or in fullscreen.
                                              Beware of setting priority
                                              to realtime.''')
    display_parser.add_argument('-f', '--fullscreen', action='store_true',
                                help='sets fullscreen mode, ESC to quit')
    display_parser.add_argument('-l', '--logtime', action='store_true',
                                help='output frame duration to a log file')
    display_parser.add_argument('-p', '--priority',
                                help='''set priority while displaying,
                                        higher priority results in
                                        less dropped frames (choices:
                                        0-3, low, normal, high,
                                        realtime)''')
                                
    def help_display(self):
        self.__class__.display_parser.print_help()

    def do_display(self, line):
        """Displays the animation in window or in fullscreen"""
        if self.cur_proj == None:
            print 'please create or open a project first'
            return
        try:
            args = self.__class__.display_parser.parse_args(shlex.split(line))
        except CmdParserError:
            print "error:", str(sys.exc_value)
            self.__class__.display_parser.print_usage()
            return
        if args.priority != None:
            if args.priority.isdigit():
                args.priority = int(args.priority)
            try:
                priority.set(args.priority)
            except (ValueError, NotImplementedError):
                print "error:", str(sys.exc_value)
                print "continuing..."
        try:
            self.cur_proj.display(args.fullscreen, args.logtime)
        except IOError:
            print "error:", str(sys.exc_value)
            return
        if args.priority != None:
            try:
                priority.set('normal')
            except:
                pass

    export_parser = CmdParser(add_help=False, prog='export',
                              description='''Exports animation as an image
                                             sequence (in a folder) to the
                                             specified directory.''')
    export_parser.add_argument('dir', nargs='?', default=os.getcwd(),
                               help='''destination directory for export
                                       (default: current working directory)''')
    export_parser.add_argument('--fmt', dest='export_fmt',
                               choices=core.EXPORT_FMTS,
                               help='image format for export')
    export_parser.add_argument('-n','--nofolder',
                               dest='folder', action='store_false',
                               help='''force images not to exported in 
                                       a containing folder''')

    def help_export(self):
        self.__class__.export_parser.print_help()

    def do_export(self, line):
        """Exports animation an image sequence to the specified directory."""
        if self.cur_proj == None:
            print 'please create or open a project first'
            return
        try:
            args = self.__class__.export_parser.parse_args(shlex.split(line))
        except CmdParserError:
            print "error:", str(sys.exc_value)
            self.__class__.export_parser.print_usage()
            return        
        try:
            self.cur_proj.export(args.dir, args.export_fmt, args.folder)
        except IOError:
            print "error:", str(sys.exc_value)
        except core.FrameOverflowError:
            print "warning:", str(sys.exc_value)
            print "Are you sure you want to continue?"
            while True:
                try:
                    if self.__class__.yn_parse(raw_input()):
                        self.cur_proj.export(args.dir, args.export_fmt, 
                                             args.folder, True)
                        break
                    else:
                        return
                except TypeError:
                    print str(sys.exc_value)
                except EOFError:
                    return True
        print "Export done."

    def do_quit(self, line):
        """Quits the program."""
        return True

    def do_EOF(self, line):
        """Typing Ctrl-D issues this command, which quits the program."""
        print '\r'
        return True

    def help_help(self):
        print 'Prints a list of commands.'
        print 'Type help <topic> for more details on each command.'
