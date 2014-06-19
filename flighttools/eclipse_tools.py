
import numpy as np
import re

import Ska.engarchive.fetch_eng as fetch_eng
import Chandra.Time as ct


def readEclipseFileLine(line):
    words = line.split()
    if len(words) > 6:
        date1 = words[0][4:] + ':' + words[0][:3] + ':' + words[1]
        date2 = words[2][4:] + ':' + words[2][:3] + ':' + words[3]
        duration = words[4]
        condition = words[5]
        obstruction = words[6]
        returndata = (date1, date2, duration, condition, obstruction)
    if len(words) == 9:
        timer = words[7]
        etype = words[8]
        returndata = (date1, date2, duration, condition, obstruction, timer,
                      etype)
    return returndata
        

def readEclipseFile(filename):
    fin = open(filename,'rb')
    datalines = fin.readlines()
    fin.close()
    eclipse = {}

    words = datalines.pop(0).split()
    eclipse.update({'epoch':words})
    # eclipse.update({'epoch':words[-2][:4]})
    # eclipse.update(dict({'epoch':zip(('year','day'),
    #                                  (words[-2][:4],words[-2][5:]))}))

    # This advances the line and ensures that empty lines and unimportant text is not read in,
    # provided the unimportant text is less than 50 characters long.
    line = datalines.pop(0)
    while len(line) < 50:
        line = datalines.pop(0)
        
    headers = re.split("\s{2,5}",line.strip())

    # Modify the Start Time, Stop Time and duration header names
    headers[0] = headers[0][:10]
    headers[1] = headers[1][:9]
    headers[2] = headers[2][:8]

    headers = tuple(headers)

    skeletondict = dict((str(key),[]) for key in headers )
    
    line = datalines.pop(0)

    n = -1

    numcols = len(headers) + 2 # +2 because dates include spaces

    while len(datalines) > 0:
        line = datalines.pop(0).strip()
        
        if len(line.split()) == numcols:
            n = n + 1
            eclipse.update({n:{}})

            eclipsedata = readEclipseFileLine(line)

            eclipse[n].update(dict(entrancepenumbra=dict(zip(headers,
                                                             eclipsedata))))

            if len(datalines) > 0:
                if len(datalines[0].split()) == 7:
                    line = datalines.pop(0)
                    eclipsedata = readEclipseFileLine(line)
                    eclipse[n].update(dict(umbra=dict(zip(headers[:-2],
                                                          eclipsedata))))
                    
                    line = datalines.pop(0)
                    eclipsedata = readEclipseFileLine(line)
                    eclipse[n].update(dict(exitpenumbra=dict(zip(headers[:-2],
                                                                 eclipsedata))))

    return eclipse


def convertEclipseTimes(eclipse):
    for n in eclipse.keys():
        if n != 'epoch':
            for m in eclipse[n].keys():
                eclipse[n][m].update({'durationsec':
                                      np.double(eclipse[n][m]['Duration'])})              
                eclipse[n][m].update({'startsec':
                                      ct.DateTime(eclipse[n][m]['Start Time']).secs})
                eclipse[n][m].update({'stopsec':
                                      ct.DateTime(eclipse[n][m]['Stop Time']).secs})
                if m == 'entrancepenumbra':
                    eclipse[n][m].update({'timersec':
                                          np.double(eclipse[n][m]
                                                    ['Entry Timer'])})
    return eclipse


def readAltitude():
    fin = open('altitude.txt','rb')
    datalines = fin.readlines()
    fin.close()
    altitude = np.array([np.double(line.strip().split()[1]) for line in datalines])
    times = np.array([ct.DateTime(line.strip().split()[0]).secs for line in datalines])
    return (times,altitude)



def findExtrema(x,y):

    x = np.array(x)
    y = np.array(y)
    
    # Remove repeated points
    d = np.diff(y)
    keep = np.append(True,d!=0)
    vals = y[keep]
    times = x[keep]
    
    d = np.diff(vals)
    s = np.sign(d)
    ds = np.diff(s)
    
    if s[0] == 1:
        minpts = np.append(True ,ds == 2)
        maxpts = np.append(False,ds == -2)
    elif s[0] == -1:
        minpts = np.append(False,ds == 2)
        maxpts = np.append(True,ds == -2)
    
    if s[-1] == 1:
        minpts = np.append(minpts,False)
        maxpts = np.append(maxpts,True)
    elif s[-1] == -1:
        minpts = np.append(minpts,True)
        maxpts = np.append(maxpts,False)
    
    minbool = np.zeros(len(y))
    minbool[keep] = minpts
    minbool = minbool == 1
    
    maxbool = np.zeros(len(y))
    maxbool[keep] = maxpts
    maxbool = maxbool == 1
    
    return minbool,maxbool



 
def readComms(filename,numheaderlines,year):
    # filename = 'DSN_times.txt'
    # numheaderlines = 9
    #
    fin = open(filename,'rb')
    datalines = fin.readlines()
    fin.close()
    [datalines.pop(0) for n in range(numheaderlines)]

    year = str(year)

    fieldnames = ('day', 'start', 'bot', 'eot', 'end', 'facility', 'user',
                  'endocde2', 'endcode1', 'config', 'passno', 'activity',
                  'tstart', 'tbot', 'teot', 'tend')

    commdata = {}

    k=-1
    while len(datalines) > 0:
        k = k + 1
        
        words = datalines.pop(0).strip().split()
        day = words.pop(0)
        start = words.pop(0)
        bot = words.pop(0)
        eot = words.pop(0)
        end = words.pop(0)
        facility = words.pop(0)
        user = words.pop(0)
        endcode2 = words.pop(-1)
        endcode1 = words.pop(-1)
        config = words.pop(-1)
        passno = words.pop(-1)
        activity = ' '.join(words)

        yearday = year + ':' + day + ':'
        tstart = ct.DateTime(yearday + start[:2] + ':' + start[2:] +
                             ':00.000').secs
        tbot = ct.DateTime(yearday + bot[:2] + ':' + bot[2:] + ':00.000').secs
        teot = ct.DateTime(yearday + eot[:2] + ':' + eot[2:] + ':00.000').secs
        tend = ct.DateTime(yearday + end[:2] + ':' + end[2:] + ':00.000').secs

        if np.double(bot) < np.double(start):
            tbot = tbot + 24 * 3600
            teot = teot + 24 * 3600
            tend = tend + 24 * 3600
        elif np.double(eot) < np.double(bot):
            teot = teot + 24 * 3600
            tend = tend + 24 * 3600            
        elif np.double(end) < np.double(eot):
            tend = tend + 24 * 3600
            
        passinfo = (day, start, bot, eot, end, facility, user, endcode2,
                    endcode1, config, passno, activity, tstart, tbot, teot,
                    tend)

        commdata.update(dict({k:dict(zip(fieldnames, passinfo))}))
    
        junk = datalines.pop(0)

    return commdata
