#! /usr/bin/env python

import os
import sys
import math
from decimal import *

import pygame
from pygame.locals import *

DEFAULT_FPS = 60

BLACK = Color(0,0,0)
GREY = Color(127,127,127)
WHITE = Color(255,255,255) 

CB_ORIGIN = {'topleft': (1, 1), 'topright': (-1, 1),
             'btmleft': (1, -1), 'btmright': (-1, -1),
             'topcenter': (0, 1), 'btmcenter': (0, -1),
             'centerleft': (1, 0), 'centerright': (-1, 0),
             'center': (0, 0)}

disp_anim = True
export_anim = False

export_count = 0
export_frames = 0
export_fmt = 'png'

global_fps = DEFAULT_FPS
bg_color = GREY
screen_size = screen_w, screen_h = 800, 600

def gcd(a, b):
    """Return greatest common divisor using Euclid's Algorithm."""
    while b > 0:      
        a, b = b, a % b
    return a

def lcm(a, b):
    """Return lowest common multiple."""
    return a * b // gcd(a, b)

def numdigits(x):
    """Returns number of digits in a decimal integer"""
    if x == 0:
        return 1
    elif x < 0:
        x = -x
    return int(math.log(x, 10)) + 1
    
class CheckerBoard:

    def __init__(self, dims, init_unit, end_unit, position, origin, 
                 cols, freq, phase=0):
        self.dims = tuple([int(x) for x in dims])
        self.init_unit = tuple([Decimal(str(x)) for x in init_unit])
        self.end_unit = tuple([Decimal(str(x)) for x in end_unit])
        self.position = tuple([Decimal(str(x)) for x in position])
        if isinstance(origin, str):
            self.origin = CB_ORIGIN[origin]
        else:
            self.origin = tuple(origin)
        self.cols = tuple(cols)
        self.freq = Decimal(str(freq))
        self.phase = Decimal(str(phase)) # In degrees
        self.unit_grad = tuple([(2 if (flag == 0) else 1) * 
                                (y2 - y1) / dx for y1, y2, dx, flag in 
                                zip(self.init_unit, self.end_unit, 
                                    self.dims, self.origin)])
        self.firstrun = True

    def draw(self, Surface, position=None):
        Surface.lock()
        if position == None:
            position = self.position
        else:
            position = tuple([Decimal(str(x)) for x in position])
        # Set initial values
        init_unit = [c + m/2 for c, m in zip(self.init_unit, self.unit_grad)]
        init_pos = list(position)
        for n, v in enumerate(self.origin):
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
                    if Decimal(i + 1) < (self.dims[0] / Decimal(2)):
                        cur_unit[0] -= self.unit_grad[0]
                    elif Decimal(i + 1) > (self.dims[0] / Decimal(2)):
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
                if Decimal(j + 1) < (self.dims[1] / Decimal(2)):
                    cur_unit[1] -= self.unit_grad[1]
                elif Decimal(j + 1) > (self.dims[1] / Decimal(2)):
                    cur_unit[1] += self.unit_grad[1]
                else:
                    pass
            else:
                cur_unit_pos[1] += self.origin[1]*cur_unit[1]
                cur_unit[1] += self.unit_grad[1]
        Surface.unlock()

    def anim(self, Surface, position=None, fps=None):
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
if disp_anim:
    screen = pygame.display.set_mode(screen_size)
    pygame.display.set_caption('checkergen')
else:
    screen = pygame.Surface(screen_size)

clock = pygame.time.Clock()

myboards = []

myboards.append(CheckerBoard((6, 6), (20, 20), (40, 40), 
                             (screen_w/2 - 20, screen_h/2 - 20),
                             'btmright', (BLACK, WHITE), 1))
myboards.append(CheckerBoard((6, 6), (20, 20), (40, 40), 
                             (screen_w/2 + 20, screen_h/2 - 20), 
                             'btmleft', (BLACK, WHITE), 2))
myboards.append(CheckerBoard((6, 6), (20, 20), (40, 40), 
                             (screen_w/2 - 20, screen_h/2 + 20), 
                             'topright', (BLACK, WHITE), 3))
myboards.append(CheckerBoard((6, 6), (20, 20), (40, 40), 
                             (screen_w/2 + 20, screen_h/2 + 20), 
                             'topleft', (BLACK, WHITE), 4))

screen.fill(bg_color)

if export_anim:
    fpps = [global_fps / board.freq for board in myboards if board.freq != 0]
    export_frames = reduce(lcm, fpps)

while (disp_anim or (export_anim and export_count < export_frames)):
    if disp_anim:
        clock.tick(global_fps)
    for event in pygame.event.get():
        if event.type == QUIT:
            disp_anim = False
    screen.lock()
    for board in myboards:
        board.anim(screen)
    screen.unlock()
    if disp_anim:
        pygame.display.flip()
    if export_anim and export_count < export_frames:
        pygame.image.save(screen,'anim{0}.{1}'.
                          format(repr(export_count).
                                 zfill(numdigits(export_frames-1)), export_fmt))
        export_count += 1
        if export_count == export_frames:
            print 'Export done.'
