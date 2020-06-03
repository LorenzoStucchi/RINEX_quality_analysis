# adapted from 
# https://github.com/rokubun/android_rinex/blob/master/andrnx/gnsslogger.py

import pandas as pd
import datetime
import numpy as np

import warnings
warnings.filterwarnings('ignore')

file_or = "data/SensorLog11_02.csv"
file_fix = "data/SensorLog11_fix.csv"
file_out = "data/raw_data_android.csv"

# Define constants
SPEED_OF_LIGHT = 299792458.0  # [m/s]
GPS_WEEKSECS = 604800  # Number of seconds in a week
NS_TO_S = 1.0e-9
# Origin of the GPS time scale
GPSTIME = datetime.datetime(1980, 1, 6)

# to do once to remove the data that are not raw measurement
def clean_data(file_start, file_end):
    data = ''
    with open(file_start) as hnd:
        for i, line in enumerate(hnd):
            if 'Raw' in line:
                data += line
    
    f = open(file_end, 'w')
    f.write(data)
    f.close()

clean_data(file_or, file_fix)

raw = pd.read_csv(file_fix)

# ONLY FOR GPS
# Keep only GPS satellite where ConstellationType=1 so Svid is the number of the satellite
CONSTELLATION_GPS = 1
sat_code = 'G'
raw_GPS = raw[ raw['ConstellationType'] == CONSTELLATION_GPS ]
raw_GPS['SatName'] = sat_code + raw_GPS.Svid.astype(str).str.zfill(2)

# Computation VALID ONLY FOR GPS
fullbiasnanos = raw_GPS['FullBiasNanos']
timenanos = np.floor(raw_GPS['TimeNanos'])
biasnanos = np.floor(raw_GPS['BiasNanos'])

# Compute the GPS week number and reception time (i.e. clock epoch)
gpsweek = np.floor(-fullbiasnanos * NS_TO_S / GPS_WEEKSECS)
local_est_GPS_time = timenanos - (fullbiasnanos + biasnanos)
gpssow = local_est_GPS_time * NS_TO_S - gpsweek * GPS_WEEKSECS

# Convert the epoch to datetime class
gpst_epoch = GPSTIME + pd.to_timedelta(gpsweek*7, 'd') + pd.to_timedelta(gpssow,'s')

# Compute the reception times
tRxSeconds = gpssow - np.floor(raw_GPS['TimeOffsetNanos']) * NS_TO_S

# Compute wavelength for metric conversion in cycles
wavelength = SPEED_OF_LIGHT / raw_GPS['CarrierFrequencyHz']
    
# Compute transmit time
tTxSeconds = raw_GPS['ReceivedSvTimeNanos'] * NS_TO_S

tau = tRxSeconds - tTxSeconds

if sum(tau > GPS_WEEKSECS / 2) > 0: # some values are over the week
    for index, row in tau.iterrows():
        if row > GPS_WEEKSECS / 2:
            del_sec = np.round(row/GPS_WEEKSECS)*GPS_WEEKSECS
            rho_sec = row - del_sec
            if rho_sec > 10:
                tau[index] = 0.0
            else:
                tau[index] = rho_sec
        
# Compute the travel time, which will be eventually the pseudorange
# Compute the range as the difference between the received time and the transmitted time
raw_GPS['pseudorange'] = tau*SPEED_OF_LIGHT
raw_GPS['cphase'] = raw_GPS['AccumulatedDeltaRangeMeters'] / wavelength
raw_GPS['doppler'] = - raw_GPS['PseudorangeRateMetersPerSecond'] / wavelength
raw_GPS['cn0'] = raw_GPS['Cn0DbHz']

# Creation of a csv similar to the RINEX result
data = pd.DataFrame()
data["GPST"]    = GPSTIME + pd.to_timedelta(gpsweek*7, 'd') + pd.to_timedelta(np.floor(gpssow),'s')
b = np.floor((gpssow - np.floor(gpssow))*10**9)
data["dec_sec"] = b.astype(int).astype(str).str.zfill(9)
data["satId"]   = raw_GPS['SatName']
data["psr_1"]   = raw_GPS['pseudorange']
data["phs_1"]   = raw_GPS['cphase']
data["dop_1"]   = raw_GPS['doppler']
data["snr_1"]   = raw_GPS['cn0']

data.to_csv(file_out)