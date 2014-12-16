
import numpy as np
import re

import Ska.engarchive.fetch_eng as fetch_eng
from Chandra.Time import DateTime


# def read_eclipse_file_line(line):
#     words = line.split()
#     if len(words) > 6:
#         date1 = words[0][4:] + ':' + words[0][:3] + ':' + words[1]
#         date2 = words[2][4:] + ':' + words[2][:3] + ':' + words[3]
#         duration = words[4]
#         condition = words[5]
#         obstruction = words[6]
#         returndata = (date1, date2, duration, condition, obstruction)
#     if len(words) == 9:
#         timer = words[7]
#         etype = words[8]
#         returndata = (date1, date2, duration, condition, obstruction, timer,
#                       etype)
#     return returndata
        

def read_eclipse_file(filename='/home/mission/Backstop/History/ECLIPSE.txt'):

    def parse_line(line):
        words = line.split()
        starttime = words[0][4:] + ':' + words[0][:3] + ':' + words[1]
        stoptime = words[2][4:] + ':' + words[2][:3] + ':' + words[3]

        returndict = {'Start Time':starttime,
                      'Stop Time':stoptime,
                      'Duration':words[4],
                      'Current Condition': words[5],
                      'Obstruction':words[6],
                      'durationsec':np.double(words[4]),
                      'startsec':DateTime(starttime).secs,
                      'stopsec':DateTime(stoptime).secs}

        if len(words) == 9:
            returndict.update({'Entry Timer':words[7],
                               'timersec':np.double(words[7]),
                               'Type':words[8]})

        return returndict


    with open(filename, 'rb') as fid:
        datalines = fid.readlines()

    # The first line includes the year and day the file was generated
    #
    # Note: This entry may be manually created and could be a source of error
    # if read incorrectly.
    words = datalines.pop(0).split()
    #eclipse = {'epoch':dict(zip(('year','day'), (words[-2][:4],words[-2][5:])))}
    eclipse = {'epoch':{'year':words[2]}}
    eclipse['epoch'].update({'dom':words[0]})
    eclipse['epoch'].update({'month':words[1]})
    eclipse['epoch'].update({'time':words[3]})

    hosc = DateTime(words[2] + words[1] + words[0] + ' at ' + words[3]).date
    eclipse['epoch'].update({'doy':hosc[5:8]})

    # Remove spacing lines
    line = datalines.pop(0)
    while len(line.strip()) < 50:
        line = datalines.pop(0)

    headers = re.split("\s{2,5}",line.strip())

    # Truncate the Start Time, Stop Time and Duration header names
    headers[0] = headers[0][:10]
    headers[1] = headers[1][:9]
    headers[2] = headers[2][:8]

    # Remove the dashed lines separating the header from the eclipse data entries
    line = datalines.pop(0)

    # This is the eclipse number; it is used to index all eclipses in the
    # file. It has no other significance.
    n = -1
    eclipse.update({'eclipse_nums':[]})

    while len(datalines) > 0:
        line = datalines.pop(0).strip()

        # All eclipse entries start wth at least 7 "words"
        if len(line.split()) == 7:

            # increment the eclipse number and create a placeholder dict
            n = n + 1
            eclipse['eclipse_nums'].append(n)
            eclipse.update({n:{}})

            # Add the entrance penumbra data, there will always be an entrance
            # penumbra
            eclipsedata = parse_line(line)
            eclipse[n].update({'entrancepenumbra':eclipsedata})

            # If this is a full eclipse, then there will also be umbra and
            # exit penumbra phases.
            if len(datalines) > 0: 
                if 'Umbra' in datalines[0]:

                    line = datalines.pop(0)
                    eclipsedata = parse_line(line)
                    eclipse[n].update({'umbra':eclipsedata})

                    line = datalines.pop(0)
                    eclipsedata = parse_line(line)
                    eclipse[n].update({'exitpenumbra':eclipsedata})

    return eclipse


def convert_eclipse_times(eclipse):
    for n in eclipse['eclipse_nums']:
        if n != 'epoch':
            for m in eclipse[n].keys():
                eclipse[n][m].update({'durationsec':
                                      np.double(eclipse[n][m]['Duration'])})              
                eclipse[n][m].update({'startsec':
                                      DateTime(eclipse[n][m]['Start Time']).secs})
                eclipse[n][m].update({'stopsec':
                                      DateTime(eclipse[n][m]['Stop Time']).secs})
                if m == 'entrancepenumbra':
                    if eclipse[n][m].has_key('Entry Timer'):
                        eclipse[n][m].update({'timersec':
                                              np.double(eclipse[n][m]
                                                        ['Entry Timer'])})
    return eclipse


def read_altitude():
    fin = open('altitude.txt','rb')
    datalines = fin.readlines()
    fin.close()
    altitude = np.array([np.double(line.strip().split()[1]) for line in datalines])
    times = np.array([DateTime(line.strip().split()[0]).secs for line in datalines])
    return (times,altitude)



def find_extrema(x,y):

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



 
def read_comms(filename,numheaderlines,year):
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
        if len(datalines[0].strip()) > 20:
            k = k + 1
            
            words = datalines.pop(0).strip().split()
            try:
                day = words.pop(0)
            except:
                import readline # optional, will allow Up/Down/History in the console
                import code
                vars = globals().copy()
                vars.update(locals())
                shell = code.InteractiveConsole(vars)
                shell.interact()
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
            tstart = DateTime(yearday + start[:2] + ':' + start[2:] +
                                 ':00.000').secs
            tbot = DateTime(yearday + bot[:2] + ':' + bot[2:] + ':00.000').secs
            teot = DateTime(yearday + eot[:2] + ':' + eot[2:] + ':00.000').secs
            tend = DateTime(yearday + end[:2] + ':' + end[2:] + ':00.000').secs

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
