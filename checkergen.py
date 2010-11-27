import os
import sys
import pygame
from pygame.locals import *

# Todo: may want to consider switching to Decimal from float

DEFAULT_FPS = 60

BLACK = Color(0,0,0)
GREY = Color(127,127,127)
WHITE = Color(255,255,255) 

CB_ORIGIN = {'topleft': (1, 1), 'topright': (-1, 1),
             'btmleft': (1, -1), 'btmright': (-1, -1),
             'topcenter': (0, 1), 'btmcenter': (0, -1),
             'centerleft': (1, 0), 'centerright': (-1, 0),
             'center': (0, 0)}

global_fps = DEFAULT_FPS
bgcolor = GREY

class CheckerBoard:

    def __init__(self, dims, init_unit, end_unit, position, origin, 
                 cols, freq, phase = 0):
        self.dims = tuple([int(x) for x in dims])
        self.init_unit = tuple([float(x) for x in init_unit])
        self.end_unit = tuple([float (x) for x in end_unit])
        self.position = tuple([float(x) for x in position])
        if isinstance(origin, str):
            self.origin = CB_ORIGIN[origin]
        else:
            self.origin = tuple(origin)
        self.cols = tuple(cols)
        self.freq = float(freq)
        self.phase = float(phase) # In degrees
        self.unit_grad = tuple([(2.0 if (flag == 0) else 1.0) * 
                                (y2 - y1) / dx for y1, y2, dx, flag in 
                                zip(self.init_unit, self.end_unit, 
                                    self.dims, self.origin)])
        self.firstrun = True

    def draw(self, Surface, position = None):
        if position == None:
            position = self.position
        else:
            position = tuple([float(x) for x in position])
        # Set initial values
        init_unit = [c + m/2 for c, m in zip(self.init_unit, self.unit_grad)]
        init_pos = list(position)
        for n, v in enumerate(self.origin):
            if v == 0:
                init_unit[n] = self.end_unit[n] - (self.unit_grad[n] / 2)
                init_pos[n] -= ((self.init_unit[n] + self.end_unit[n]) / 2 *
                                self.dims[n] / 2.0)
        cur_unit = list(init_unit)
        cur_unit_pos = list(init_pos)
        # Draw unit cells in nested for loop
        for j in range(self.dims[1]):
            for i in range(self.dims[0]):
                cur_unit_rect = cur_unit_pos + cur_unit
                # Ensure unit cells are drawn in the right place
                for n, v in enumerate(self.origin):
                    if v < 0:
                        cur_unit_rect[n] -= cur_unit[n]                
                cur_unit_rect = [int(round(x)) for x in cur_unit_rect]
                if 180 <= self.phase < 360:
                    cur_cols = list(reversed(self.cols)) 
                else:
                    cur_cols = list(self.cols)
                Surface.fill(cur_cols[(i + j) % 2], tuple(cur_unit_rect))
                # Increase x values
                if self.origin[0] == 0:
                    cur_unit_pos[0] += cur_unit[0]
                    if float(i + 1) < (self.dims[0] / 2.0):
                        cur_unit[0] -= self.unit_grad[0]
                    elif float(i + 1) > (self.dims[0] / 2.0):
                        cur_unit[0] += self.unit_grad[0]
                    else:
                        pass
                else:
                    cur_unit_pos[0] += self.origin[0]*cur_unit[0]
                    cur_unit[0] += self.unit_grad[0]
            # Reset x values
            cur_unit_pos[0] = init_pos[0]
            cur_unit[0] = init_unit[0]
            # Increase y values
            if self.origin[1] == 0:
                cur_unit_pos[1] += cur_unit[1]
                if float(j + 1) < (self.dims[1] / 2.0):
                    cur_unit[1] -= self.unit_grad[1]
                elif float(j + 1) > (self.dims[1] / 2.0):
                    cur_unit[1] += self.unit_grad[1]
                else:
                    pass
            else:
                cur_unit_pos[1] += self.origin[1]*cur_unit[1]
                cur_unit[1] += self.unit_grad[1]

    def anim(self, Surface, position = None, fps = None):
        if fps == None:
            fps = global_fps
        if self.freq != 0:
            fpp = fps / self.freq
            if self.firstrun == True:
                self.firstrun = False
            else:
                self.phase += 360 / fpp
                if self.phase >= 360:
                    self.phase -= 360
        self.draw(Surface, position)

pygame.init()

size = width, height = 800, 600
window = pygame.display.set_mode(size)
pygame.display.set_caption('checkergen')
screen = pygame.display.get_surface()

clock = pygame.time.Clock()

myboards = []

myboards.append(CheckerBoard((6, 6), (20, 20), (40, 40), 
                             (width/2 - 20, height/2 - 20),
                             'btmright', (BLACK, WHITE), 1))
myboards.append(CheckerBoard((6, 6), (20, 20), (40, 40), 
                             (width/2 + 20, height/2 - 20), 
                             'btmleft', (BLACK, WHITE), 2))
myboards.append(CheckerBoard((6, 6), (20, 20), (40, 40), 
                             (width/2 - 20, height/2 + 20), 
                             'topright', (BLACK, WHITE), 3))
myboards.append(CheckerBoard((6, 6), (20, 20), (40, 40), 
                             (width/2 + 20, height/2 + 20), 
                             'topleft', (BLACK, WHITE), 4))

screen.fill(bgcolor)

while True:
    clock.tick(global_fps)
    for board in myboards:
        board.anim(screen)
    for event in pygame.event.get():
        if event.type == QUIT:
            sys.exit(0)
    pygame.display.flip()
