import os, sys
import pygame
from pygame.locals import *

def checkerdraw(Surface, position, board_dims, init_cell_dims, end_cell_dims, cols):
    cur_cell_pos = list(position)
    cell_grad = [(end_cell_dims[x]-init_cell_dims[x])/board_dims[x] for x in range(2)]
    cur_cell_dims = [init_cell_dims[x]+cell_grad[x]/2 for x in range(2)]
    for j in range(board_dims[1]):
        for i in range(board_dims[0]):
            pygame.draw.rect(Surface, cols[(i+j)%2], tuple(cur_cell_pos + cur_cell_dims))
            #Increase x values
            cur_cell_pos[0] += cur_cell_dims[0]
            cur_cell_dims[0] += cell_grad[0]
        #Reset x values
        cur_cell_pos[0] = position[0]
        cur_cell_dims[0] = init_cell_dims[0]+cell_grad[0]/2
        #Increase y values
        cur_cell_pos[1] += cur_cell_dims[1]
        cur_cell_dims[1] += cell_grad[1]



pygame.init()

size = width, height = 800, 600
window = pygame.display.set_mode(size)
pygame.display.set_caption('checkergen')
screen = pygame.display.get_surface()
clock = pygame.time.Clock()

black = Color(0,0,0,0)
white = Color(255,255,255,255)

checkerdraw(screen, (width/4,height/4), (10,10), (10,10), (50,50), (black,white))

while True:
    clock.tick(60)
    for event in pygame.event.get():
        if event.type == QUIT:
            sys.exit(0)

    pygame.display.flip()
    
