#! /usr/bin/env python

"""Simple script to generate Python-compatible CRS header file.

Generate header file containing CRS Video Eyetracker Toolbox constants
dynamically to avoid copyright concerns. Prompts user for location of
crsLoadConstants.m, which is then transcribed to CRS.py, with the
unnecessary portions stripped.

CRS and Video Eyetracker Toolbox are trademarks of Cambridge Research Systems.

"""

import os
import sys

mfilename = 'crsLoadConstants.m'
pyfilename = 'CRS.py'
default_path = os.path.normpath('C:\Program Files\icannotremember')
sep1 = "\
% *************************************\
****************************************\n\
% Video Eye Tracker Toolbox constants *\
****************************************\n\
% *************************************\
****************************************"
sep2 = "\
% *************************************\
****************************************\n\
% * CONSTANTS DEFINED IN VSGV8.h ******\
****************************************\n\
% *************************************\
****************************************"

print 'path to crsLoadConstants.m: (default: {0})'.format(default_path)
path = raw_input()
if len(path) == 0:
    # Default to standard Windows install path
   path == default_path
else:
    path = os.path.normpath(path)
if not os.path.isfile(path):
    sys.exit("path specified is not a file")
elif os.path.basename(path) != mfilename:
    sys.exit("wrong filename, {0} expected".format(mfilename))

# U flag for standardized newlines
mfile = open(path, 'rU')
mstr = mfile.read()
mfile.close()

# Actual text processing
pystr = mstr.split(sep1)[1]
pystr = sep1 + pystr
pystr = pystr.split(sep2)[0]
pystr = pystr.replace('%', '#')
pystr = pystr.replace('CRS.', '')
pystr = pystr.replace(';', '')

# Write out to file
pyfile = open(pyfilename, 'w')
pyfile.write(pystr)
pyfile.close()

print 'Done.'
