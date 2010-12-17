#! /usr/bin/env python

import os
import sys
import copy
import textwrap
import readline
import argparse
import cmd
import threading
import math
from decimal import *

import pygame
from pygame.locals import *

CKG_FMT = 'ckg'
DEFAULT_NAME = 'untitled'
DEFAULT_FPS = 60
DEFAULT_RES = 800, 600
DEFAULT_BG = Color(127, 127, 127)
EXPORT_FMTS = ['bmp', 'tga', 'jpg', 'png']
DEFAULT_EXPORT_FMT = 'png'

def gcd(a, b):
    """Return greatest common divisor using Euclid's Algorithm."""
    while b > 0:      
        a, b = b, a % b
    return a

def lcm(a, b):
    """Return lowest common multiple."""
    return a * b // gcd(a, b)

def numdigits(x):
    """Returns number of digits in a decimal integer."""
    if x == 0:
        return 1
    elif x < 0:
        x = -x
    return int(math.log(x, 10)) + 1

def public_dir(obj):
    """Returns all 'public' attributes of an object"""
    names = dir(obj)
    for name in names[:]:
        if name[0] == '_' or name[-1] == '_':
            names.remove(name)
    return names

def yn_parse(s):
    if s in ['y', 'Y', 'yes', 'YES', 'Yes']:
        return True
    elif s in ['n', 'N', 'no', 'NO', 'No']:
        return False
    else:
        msg = "only 'y','n' or variants accepted"
        raise TypeError(msg)

def col_cast(s, sep=','):
    """Tries to cast a string to a Color"""
    try:
        c = Color(s)
    except ValueError:
        c = Color(*[int(x) for x in s.split(sep)])
    return c                        

def store_tuple(nargs, sep, typecast=None, castargs=[]):
    """Retuns argparse action that stores a tuple."""
    class TupleAction(argparse.Action):
        def __call__(self, parser, args, values, option_string=None):
            vallist = values.split(sep)
            if len(vallist) != nargs:
                msg = ("argument '{f}' should be a list of " + 
                       "{nargs} values separated by '{sep}'").\
                       format(f=self.dest,nargs=nargs,sep=sep)
                raise argparse.ArgumentTypeError(msg)
            if typecast != None:
                for n, val in enumerate(vallist):
                    try:
                        val = typecast(*([val] + castargs))
                        vallist[n] = val
                    except (ValueError, TypeError, InvalidOperation):
                        msg = ("element '{val}' of argument '{f}' " +
                               "is of the wrong type").\
                               format(val=vallist[n],f=self.dest)
                        raise argparse.ArgumentTypeError(msg)
            setattr(args, self.dest, tuple(vallist))
    return TupleAction

class CkgProj:
    
    def __init__(self, name=DEFAULT_NAME, fps=DEFAULT_FPS, res=DEFAULT_RES, 
                 bg=DEFAULT_BG, export_fmt=DEFAULT_EXPORT_FMT, path=None):
        if path != None:
            self.load(path)
            return
        self.name = str(name)
        self.fps = Decimal(str(fps))
        self.res = tuple([int(d) for d in res])
        self.bg = bg
        self.bg.set_length(3)
        if export_fmt in EXPORT_FMTS:
            self.export_fmt = export_fmt
        else:
            msg = 'image format not recognized or supported'
            raise TypeError(msg)
        self.boards = []
        self.dirty = True

    def load(self, path):
        # TODO: Extension checking
        self.name = os.path.splitext(os.path.basename(path))[0]
        self.dirty = False        

    def save(self, path):
        self.name = os.path.splitext(os.path.basename(path))[0]
        self.dirty = False
        
class CheckerBoard:

    locations = {'topleft': (1, 1), 'topright': (-1, 1),
                 'btmleft': (1, -1), 'btmright': (-1, -1),
                 'topcenter': (0, 1), 'btmcenter': (0, -1),
                 'centerleft': (1, 0), 'centerright': (-1, 0),
                 'center': (0, 0)}

    def __init__(self, dims, init_unit, end_unit, position, origin, 
                 cols, freq, phase=0):
        self.dims = tuple([int(x) for x in dims])
        self.init_unit = tuple([Decimal(str(x)) for x in init_unit])
        self.end_unit = tuple([Decimal(str(x)) for x in end_unit])
        self.position = tuple([Decimal(str(x)) for x in position])
        if origin in CheckerBoard.locations and type(origin) == str:
            self.origin = origin
        else:
            raise TypeError
        self.cols = tuple(cols)
        for col in self.cols:
            col.set_length(3)
        self.freq = Decimal(str(freq))
        self.phase = Decimal(str(phase))
        self.cur_phase = self.phase
        self.unit_grad = tuple([(2 if (flag == 0) else 1) * 
                                (y2 - y1) / dx for y1, y2, dx, flag in 
                                zip(self.init_unit, self.end_unit, 
                                    self.dims, self.origin)])

    def update(self, attr, val):
        setattr(self, attr, val)
        if attr == 'cols':
            for col in self.cols:
                col.set_length(3)            
        if attr in ['dims','init_unit','end_unit','origin']:
            self.unit_grad = tuple([(2 if (flag == 0) else 1) * 
                                    (y2 - y1) / dx for y1, y2, dx, flag in 
                                    zip(self.init_unit, self.end_unit, 
                                        self.dims, self.origin)])

    def draw(self, Surface, position=None):
        Surface.lock()
        if position == None:
            position = self.position
        else:
            position = tuple([Decimal(str(x)) for x in position])
        # Set initial values
        init_unit = [c + m/2 for c, m in zip(self.init_unit, self.unit_grad)]
        init_pos = list(position)
        for n, v in enumerate(CheckerBoard.locations[self.origin]):
            if v == 0:
                init_unit[n] = self.end_unit[n] - (self.unit_grad[n] / 2)
                init_pos[n] -= ((self.init_unit[n] + self.end_unit[n]) / 2 *
                                self.dims[n] / Decimal(2))
        cur_unit = list(init_unit)
        cur_unit_pos = list(init_pos)
        # Draw unit cells in nested for loop
        for j in range(self.dims[1]):
            for i in range(self.dims[0]):
                cur_unit_rect = cur_unit_pos + cur_unit
                # Ensure unit cells are drawn in the right place
                for n, v in enumerate(CheckerBoard.locations[self.origin]):
                    if v < 0:
                        cur_unit_rect[n] -= cur_unit[n]                
                cur_unit_rect = [int(round(x)) for x in cur_unit_rect]
                if 180 <= self.phase < 360:
                    cur_cols = list(reversed(self.cols)) 
                else:
                    cur_cols = list(self.cols)
                Surface.fill(cur_cols[(i + j) % 2], tuple(cur_unit_rect))
                # Increase x values
                if CheckerBoard.locations[self.origin][0] == 0:
                    cur_unit_pos[0] += cur_unit[0]
                    if Decimal(i + 1) < (self.dims[0] / Decimal(2)):
                        cur_unit[0] -= self.unit_grad[0]
                    elif Decimal(i + 1) > (self.dims[0] / Decimal(2)):
                        cur_unit[0] += self.unit_grad[0]
                    else:
                        pass
                else:
                    cur_unit_pos[0] += CheckerBoard.locations[self.origin][0]*\
                                       cur_unit[0]
                    cur_unit[0] += self.unit_grad[0]
            # Reset x values
            cur_unit_pos[0] = init_pos[0]
            cur_unit[0] = init_unit[0]
            # Increase y values
            if CheckerBoard.locations[self.origin][1] == 0:
                cur_unit_pos[1] += cur_unit[1]
                if Decimal(j + 1) < (self.dims[1] / Decimal(2)):
                    cur_unit[1] -= self.unit_grad[1]
                elif Decimal(j + 1) > (self.dims[1] / Decimal(2)):
                    cur_unit[1] += self.unit_grad[1]
                else:
                    pass
            else:
                cur_unit_pos[1] += CheckerBoard.locations[self.origin][1]*\
                                   cur_unit[1]
                cur_unit[1] += self.unit_grad[1]
        Surface.unlock()

    def reset(self, cur_phase=None):
        if cur_phase == None:
            cur_phase = self.phase
        self.cur_phase = cur_phase

    def anim(self, Surface, position=None, fps=DEFAULT_FPS):
        self.draw(Surface, position)
        if self.freq != 0:
            fpp = fps / self.freq
            self.cur_phase += 360 / fpp
            if self.cur_phase >= 360:
                self.cur_phase -= 360

def display_anim(proj):
    pygame.init()
    screen = pygame.display.set_mode(proj.res)
    screen.fill(proj.bg)
    pygame.display.set_caption('checkergen')    
    clock = pygame.time.Clock()

    for board in proj.boards:
        board.reset()

    while True:
        clock.tick(proj.fps)
        for event in pygame.event.get():
            if event.type == QUIT:
                return
        screen.lock()
        for board in proj.boards:
            board.anim(screen, fps=proj.fps)
        screen.unlock()
        python.display.flip()

def export_anim(proj, export_dir, export_fmt=None):
    if export_fmt == None:
        export_fmt = proj.export_fmt
    pygame.init()
    screen = pygame.Surface(proj.res)
    screen.fill(proj.bg)
    fpps = [proj.fps / board.freq for board in proj.boards if board.freq != 0]
    frames = reduce(lcm, fpps)
    count = 0

    for board in proj.boards:
        board.reset()

    while count < frames:
        screen.lock()
        for board in proj.boards:
            board.anim(screen, fps=proj.fps)
        screen.unlock()
        savepath = os.path.join(export_dir, 
                                '{0}{2}.{1}'.
                                format(proj.name, export_fmt,
                                       repr(count).zfill(numdigits(frames-1))))
        pygame.image.save(screen, savepath)
        count += 1

class CmdParser(argparse.ArgumentParser):
    def error(self, message):
        raise SyntaxError(message)
        
class CkgCmd(cmd.Cmd):

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
                if yn_parse(raw_input()):
                    self.do_save('')
                break
            except TypeError:
                print str(sys.exc_info()[1])
            except EOFError:
                return True

    def do_new(self, line):
        """Creates new project with given name (can contain whitespace)."""
        name = line.strip().strip('"\'')
        if len(name) == 0:
            name = 'untitled'
        if self.save_check():
            return
        self.cur_proj = CkgProj(name=name)
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
        self.cur_proj = CkgProj(path=path)
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
            path = os.path.join(path, '.'.join([self.cur_proj.name, CKG_FMT]))
        elif os.path.isdir(os.path.dirname(path)):
            if path[-4:] != ('.' + CKG_FMT):
                print 'error: specified filepath lacks \'.{0}\' extension'.\
                      format(CKG_FMT)
                return
        else:
            print 'error: specified directory does not exist'
            return
        self.cur_proj.save(path)
        print 'project saved to "{0}"'.format(path)

    set_parser = CmdParser(add_help=False, prog='set',
                          description='''Sets various project settings.''')
    set_parser.add_argument('--name', help='project name, always same as ' +\
                                           'filename without the extension')
    set_parser.add_argument('--fps', type=Decimal,
                            help='number of animation frames ' +\
                                 'rendered per second')
    set_parser.add_argument('--res', action=store_tuple(2, ',', int),
                            help='animation canvas size/resolution in pixels',
                            metavar='WIDTH,HEIGHT')
    set_parser.add_argument('--bg', metavar='COLOR', type=col_cast,
                            help='background color of the canvas' +
                                 '(color format: R,G,B or name, ' + 
                                 'component range from 0-255)')
    set_parser.add_argument('--fmt', dest='export_fmt', choices=EXPORT_FMTS,
                            help='image format for animation ' +\
                                 'to be exported as')

    def do_set(self, line):
        if self.cur_proj == None:
            self.do_new('')
        try:
            args = CkgCmd.set_parser.parse_args(line.split())
        except (SyntaxError, InvalidOperation,
                argparse.ArgumentError, argparse.ArgumentTypeError):
            print "error:", str(sys.exc_info()[1])
            if sys.exc_info()[0] in (SyntaxError, argparse.ArgumentError):
                CkgCmd.set_parser.print_usage()
            return
        names = public_dir(args)
        noflags = True
        for name in names:
            val = getattr(args, name)
            if val != None:
                setattr(self.cur_proj, name, val)
                noflags = False
        if noflags:
            print "error: no options specified, please specify at least one"
            CkgCmd.set_parser.print_usage()
        else:
            self.cur_proj.dirty = True

    def help_set(self):
        CkgCmd.set_parser.print_help()

    mk_parser = CmdParser(add_help=False, prog='mk',
                          description='''Makes a new checkerboard with the 
                                         given parameters.''')
    mk_parser.add_argument('dims', action=store_tuple(2, ',', Decimal),
                           help='width,height of checkerboard in no. of ' +
                                'unit cells')
    mk_parser.add_argument('init_unit', action=store_tuple(2, ',', Decimal),
                           help='width,height of initial unit cell in ' +
                                'pixels')
    mk_parser.add_argument('end_unit', action=store_tuple(2, ',', Decimal),
                           help='width,height of final unit cell in ' +
                                'pixels')
    mk_parser.add_argument('position', action=store_tuple(2, ',', Decimal),
                           help='x,y position of checkerboard in pixels')
    mk_parser.add_argument('origin', choices=CheckerBoard.locations,
                           help='location of origin point of checkerboard ' +
                                '(choices: %(choices)s)',
                           metavar='origin')
    mk_parser.add_argument('cols', action=store_tuple(2, ',', col_cast, [';']),
                           help='color1,color2 of the checkerboard ' +
                                '(color format: R;G;B or name, ' + 
                                'component range from 0-255)')
    mk_parser.add_argument('freq', type=Decimal,
                           help='frequency of color reversal in Hz')
    mk_parser.add_argument('phase', type=Decimal, nargs='?', default='0',
                           help='initial phase of animation in degrees')

    def do_mk(self, line):
        """Makes a checkerboard with the given parameters."""
        if self.cur_proj == None:
            self.do_new('')
        try:
            args = CkgCmd.mk_parser.parse_args(line.split())
        except (SyntaxError, InvalidOperation,
                argparse.ArgumentError, argparse.ArgumentTypeError):
            print "error:", str(sys.exc_info()[1])
            if sys.exc_info()[0] in (SyntaxError, argparse.ArgumentError):
                CkgCmd.mk_parser.print_usage()
            return
        newboard = CheckerBoard(dims=args.dims,
                                init_unit=args.init_unit,
                                end_unit=args.end_unit,
                                position=args.position,
                                origin=args.origin,
                                cols=args.cols,
                                freq=args.freq,
                                phase=args.phase)
        self.cur_proj.boards.append(newboard)
        self.cur_proj.dirty = True
        print "checkerboard", len(self.cur_proj.boards)-1, "added"

    def help_mk(self):
        CkgCmd.mk_parser.print_help()

    ed_parser = CmdParser(add_help=False, prog='ed',
                          description='''Edits attributes of checkerboards
                                         specified by ids.''')
    ed_parser.add_argument('idlist', nargs='+', metavar='id', type=int,
                           help='ids of checkerboards to be edited')
    ed_parser.add_argument('--dims', action=store_tuple(2, ',', Decimal),
                           help='checkerboard dimensions in unit cells',
                           metavar='WIDTH,HEIGHT')
    ed_parser.add_argument('--init_unit', action=store_tuple(2, ',', Decimal),
                           help='initial unit cell dimensions in pixels',
                           metavar='WIDTH,HEIGHT')
    ed_parser.add_argument('--end_unit', action=store_tuple(2, ',', Decimal),
                           help='final unit cell dimensions in pixels',
                           metavar='WIDTH,HEIGHT')
    ed_parser.add_argument('--position', action=store_tuple(2, ',', Decimal),
                           help='position of checkerboard in pixels',
                           metavar='X,Y')
    ed_parser.add_argument('--origin', choices=CheckerBoard.locations,
                           help='location of origin point of checkerboard ' +
                                '(choices: %(choices)s)',
                           metavar='LOCATION')
    ed_parser.add_argument('--cols', metavar='COLOR1,COLOR2',
                           action=store_tuple(2, ',', col_cast, [';']),
                           help='checkerboard colors (color format: ' +
                                'R;G;B or name, component range from 0-255)')
    ed_parser.add_argument('--freq', type=Decimal,
                           help='frequency of color reversal in Hz')
    ed_parser.add_argument('--phase', type=Decimal,
                           help='initial phase of animation in degrees')

    def do_ed(self, line):
        """Edits attributes of checkerboards specified by ids."""
        if self.cur_proj == None:
            self.do_new('')
        try:
            args = CkgCmd.ed_parser.parse_args(line.split())
        except (SyntaxError, InvalidOperation,
                argparse.ArgumentError, argparse.ArgumentTypeError):
            print "error:", str(sys.exc_info()[1])
            if sys.exc_info()[0] in (SyntaxError, argparse.ArgumentError):
                CkgCmd.ed_parser.print_usage()
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
                    self.cur_proj.boards[x].update(name, val)
                noflags = False
        if noflags:
            print "error: no options specified, please specify at least one"
            CkgCmd.ed_parser.print_usage()
        else:
            self.cur_proj.dirty = True

    def help_ed(self):
        CkgCmd.ed_parser.print_help()

    def do_rm(self, line):
        """Removes checkerboards specified by ids"""
        if self.cur_proj == None:
            self.do_new('')
        idlist = line.split()
        if len(idlist) == 0:
            print "error: too few arguments"
        rmlist = []
        for x in idlist:
            if x == 'all':
                del self.cur_proj.boards[:]
                print "all checkerboards removed"
                return
            try:
                x = int(x)
            except ValueError:
                print "ignoring non-integral argument '{x}'".format(x=x)
                continue
            if x >= len(self.cur_proj.boards) or x < 0:
                print "checkerboard", x, "does not exist"
                continue
            rmlist.append(self.cur_proj.boards[x])
            print "checkerboard", x, "removed"
        for board in rmlist:
            self.cur_proj.boards.remove(board)
        self.cur_proj.dirty = True
        del rmlist[:]

    def help_rm(self):
        print 'usage: rm id [id ...]'
        print 'Removes all checkerboards specified by the ids.'

    def do_ls(self, line):
        """Lists project settings, checkerboards and their attributes."""
        if self.cur_proj == None:
            print 'please create or open a project first'
            return

        ls_settings = True
        ls_boards = True

        if len(line) > 0:
            arg = line.split()[0]
            if arg == 'boards':
                ls_settings = False
            elif arg == 'settings':
                ls_boards = False

        if ls_settings:
            print 'name'.rjust(13),\
                'fps'.rjust(6),\
                'res'.rjust(12),\
                'bg color'.rjust(16),\
                'fmt'.rjust(7)
            name = self.cur_proj.name
            fps = str(self.cur_proj.fps)
            res = [str(i) for i in self.cur_proj.res]
            res = ','.join(res)
            bg = str(tuple(self.cur_proj.bg)).translate(None,' ')
            export_fmt = self.cur_proj.export_fmt
            print name.rjust(13),\
                fps.rjust(6),\
                res.rjust(12),\
                bg.rjust(16),\
                export_fmt.rjust(7)

        if ls_settings and ls_boards:
            print ''

        if ls_boards:
            print 'id'.rjust(2),\
                'dims'.rjust(10),\
                'init_unit'.rjust(14),\
                'end_unit'.rjust(14),\
                'position'.rjust(14)
            for n, board in enumerate(self.cur_proj.boards):
                dims = [str(i) for i in board.dims]
                dims = ','.join(dims)
                init_unit = [str(i) for i in board.init_unit]
                init_unit = ','.join(init_unit)
                end_unit = [str(i) for i in board.end_unit]
                end_unit = ','.join(end_unit)
                position = [str(i) for i in board.position]
                position = ','.join(position)
                print str(n).rjust(2),\
                    dims.rjust(10),\
                    init_unit.rjust(14),\
                    end_unit.rjust(14),\
                    position.rjust(14)        
            print '\n',\
                'id'.rjust(2),\
                'colors'.rjust(27),\
                'origin'.rjust(12),\
                'freq'.rjust(6),\
                'phase'.rjust(7)
            for n, board in enumerate(self.cur_proj.boards):
                cols = [str(tuple(c)).translate(None,' ') for c in board.cols]
                cols = ','.join(cols)
                print str(n).rjust(2),\
                    cols.rjust(27),\
                    board.origin.rjust(12),\
                    str(board.freq).rjust(6),\
                    str(board.phase).rjust(7)            

    def help_ls(self):
        print 'usage: ls {settings, boards}'
        print 'Lists project settings, checkerboards and their attributes.'
        print 'Providing no arguments results in everything being listed.'
        
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
    
parser = argparse.ArgumentParser(
    description='''Generate flashing checkerboard patterns for display
                   or export as a series of images, intended for use in
                   psychophysics experiments. Enters interactive command
                   line mode if no options are specified.''')

parser.add_argument('-c', '--cmd', dest='cmd_mode', action='store_true',
                    help='enter command line mode regardless of other options')
parser.add_argument('-d', '--disp', dest='display_flag', action='store_true',
                    help='displays the animation on the screen')
parser.add_argument('-e', '--export', dest='export_dir', metavar='dir',
                    help='export the animation to the specified directory')
parser.add_argument('--fmt', dest='export_fmt', choices=EXPORT_FMTS,
                    help='image format for animation to be exported as')
parser.add_argument('path', nargs='?',
                    help='checkergen project file to open')

args = parser.parse_args()

if args.export_dir != None:
    if not os.path.isdir(args.export_dir):
        sys.exit("error: export path is not a directory")
    args.export_flag = True
else:
    args.export_flag = False

if args.path != None:
    if not os.path.isfile(args.path):
        sys.exit("error: path specified is not a file")
    args.proj = CkgProj(path=args.path)
    os.chdir(os.path.dirname(os.path.abspath(args.path)))
else:
    args.proj = None

if not args.display_flag and not args.export_flag:
    args.cmd_mode = True
elif args.path == None:
    if not args.cmd_mode:
        sys.exit("error: no project file specified for display or export")
    else:
        print("error: no project file specified for display or export\n")

if args.display_flag:
    display_thread = threading.Thread(target=display_anim, 
                                      args=[copy.deepcopy(args.proj)])
    display_thread.start()
if args.export_flag:
    export_thread = threading.Thread(target=export_anim, 
                                     args=[copy.deepcopy(args.proj), 
                                           args.export_dir, 
                                           args.export_fmt])
    export_thread.start()
if args.cmd_mode:
    mycmd = CkgCmd()
    mycmd.cur_proj = args.proj
    mycmd.prompt = '(ckg) '
    mycmd.intro = textwrap.dedent('''\
                                  Enter 'help' for a list of commands.
                                  Enter 'quit' or Ctrl-D to exit.''')
    mycmd.cmdloop()
