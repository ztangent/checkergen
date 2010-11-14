import os, sys
import pygame
from pygame.locals import *

def checkerdraw(Surface, position, board_dims, cell_dims, cols):
    for i in [cell_dims[0]*x for x in range(board_dims[0])]:
        for j in [cell_dims[1]*x for x in range(board_dims[1])]:
            pygame.draw.rect(Surface, cols[(i+j)%2], (position[0]+i,position[1]+j) + cell_dims)

pygame.init()

size = width, height = 800, 600
window = pygame.display.set_mode(size)
pygame.display.set_caption('checkergen')
screen = pygame.display.get_surface()
clock = pygame.time.Clock()

black = Color(0,0,0,0)
white = Color(255,255,255,255)

checkerdraw(screen, (width/4,height/4), (width/50,height/50), (25,25), (black,white))

while True:
    clock.tick(60)
    for event in pygame.event.get():
        if event.type == QUIT:
            sys.exit(0)

    pygame.display.flip()
    
