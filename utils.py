"""Utility functions and classes."""

import os
import time
import re
import math
from decimal import *
from xml.dom import minidom

from pygame.locals import *

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
    """Tries to cast a string to a color (3-tuple)."""
    try:
        c = Color(s)
        c.set_length(3)
        c = tuple(c)
    except ValueError:
        c = tuple([int(x) for x in s.split(sep)])
    return c

# XML helper functions
# TODO: fix crashing on messed up namespace
def xml_get(parent, namespace, name):
    """Returns concatenated text node values inside an element."""
    element = parent.getElementsByTagNameNS(namespace, name)[0]
    strings = []
    for node in element.childNodes:
        if node.nodeType == node.TEXT_NODE:
            strings.append(node.data)
    return ''.join(strings)

def xml_set(document, parent, name, string):
    """Creates a DOM element with name and stores value as a text node."""
    element = document.createElement(name)
    parent.appendChild(element)
    text = document.createTextNode(string)
    element.appendChild(text)

def xml_pretty_print(document, indent):
    """Hack to prettify minidom's not so pretty print."""
    ugly_xml = document.toprettyxml(indent=indent)
    prettifier_re = re.compile('>\n\s+([^<>\s].*?)\n\s+</', re.DOTALL)    
    pretty_xml = prettifier_re.sub('>\g<1></', ugly_xml)
    return pretty_xml

class Timer:
    """High-res timer that should be cross-platform."""
    def __init__(self):
        if os.name == 'nt':
            time.clock()
        self.running = False
        
    def start(self):
        if os.name == 'nt':
            self.start_time = time.clock()
        elif os.name == 'posix':
            self.start_time = time.time()
        self.running = True

    def stop(self):
        if not self.running:
            return -1
        if os.name == 'nt':
            self.stop_time = time.clock()
        elif os.name == 'posix':
            self.stop_time = time.time()
        self.running = False
        return self.stop_time - self.start_time

    def elapsed(self):
        if not self.running:
            return -1
        if os.name == 'nt':
            cur_time = time.clock()
        elif os.name == 'posix':
            cur_time = time.time()
        return cur_time - self.start_time

    def tick(self, fps):
        """Limits loop to specified fps. To be placed at start of loop."""
        fps = float(fps)
        ret = self.elapsed()
        if self.elapsed() != -1:
            while self.elapsed() < (1.0 / fps):
                pass
        self.start()
        if ret != -1:
            return ret * 1000
