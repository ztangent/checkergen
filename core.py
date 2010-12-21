"""Contains core functionality of checkergen.

Errors and Exceptions:
FileFormatError
FrameOverflowError

Classes:
CkgProj -- A checkergen project, contains settings and CheckerBoards.
CheckerBoard -- A (distorted) checkerboard pattern, can color-flip.

Functions:
display_anim -- Displays flashing checkerboard patterns on the screen.
export_anim -- Exports such patterns as an image sequence.

"""

import os
import sys
from xml.dom import minidom

import pygame
from pygame.locals import *

from utils import *

CKG_FMT = 'ckg'
XML_NAMESPACE = 'http://github.com/ZOMGxuan/checkergen'
DEFAULT_NAME = 'untitled'
DEFAULT_FPS = 60
DEFAULT_RES = 800, 600
DEFAULT_BG = (127, 127, 127)
EXPORT_FMTS = ['bmp', 'tga', 'jpg', 'png']
DEFAULT_EXPORT_FMT = 'png'
MAX_EXPORT_FRAMES = 10000

class FileFormatError(ValueError):
    """Raised when correct file format/extension is not supplied."""
    pass

class FrameOverflowError(Exception):
    """Raised when more than MAX_EXPORT_FRAMES are going to be exported."""
    pass
        
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
            value = eval(xml_get(project, XML_NAMESPACE, var))
            setattr(self, var, value)
        self.boards = []
        board_els = project.getElementsByTagNameNS(XML_NAMESPACE, 'board')
        board_args = ['dims', 'init_unit', 'end_unit', 'position',
                      'origin', 'cols', 'freq', 'phase']
        for board_el in board_els:
            board_dict = dict([(arg, eval(xml_get(board_el, 
                                                  XML_NAMESPACE, arg)))
                               for arg in board_args])
            new_board = CheckerBoard(**board_dict)
            self.boards.append(new_board)

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
            xml_set(doc, project, var, repr(getattr(self, var)))
        for board in self.boards:
            board_el = doc.createElement('board')
            project.appendChild(board_el)
            for var in ['dims', 'init_unit', 'end_unit', 'position',
                        'origin', 'cols', 'freq', 'phase']:
                xml_set(doc, board_el, var, repr(getattr(board, var)))

        with open(path, 'w') as project_file:
            project_file.write(xml_pretty_print(doc,indent='    '))

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
        if origin in self.__class__.locations and type(origin) == str:
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
        if not self._prerendered:
            self.prerender()

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
                               self.__class__.locations[self.origin])])

        # Set initial values
        init_pos = [to_decimal(0), to_decimal(0)]
        init_unit = [c + m/2 for c, m in zip(self.init_unit, unit_grad)]
        for n, v in enumerate(self.__class__.locations[self.origin]):
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
                for n, v in enumerate(self.__class__.locations[self.origin]):
                    if v < 0:
                        cur_unit_rect[n] -= cur_unit[n]                
                cur_unit_rect = [int(round(x)) for x in cur_unit_rect]
                prerenders[0].fill(self.cols[(i + j) % 2], 
                                       tuple(cur_unit_rect))
                prerenders[1].fill(self.cols[(i + j + 1) % 2], 
                                       tuple(cur_unit_rect))

                # Increase x values
                if self.__class__.locations[self.origin][0] == 0:
                    cur_unit_pos[0] += cur_unit[0]
                    if to_decimal(i + 1) < (self.dims[0] / to_decimal(2)):
                        cur_unit[0] -= unit_grad[0]
                    elif to_decimal(i + 1) > (self.dims[0] / to_decimal(2)):
                        cur_unit[0] += unit_grad[0]
                    else:
                        pass
                else:
                    cur_unit_pos[0] += \
                        self.__class__.locations[self.origin][0] * cur_unit[0]
                    cur_unit[0] += unit_grad[0]

            # Reset x values
            cur_unit_pos[0] = init_pos[0]
            cur_unit[0] = init_unit[0]

            # Increase y values
            if self.__class__.locations[self.origin][1] == 0:
                cur_unit_pos[1] += cur_unit[1]
                if to_decimal(j + 1) < (self.dims[1] / to_decimal(2)):
                    cur_unit[1] -= unit_grad[1]
                elif to_decimal(j + 1) > (self.dims[1] / to_decimal(2)):
                    cur_unit[1] += unit_grad[1]
                else:
                    pass
            else:
                cur_unit_pos[1] += \
                    self.__class__.locations[self.origin][1] * cur_unit[1]
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

def display_anim(proj, fullscreen=False, highrestime=True):
    pygame.display.init()
    if fullscreen:
        screen = pygame.display.set_mode(proj.res,
                                         FULLSCREEN | HWSURFACE | DOUBLEBUF)
    else:
        screen = pygame.display.set_mode(proj.res, DOUBLEBUF)
    screen.fill(proj.bg)
    pygame.display.set_caption('checkergen')
    if not highrestime:
        clock = pygame.time.Clock()
    else:
        clock = Timer()

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
        if not highrestime:
            pygame.time.wait(0)

def export_anim(proj, export_dir, export_fmt=None, folder=True, force=False):
    if not os.path.isdir(export_dir):
            msg = 'export path is not a directory'
            raise IOError(msg)
    if export_fmt == None:
        export_fmt = proj.export_fmt
    screen = pygame.Surface(proj.res)
    screen.fill(proj.bg)
    fpps = [proj.fps / board.freq for board in proj.boards if board.freq != 0]
    frames = reduce(lcm, fpps)
    count = 0

    if frames > MAX_EXPORT_FRAMES and not force:
        msg = 'large number ({0}) of frames to be exported'.\
            format(MAX_EXPORT_FRAMES)
        raise FrameOverflowError(msg)

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
