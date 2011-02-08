"""Provides support for CRS VideoEyetracker Toolbox."""

import win32com.client

# COM ProgID of the Toolbox
ProgID = "crsVET.VideoEyeTracker"
# VET application object
VET = None
# For easier access to constants and standardization with MATLAB interface
CRS = win32com.client.constants
# For internal usage
SCREEN_DIMS = []
SLOPPY_COUNT = 0

class EyetrackingError(Exception):
    """Raised when something goes wrong with VET."""

def init(user_select = False):
    global VET
    try:
        VET = win32com.client.Dispatch(ProgID)
    except:
        msg = 'could not start VideoEyetracker Toolbox'
        raise EyetrackingError(msg)
    if user_select:
        if not VET.SelectVideoSource(CRS.vsUserSelect, ''):
            msg = 'could not select video source'
            raise EyetrackingError(msg)
    else:
        # Default to 250 Hz High Speed Camera
        if not VET.SelectVideoSource(CRS.vsHighSpeedCamera250, ''):
            msg = 'could not select video source'
            raise EyetrackingError(msg)

def show_camera():
    VET.CreateCameraScreen(0)

def quit_camera():
    VET.DestroyCameraScreen()
    
def setup(viewing_distance, screen_dims,
          fixation_period = None, fixation_range = None):
    """Calibrates the display and sets fixation properties."""
    global SCREEN_DIMS
    if len(screen_dims) != 2:
        msg = 'screen_dims must be a 2-tuple'
        raise ValueError(msg)
    SCREEN_DIMS = screen_dims
    VET.SetDeviceParameters(CRS.deUser, viewing_distance,
                            screen_dims[0], screen_dims[1])
    if fixation_period != None:
        VET.FixationPeriod = fixation_period
    if fixation_range != None:
        VET.FixationRange = fixation_range

def calibrate():
    """Calibrate the subject."""
    VET.Calibrate()

def start():
    """Start tracking the eye."""
    VET.ClearDataBuffer()
    VET.StartTracking()

def stop():
    """Stop tracking the eye."""
    VET.StopTracking()

def sloppy_fixation(res, fps, fix_pos, fix_range, sloppy_dur):
    """Checks whether subject is fixating (with some leeway)."""
    global SLOPPY_COUNT
    if len(SCREEN_DIMS) == 0:
        msg = 'eyetracking not setup yet'
        raise EyetrackingError(msg)
    if not VET.CalibrationStatus()[0]:
        msg = 'subject not yet calibrated'
        raise EyetrackingError(msg)
    pix_per_mm = tuple([num_pix/num_mm for
                        num_pix, num_mm in zip(res, SCREEN_DIMS)])
    if VET.FixationLocation.Fixation:
        if (abs(VET.FixationLocation.Xposition *
                pix_per_mm[0]) <= fix_range[0]/2) and
           (abs(VET.FixationLocation.Yposition *
                pix_per_mm[1]) <= fix_range[1]/2):
            return True
    else:
        SLOPPY_COUNT += 1
    if SLOPPY_COUNT >= sloppy_dur * fps:
        SLOPPY_COUNT = 0
        return False
    else:
        return True
