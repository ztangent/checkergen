"""Provides support for CRS VideoEyetracker Toolbox."""

import os.path

from utils import *

FIX_POS = (0, 0)
FIX_RANGE = (20, 20)
FIX_PER = 300
TRACK_PER = 300

try:
    import win32com.client
    available = True
except ImportError:
    available = False

# COM ProgID of the Toolbox
ProgID = "crsVET.VideoEyeTracker"
RecordName = "etResultSet"
# VET application object
VET = None

class EyetrackingError(Exception):
    """Raised when something goes wrong with VET."""
    pass

if available:
    # Try dispatching object, else unavailable
    try:
        from win32com.client import gencache
        # Ensure makepy module is generated
        gencache.EnsureModule('{248DBF0C-A874-4032-82CE-DC5B307BB6E7}',
                              0, 3, 11)
        VET = win32com.client.Dispatch(ProgID)
        DummyResultSet = win32com.client.Record(RecordName, VET)
    except:
        available = False

if available:

    # For easier access to constants and standardization with MATLAB interface
    CRS = win32com.client.constants
    
    lastfixstatus = False
    fixcount = 0
    lasttrackstatus = False
    trackcount = 0

    def select_source(user_select = False, path = None):
        if user_select:
            if not VET.SelectVideoSource(CRS.vsUserSelect, ''):
                msg = 'could not select video source'
                raise EyetrackingError(msg)
        elif path != None:
            # Open from file
            if not VET.SelectVideoSource(CRS.vsFile, path):
                msg = 'could not use path as video source'
                raise EyetrackingError(msg)            
        else:
            # Default to 250 Hz High Speed Camera
            if not VET.SelectVideoSource(CRS.vsHighSpeedCamera250, ''):
                msg = 'could not select video source'
                raise EyetrackingError(msg)

    def is_source_ready():
        """Returns true if a video source has been selected."""
        if VET.VideoSourceType == 0:
            return False
        else:
            return True

    def show_camera():
        VET.CreateCameraScreen(0)

    def quit_camera():
        VET.DestroyCameraScreen()
        
    def setup(viewing_distance=None, screen_dims=None,
              fixation_period=None, fixation_range=None):
        """Calibrates the display and sets fixation properties."""
        if viewing_distance != None and screen_dims != None:
            if len(screen_dims) != 2:
                msg = 'screen_dims must be a 2-tuple'
                raise ValueError(msg)
            VET.SetDeviceParameters(CRS.deUser, viewing_distance,
                                    screen_dims[0], screen_dims[1])
        if fixation_period != None:
            VET.FixationPeriod = fixation_period
        if fixation_range != None:
            VET.FixationRange = fixation_range

    def calibrate(path = None):
        """Calibrate the subject.
           Optionally supply a path with no spaces to a 
           calibration file to load."""
        if not is_source_ready():
            select_source()
        if not VET.Tracking:
            VET.ClearDataBuffer()
            VET.StartTracking()
        if path == None:
            if not VET.Calibrate():
                msg = 'calibration failed'
                raise EyetrackingError(msg)
        else:
            if not os.path.isfile(path):
                msg = 'specified file does not exist'
                raise EyetrackingError(msg)
            if not VET.LoadCalibrationFile(path):
                msg = 'file could not be loaded'
                raise EyetrackingError(msg)
        if not is_calibrated():
            msg = 'calibration failed'
            raise EyetrackingError(msg)
 
    def is_calibrated():
        if VET.CalibrationStatus()[0] != 0:
            return True
        else:
            return False

    def start():
        """Start tracking the eye."""
        if not is_source_ready():
            select_source()
        if not is_calibrated():
            msg = 'subject not yet calibrated'
            raise EyetrackingError(msg)
        VET.ClearDataBuffer()
        VET.StartTracking()

    def stop():
        """Stop tracking the eye."""
        VET.StopTracking()

    def is_tracked(fps, track_period=TRACK_PER):
        """Returns true if the eye is being tracked.

        fps -- frames per second at which stimulus is running

        track_period -- duration in milliseconds during which eye has to
        be consistently tracked or untracked in order for value returned
        by this function to change

        """
        global lasttrackstatus
        global trackcount
        data = VET.GetLatestEyePosition(DummyResultSet)[1]
        if data.Tracked != lasttrackstatus:
            trackcount += 1
        else:
            trackcount = 0
        if trackcount >= track_period / to_decimal(1000) * fps:
            trackcount = 0
            lasttrackstatus = data.Tracked
        return lasttrackstatus

    def is_fixated(fps, fix_pos=FIX_POS,
                        fix_range=FIX_RANGE,
                        fix_period=FIX_PER):
        """Checks whether subject is fixating on specified location.

        fps -- frames per second at which stimulus is running

        fix_pos -- (x, y) position of desired fixation location in mm
        from center of screen

        fix_range -- (width, height) of box surrounding fix_pos within
        which fixation is allowed (in mm)

        fix_period -- duration in milliseconds during which eye has to
        be consistently fixated or not fixated in order for value returned
        by this function to change

        """
        global lastfixstatus
        global fixcount
        data = VET.GetLatestEyePosition(DummyResultSet)[1]
        pos = (data.ScreenPositionXmm, data.ScreenPositionYmm)
        diff = [abs(p - fp) for p, fp in zip(pos, fix_pos)]
        curfixstatus = False
        if data.Tracked == True:
            if diff[0] < fix_range[0] and diff[1] < fix_range[1]:
                curfixstatus = True
        if curfixstatus != lastfixstatus:
            fixcount += 1
        else:
            fixcount = 0
        if fixcount >= fix_period / to_decimal(1000) * fps:
            fixcount = 0
            lastfixstatus = curfixstatus
        return lastfixstatus
