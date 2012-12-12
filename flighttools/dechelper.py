import re
import os
import sys
import numpy as np

import Ska
import Ska.engarchive.fetch_eng as fetch
import Chandra.Time as ct

class fetchobject(Ska.engarchive.fetch.Msid):
    def __init__(self, msid, times, vals, tstart, tstop, stat=None):
        self.times = times # This gets overwritten if stats are requested
        self.vals = vals
        self.MSID = 'DP_' + msid.upper()
        self.datestart = ct.DateTime(tstart).date
        self.datestop = ct.DateTime(tstop).date
        self.tstart = ct.DateTime(tstart).secs
        self.tstop = ct.DateTime(tstop).secs
        if stat:
            #import code
            #code.interact(local=locals())
            stats = getstats(self, stat)
            self.__dict__.update(stats)


def getstats(data, stat):

    tstart = data.times[0]
    tstop = data.times[-1]
    dt = np.diff(data.times)[0]

    if stat.lower() == '5min':
        pts = int(round(328 / dt))
    elif stat.lower() == 'daily':
        pts = int(round(86400 / dt))

    if stat:
        # Note this assumes no missing values...
        numintervals = int(len(data.times) / pts)

        timemat = np.reshape(data.times[:numintervals * pts], (numintervals, pts))
        valmat = np.reshape(data.vals[:numintervals * pts], (numintervals, pts))

        meantimes = np.mean(timemat, axis=1)
        meanvals = np.mean(valmat, axis=1)
        minvals = np.min(valmat, axis=1)       
        maxvals = np.max(valmat, axis=1)
        stds = np.std(valmat, axis=1)
        midvals = valmat[:, round(pts/2)]

        returndict = {'times':meantimes, 'means':meanvals, 'mins':minvals,
                      'maxes':maxvals, 'midvals':midvals, 'stds':stds}
        return returndict


def OBAHCHK(time1, time2, stat=None):

    msids = ['OOBTHR08', 'OOBTHR09', 'OOBTHR10', 'OOBTHR11', 'OOBTHR12', 
             'OOBTHR13', 'OOBTHR14', 'OOBTHR15', 'OOBTHR17', 'OOBTHR18', 
             'OOBTHR19', 'OOBTHR20', 'OOBTHR21', 'OOBTHR22', 'OOBTHR23', 
             'OOBTHR24', 'OOBTHR25', 'OOBTHR26', 'OOBTHR27', 'OOBTHR28', 
             'OOBTHR29', 'OOBTHR30', 'OOBTHR31', 'OOBTHR33', 'OOBTHR34', 
             'OOBTHR35', 'OOBTHR36', 'OOBTHR37', 'OOBTHR38', 'OOBTHR39', 
             'OOBTHR40', 'OOBTHR41', 'OOBTHR42', 'OOBTHR45', 'OOBTHR46']

    data = fetch.Msidset(msids, time1, time2)
    data.interpolate()

    maxes = data[msids[0]].vals
    mins = data[msids[0]].vals
    for name in data.keys():
        maxes = np.max((maxes, data[name].vals), axis=0)
        mins = np.min((mins, data[name].vals), axis=0)
        

    return fetchobject('OBAHCHK', data.times, maxes-mins, time1, time2, stat)


def HADG(time1, time2, stat=None):

    msids = ['OHRMGRD3', 'OHRMGRD6']

    data = fetch.Msidset(msids, time1, time2)
    data.interpolate()

    vals = np.max((data[msids[0]].vals, data[msids[1]].vals), axis=0)

    return fetchobject('HADG', data.times, vals, time1, time2, stat)


def POBA(time1, time2, stat=None):

    data = fetch.Msid('DP_POBAT', time1, time2)

    return fetchobject('POBA', data.times, data.vals, time1, time2, stat)



def PSUM(time1, time2, stat=None):

    data = fetch.Msid('DP_PABH', time1, time2)

    return fetchobject('PSUM', data.times, data.vals, time1, time2, stat)


def DUTYCYCLE(time1, time2, stat=None):

    msids = ['4OHTRZ53', '4OHTRZ54', '4OHTRZ55', '4OHTRZ57']

    data = fetch.Msidset(msids, time1, time2)
    data.interpolate()

    RTOTAL = 1./( 1/94.1 + 1/124.3 + 1/126.8 + 1/142.3)
    DC1 = np.abs(data['4OHTRZ53'].raw_vals)/94.1 + np.abs(data['4OHTRZ54'].raw_vals)/124.3
    DC2 = np.abs(data['4OHTRZ55'].raw_vals)/126.8 + np.abs(data['4OHTRZ57'].raw_vals)/142.3
    DUTYCYCLE = RTOTAL*(DC1+DC2)

    return fetchobject('DUTYCYCLE', data.times, DUTYCYCLE, time1, time2, stat)





    




    
