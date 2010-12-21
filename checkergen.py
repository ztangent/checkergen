#! /usr/bin/env python

import os
import sys
import copy
import textwrap
import re
import readline
import argparse
import cmd
import shlex
import threading
import math
from decimal import *
from xml.dom import minidom

import pygame
from pygame.locals import *

CKG_FMT = 'ckg'
XML_NAMESPACE = 'http://github.com/ZOMGxuan/checkergen'
DEFAULT_NAME = 'untitled'
DEFAULT_FPS = 60
DEFAULT_RES = 800, 600
DEFAULT_BG = Color(127, 127, 127)
EXPORT_FMTS = ['bmp', 'tga', 'jpg', 'png']
DEFAULT_EXPORT_FMT = 'png'
MAX_EXPORT_FRAMES = 10000

class FileFormatError(Exception):
    """Raised when correct file format/extension is not supplied."""
    def __init__(self, msg):
        self.msg = msg
    def __str__(self):
        return self.msg

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
        raise ValueError(msg)

def to_decimal(s):
    """ValueError raising Decimal converter."""
    try:
        return Decimal(s)
    except InvalidOperation:
        try:
            return Decimal(str(s))
        except InvalidOperation:
            raise ValueError

def col_cast(s, sep=','):
    """Tries to cast a string to a Color."""
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

# Some XML helper functions
def getXMLval(parent, namespace, name):
    """Returns concatenated text node values inside an element."""
    element = parent.getElementsByTagNameNS(namespace, name)[0]
    textlist = []
    for node in element.childNodes:
        if node.nodeType == node.TEXT_NODE:
            textlist.append(node.data)
    return ''.join(textlist)

def setXMLval(document, parent, name, value):
    """Creates a DOM element with name and stores value as a text node."""
    element = document.createElement(name)
    parent.appendChild(element)
    text = document.createTextNode(value)
    element.appendChild(text)

def really_pretty_print(document, indent):
    """Hack to prettify minidom's not so pretty print."""
    ugly_xml = document.toprettyxml(indent=indent)
    prettifier_re = re.compile('>\n\s+([^<>\s].*?)\n\s+</', re.DOTALL)    
    pretty_xml = prettifier_re.sub('>\g<1></', ugly_xml)
    return pretty_xml

class CkgProj:
    """Defines a checkergen project, with checkerboards and other settings."""

    def __init__(self, name=DEFAULT_NAME, fps=DEFAULT_FPS, res=DEFAULT_RES, 
                 bg=DEFAULT_BG, export_fmt=DEFAULT_EXPORT_FMT, path=None):
        if path != None:
            self.load(path)
            return
        self.name = str(name)
        self.fps = to_decimal(fps)
        self.res = tuple([int(d) for d in res])
        self.bg = bg
        if export_fmt in EXPORT_FMTS:
            self.export_fmt = export_fmt
        else:
            msg = 'image format not recognized or supported'
            raise FileFormatError(msg)
        self.boards = []

    def __setattr__(self, name, value):
        self.__dict__[name] = value
        if name != 'dirty':
            self.dirty = True

    def load(self, path):
        name, ext = os.path.splitext(os.path.basename(path))
        if ext == '.{0}'.format(CKG_FMT):
            self.name = name
        else:
            msg = "path lacks '.{0}' extension".format(CKG_FMT)
            raise FileFormatError(msg)

        with open(path, 'r') as project_file:
            doc = minidom.parse(project_file)

        project = doc.documentElement
        for var in ['fps', 'res', 'bg', 'export_fmt']:
            value = eval(getXMLval(project, XML_NAMESPACE, var))
            setattr(self, var, value)
        self.bg = Color(*self.bg)
        board_nodes = project.getElementsByTagNameNS(XML_NAMESPACE, 'board')
        self.boards = []
        for node in board_nodes:
            dims = eval(getXMLval(node, XML_NAMESPACE, 'dims'))
            init_unit = eval(getXMLval(node, XML_NAMESPACE, 'init_unit'))
            end_unit = eval(getXMLval(node, XML_NAMESPACE, 'end_unit'))
            position = eval(getXMLval(node, XML_NAMESPACE, 'position'))
            origin = eval(getXMLval(node, XML_NAMESPACE, 'origin'))
            cols = eval(getXMLval(node, XML_NAMESPACE, 'cols'))
            cols = [Color(*col) for col in cols]
            freq = eval(getXMLval(node, XML_NAMESPACE, 'freq'))
            phase = eval(getXMLval(node, XML_NAMESPACE, 'phase'))
            newboard = CheckerBoard(dims=dims,
                                    init_unit=init_unit,
                                    end_unit=end_unit,
                                    position=position,
                                    origin=origin,
                                    cols=cols,
                                    freq=freq,
                                    phase=phase)
            self.boards.append(newboard)

        self.dirty = False

    def save(self, path):
        self.name, ext = os.path.splitext(os.path.basename(path))
        if ext != '.{0}'.format(CKG_FMT):
            path = '{0}.{1}'.format(path, CKG_FMT)

        impl = minidom.getDOMImplementation()
        doc = impl.createDocument(XML_NAMESPACE, 'project', None)
        project = doc.documentElement
        # Hack below because minidom doesn't support namespaces properly
        project.setAttribute('xmlns', XML_NAMESPACE)
        for var in ['fps', 'res', 'bg', 'export_fmt']:
            setXMLval(doc, project, var, repr(getattr(self, var)))
        for board in self.boards:
            board_el = doc.createElement('board')
            project.appendChild(board_el)
            for var in ['dims', 'init_unit', 'end_unit', 'position',
                        'origin', 'cols', 'freq', 'phase']:
                setXMLval(doc, board_el, var, repr(getattr(board, var)))

        with open(path, 'w') as project_file:
            project_file.write(really_pretty_print(doc,indent='    '))

        self.dirty = False

        return path
        
class CheckerBoard:

    locations = {'topleft': (1, 1), 'topright': (-1, 1),
                 'bottomleft': (1, -1), 'bottomright': (-1, -1),
                 'midtop': (0, 1), 'midbottom': (0, -1),
                 'midleft': (1, 0), 'midright': (-1, 0),
                 'center': (0, 0)}

    def __init__(self, dims, init_unit, end_unit, position, origin, 
                 cols, freq, phase=0):
        self.dims = tuple([int(x) for x in dims])
        self.init_unit = tuple([to_decimal(x) for x in init_unit])
        self.end_unit = tuple([to_decimal(x) for x in end_unit])
        self.position = tuple([to_decimal(x) for x in position])
        if origin in CheckerBoard.locations and type(origin) == str:
            self.origin = origin
        else:
            raise TypeError
        self.cols = tuple(cols)
        self.freq = to_decimal(freq)
        self.phase = to_decimal(phase)
        self.reset()

    def __setattr__(self, name, value):
        self.__dict__[name] = value
        if name in ['dims', 'init_unit', 'end_unit', 'origin','cols']:
            self._prerendered = False

    def reset(self, new_phase=None):
        if new_phase == None:
            new_phase = self.phase
        self._cur_phase = new_phase
        self._prev_phase = new_phase
        self._first_draw = True

    def update(self, fps=DEFAULT_FPS):
        self._prev_phase = self._cur_phase
        if self.freq != 0:
            fpp = fps / self.freq
            self._cur_phase += 360 / fpp
            if self._cur_phase >= 360:
                self._cur_phase %= 360

    def prerender(self):
        """Prerenders the checkerboards for quick blitting later."""
        # Set up prerender surfaces
        self._size = tuple([(y1 + y2) / 2 * n for y1, y2, n in
                            zip(self.init_unit, self.end_unit, self.dims)])
        prerenders = [pygame.Surface(self._size) for i in range(2)]

        # Compute unit size gradient
        unit_grad = tuple([(2 if (flag == 0) else 1) * 
                           (y2 - y1) / n for y1, y2, n, flag in 
                           zip(self.init_unit, self.end_unit, self.dims,
                               CheckerBoard.locations[self.origin])])

        # Set initial values
        init_pos = [to_decimal(0), to_decimal(0)]
        init_unit = [c + m/2 for c, m in zip(self.init_unit, unit_grad)]
        for n, v in enumerate(CheckerBoard.locations[self.origin]):
            if v == 0:
                init_unit[n] = self.end_unit[n] - (unit_grad[n] / 2)
            elif v < 0:
                init_pos[n] = self._size[n]
        cur_unit = list(init_unit)
        cur_unit_pos = list(init_pos)

        for prerender in prerenders:
            prerender.lock()

        # Draw unit cells in nested for loop
        for j in range(self.dims[1]):
            for i in range(self.dims[0]):
                cur_unit_rect = cur_unit_pos + cur_unit

                # Ensure unit cells are drawn in the right place
                for n, v in enumerate(CheckerBoard.locations[self.origin]):
                    if v < 0:
                        cur_unit_rect[n] -= cur_unit[n]                
                cur_unit_rect = [int(round(x)) for x in cur_unit_rect]
                prerenders[0].fill(self.cols[(i + j) % 2], 
                                       tuple(cur_unit_rect))
                prerenders[1].fill(self.cols[(i + j + 1) % 2], 
                                       tuple(cur_unit_rect))

                # Increase x values
                if CheckerBoard.locations[self.origin][0] == 0:
                    cur_unit_pos[0] += cur_unit[0]
                    if to_decimal(i + 1) < (self.dims[0] / to_decimal(2)):
                        cur_unit[0] -= unit_grad[0]
                    elif to_decimal(i + 1) > (self.dims[0] / to_decimal(2)):
                        cur_unit[0] += unit_grad[0]
                    else:
                        pass
                else:
                    cur_unit_pos[0] += CheckerBoard.locations[self.origin][0]*\
                                       cur_unit[0]
                    cur_unit[0] += unit_grad[0]

            # Reset x values
            cur_unit_pos[0] = init_pos[0]
            cur_unit[0] = init_unit[0]

            # Increase y values
            if CheckerBoard.locations[self.origin][1] == 0:
                cur_unit_pos[1] += cur_unit[1]
                if to_decimal(j + 1) < (self.dims[1] / to_decimal(2)):
                    cur_unit[1] -= unit_grad[1]
                elif to_decimal(j + 1) > (self.dims[1] / to_decimal(2)):
                    cur_unit[1] += unit_grad[1]
                else:
                    pass
            else:
                cur_unit_pos[1] += CheckerBoard.locations[self.origin][1]*\
                                   cur_unit[1]
                cur_unit[1] += unit_grad[1]

        for prerender in prerenders:
            prerender.unlock()

        self._prerenders = tuple(prerenders)
        self._prerendered = True

    def draw(self, Surface, position=None, always_redraw=False):
        """Draws appropriate prerender depending on current phase."""
        if not self._prerendered or always_redraw:
            self.prerender()
        if position == None:
            position = self.position
        dest = pygame.Rect((0, 0), self._size)
        setattr(dest, self.origin, position)
        self._cur_phase %= 360
        if 0 <= self._cur_phase < 180:
            Surface.blit(self._prerenders[0], dest)
        elif 180 <= self._cur_phase < 360:
            Surface.blit(self._prerenders[1], dest)

    def lazydraw(self, Surface, position=None):
        """Only draws on color reversal."""
        if ((180 <= self._cur_phase < 360 and 0 <= self._prev_phase < 180) or 
            (0 <= self._cur_phase < 180 and 180 <= self._prev_phase < 360) or
            self._first_draw):
            self.draw(Surface, position)
        if self._first_draw:
            self._first_draw = False

def display_anim(proj, fullscreen=False):
    pygame.display.init()
    if fullscreen:
        screen = pygame.display.set_mode(proj.res,
                                         FULLSCREEN | HWSURFACE | DOUBLEBUF)
    else:
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
                pygame.display.quit()
                return
            if event.type == KEYDOWN:
                if event.key == K_ESCAPE:
                    pygame.display.quit()
                    return
        for board in proj.boards:
            board.lazydraw(screen)
            board.update(proj.fps)
        pygame.display.flip()
        pygame.time.wait(0)

def export_anim(proj, export_dir, export_fmt=None, folder=True, cmd_mode=True):
    if not os.path.isdir(export_dir):
        if cmd_mode:
            print "error: export path is not a directory"
        return
    if cmd_mode:
        print "Exporting..."
    if export_fmt == None:
        export_fmt = proj.export_fmt
    pygame.display.init()
    screen = pygame.Surface(proj.res)
    screen.fill(proj.bg)
    fpps = [proj.fps / board.freq for board in proj.boards if board.freq != 0]
    frames = reduce(lcm, fpps)
    count = 0

    if frames > MAX_EXPORT_FRAMES:
        if not cmd_mode:
            pygame.display.quit()
            return
        else:
            print "More than", MAX_EXPORT_FRAMES, "are going to be exported."
            print "Are you sure you want to continue? (y/n)"
            if not yn_parser(raw_input()):
                print "Export cancelled."
                pygame.display.quit()
                return
            
    if folder:
        export_dir = os.path.join(export_dir, proj.name)
        if not os.path.isdir(export_dir):
            os.mkdir(export_dir)

    for board in proj.boards:
        board.reset()

    while count < frames:
        for board in proj.boards:
            board.lazydraw(screen)
            board.update(proj.fps)
        savepath = os.path.join(export_dir, 
                                '{0}{2}.{1}'.
                                format(proj.name, export_fmt,
                                       repr(count).zfill(numdigits(frames-1))))
        pygame.image.save(screen, savepath)
        count += 1
    if cmd_mode:
        print "Export done."
        pygame.display.quit()

class CmdParserError(Exception):
    """To be raised when CmdParser encounters an error."""
    def __init__(self, msg):
        self.msg = msg
    def __str__(self):
            return self.msg

class CmdParser(argparse.ArgumentParser):
    """Override ArgumentParser so that it doesn't exit."""
    def error(self, msg):
        raise CmdParserError(msg)
        
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
        try:
            self.cur_proj = CkgProj(path=path)
        except FileFormatError:
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
            path = os.path.join(path, '.'.join([self.cur_proj.name, CKG_FMT]))
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
    set_parser.add_argument('--bg', metavar='COLOR', type=col_cast,
                            help='''background color of the canvas
                                    (color format: R,G,B or name, 
                                    component range from 0-255)''')
    set_parser.add_argument('--fmt', dest='export_fmt', choices=EXPORT_FMTS,
                            help='''image format for animation
                                    to be exported as''')

    def help_set(self):
        CkgCmd.set_parser.print_help()

    def do_set(self, line):
        if self.cur_proj == None:
            print 'no project open, automatically creating project...'
            self.do_new('')
        try:
            args = CkgCmd.set_parser.parse_args(shlex.split(line))
        except CmdParserError:
            print "error:", str(sys.exc_value)
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
            print "no options specified, please specify at least one"
            CkgCmd.set_parser.print_usage()

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
    mk_parser.add_argument('origin', choices=CheckerBoard.locations,
                           help='''location of origin point of checkerboard
                                   (choices: %(choices)s)''',
                           metavar='origin')
    mk_parser.add_argument('cols', action=store_tuple(2, ',', col_cast, [';']),
                           help='''color1,color2 of the checkerboard
                                   (color format: R;G;B or name, 
                                   component range from 0-255)''')
    mk_parser.add_argument('freq', type=to_decimal,
                           help='frequency of color reversal in Hz')
    mk_parser.add_argument('phase', type=to_decimal, nargs='?', default='0',
                           help='initial phase of animation in degrees')

    def help_mk(self):
        CkgCmd.mk_parser.print_help()

    def do_mk(self, line):
        """Makes a checkerboard with the given parameters."""
        if self.cur_proj == None:
            print 'no project open, automatically creating project...'
            self.do_new('')
        try:
            args = CkgCmd.mk_parser.parse_args(shlex.split(line))
        except CmdParserError:
            print "error:", str(sys.exc_value)
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
    ed_parser.add_argument('--origin', choices=CheckerBoard.locations,
                           help='''location of origin point of checkerboard
                                   (choices: %(choices)s)''',
                           metavar='LOCATION')
    ed_parser.add_argument('--cols', metavar='COLOR1,COLOR2',
                           action=store_tuple(2, ',', col_cast, [';']),
                           help='''checkerboard colors (color format:
                                   R;G;B or name, component range 
                                   from 0-255)''')
    ed_parser.add_argument('--freq', type=to_decimal,
                           help='frequency of color reversal in Hz')
    ed_parser.add_argument('--phase', type=to_decimal,
                           help='initial phase of animation in degrees')

    def help_ed(self):
        CkgCmd.ed_parser.print_help()

    def do_ed(self, line):
        """Edits attributes of checkerboards specified by ids."""
        if self.cur_proj == None:
            print 'please create or open a project first'
            return
        try:
            args = CkgCmd.ed_parser.parse_args(shlex.split(line))
        except CmdParserError:
            print "error:", str(sys.exc_value)
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
                    setattr(self.cur_proj.boards[x], name, val)
                noflags = False
        if noflags:
            print "no options specified, please specify at least one"
            CkgCmd.ed_parser.print_usage()
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
        CkgCmd.rm_parser.print_help()

    def do_rm(self, line):
        """Removes checkerboards specified by ids"""
        if self.cur_proj == None:
            print 'please create or open a project first'
            return
        try:
            args = CkgCmd.rm_parser.parse_args(shlex.split(line))
        except CmdParserError:
            print "error:", str(sys.exc_value)
            CkgCmd.rm_parser.print_usage()
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
        CkgCmd.ls_parser.print_help()

    def do_ls(self, line):
        """Lists project settings, checkerboards and their attributes."""

        def ls_str(s, sep=','):
            """Special space-saving output formatter."""
            if type(s) in [tuple, list]:
                return sep.join([ls_str(i) for i in s])
            elif type(s) == pygame.Color:
                return str((s.r, s.b, s.g)).translate(None,' ')
            else:
                return str(s)

        if self.cur_proj == None:
            print 'please create or open a project first'
            return
        try:
            args = CkgCmd.ls_parser.parse_args(shlex.split(line))
        except CmdParserError:
            print "error:", str(sys.exc_value)
            CkgCmd.ls_parser.print_usage()
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
                'origin'.rjust(12),\
                'freq'.rjust(6),\
                'phase'.rjust(7)
            for n, board in zip(args.idlist, self.cur_proj.boards):
                print \
                    ls_str(n).rjust(2),\
                    ls_str(board.cols).rjust(27),\
                    ls_str(board.origin).rjust(12),\
                    ls_str(board.freq).rjust(6),\
                    ls_str(board.phase).rjust(7)            

    display_parser = CmdParser(add_help=False, prog='display',
                               description='''Displays the animation in a
                                              window or in fullscreen.''')
    display_parser.add_argument('-f', '--fullscreen', action='store_true',
                                help='sets fullscreen mode, ESC to quit')

    def help_display(self):
        CkgCmd.display_parser.print_help()

    def do_display(self, line):
        """Displays the animation in window or in fullscreen"""
        if self.cur_proj == None:
            print 'please create or open a project first'
            return
        try:
            args = CkgCmd.display_parser.parse_args(shlex.split(line))
        except CmdParserError:
            print "error:", str(sys.exc_value)
            CkgCmd.display_parser.print_usage()
            return
        display_anim(self.cur_proj, args.fullscreen)
        # pygame rendering within a thread is broken, comment out for now
        ## for thread in threading.enumerate():
        ##     if thread.name == 'display_thread':
        ##         print 'error: animation is already being displayed'
        ##         return
        ## else:
        ##     threading.Thread(target=display_anim, name='display_thread',
        ##                      args=[copy.deepcopy(self.cur_proj),
        ##                            args.fullscreen]).start()

    export_parser = CmdParser(add_help=False, prog='export',
                              description='''Exports animation as an image
                                             sequence (in a folder) to the
                                             specified directory.''')
    export_parser.add_argument('dir', nargs='?', default=os.getcwd(),
                               help='''destination directory for export
                                       (default: current working directory)''')
    export_parser.add_argument('--fmt', dest='export_fmt', choices=EXPORT_FMTS,
                               help='image format for export')
    export_parser.add_argument('-n','--nofolder', action='store_false',
                               help='''force images not to exported in 
                                       a containing folder''')


    def help_export(self):
        CkgCmd.export_parser.print_help()

    def do_export(self, line):
        """Exports animation an image sequence to the specified directory."""
        if self.cur_proj == None:
            print 'please create or open a project first'
            return
        try:
            args = CkgCmd.export_parser.parse_args(shlex.split(line))
        except CmdParserError:
            print "error:", str(sys.exc_value)
            CkgCmd.export_parser.print_usage()
            return
        export_anim(self.cur_proj, args.dir, args.export_fmt, args.nofolder)

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
parser.add_argument('-d', '--display',
                    dest='display_flag', action='store_true',
                    help='displays the animation on the screen')
parser.add_argument('-e', '--export', dest='export_dir', metavar='dir',
                    help='export the animation to the specified directory')
parser.add_argument('-f', '--fullscreen', action='store_true',
                    help='animation displayed in fullscreen mode')
parser.add_argument('--fmt', dest='export_fmt', choices=EXPORT_FMTS,
                    help='image format for animation to be exported as')
parser.add_argument('path', nargs='?', type=file,
                    help='checkergen project file to open')

args = parser.parse_args()

if args.export_dir != None:
    print args.export_dir
    args.export_flag = True
else:
    args.export_flag = False

if not args.display_flag and not args.export_flag:
    args.cmd_mode = True

if args.path != None:
    if not os.path.isfile(args.path):
        sys.exit("error: path specified is not a file")
    args.proj = CkgProj(path=args.path)
    os.chdir(os.path.dirname(os.path.abspath(args.path)))
else:
    args.proj = None
    if args.display_flag or args.export_flag:
        print "error: no project file specified for display or export"
        if not args.cmd_mode:
            sys.exit(1)

if args.display_flag:
    display_thread = threading.Thread(target=display_anim,
                                      name='display_thread',
                                      args=[copy.deepcopy(args.proj), 
                                            args.fullscreen])
    display_thread.start()
if args.export_flag:
    export_anim(copy.deepcopy(args.proj), args.export_dir, args.export_fmt)
if args.cmd_mode:
    mycmd = CkgCmd()
    mycmd.cur_proj = args.proj
    mycmd.prompt = '(ckg) '
    mycmd.intro = textwrap.dedent('''\
                                  Enter 'help' for a list of commands.
                                  Enter 'quit' or Ctrl-D to exit.''')
    mycmd.cmdloop()
