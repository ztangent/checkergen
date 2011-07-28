"""Provides support for CRS VideoEyetracker Toolbox."""

import os.path

from utils import *

FIX_POS = (0, 0)
FIX_RANGE = (20, 20)
PERIOD = 300

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
    
    data = None
    last_status = -1
    new_status = -1
    count = 0

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
        global data
        global last_status
        global new_status
        global count
        if not is_source_ready():
            select_source()
        if not is_calibrated():
            msg = 'subject not yet calibrated'
            raise EyetrackingError(msg)
        data = None
        last_status = -1
        new_status = -1
        count = 0
        VET.ClearDataBuffer()
        VET.StartTracking()

    def stop():
        """Stop tracking the eye."""
        VET.StopTracking()

    def poll_tracker():
        """Poll tracker for tracking information."""
        global data
        data = VET.GetLatestEyePosition(DummyResultSet)[1]        

    def get_status(fps, period=PERIOD,
                        fix_pos=FIX_POS,
                        fix_range=FIX_RANGE):
        """Returns fixation/tracking status.
        -1 for untracked, 0 for unfixated, 1 for fixated.

        fps -- frames per second at which stimulus is running

        period -- duration in milliseconds during which eye has to
        maintain the same status in order for value returned
        by this function to change

        fix_pos -- (x, y) position of desired fixation location in mm
        from center of screen

        fix_range -- (width, height) of box surrounding fix_pos within
        which fixation is allowed (in mm)

        """
        global last_status
        global new_status
        global count
        pos = (data.ScreenPositionXmm, data.ScreenPositionYmm)
        diff = [abs(p - fp) for p, fp in zip(pos, fix_pos)]
        if data.Tracked == True:
            if diff[0] < fix_range[0] and diff[1] < fix_range[1]:
                cur_status = 1
            else:
                cur_status = 0
        else:
            cur_status = -1
        if cur_status == new_status:
            count += 1
        else:
            count = 0
        if cur_status != last_status:
            new_status = cur_status
        if count >= period / to_decimal(1000) * fps:
            count = 0
            last_status = new_status
        return last_status

    def x_pos():
        if data.Tracked:
            return float(data.ScreenPositionXmm)
        else:
            return ''
        
    def y_pos():
        if data.Tracked:
            return float(data.ScreenPositionYmm)
        else:
            return ''
