
import numpy as np
import re

import Ska.engarchive.fetch_eng as fetch_eng
from Chandra.Time import DateTime

def readGLIMMON(filename='/home/greta/AXAFSHARE/dec/G_LIMMON.dec'):
    revision_pattern = '.*\$Revision\s*:\s*([0-9.]+).*$'
    date_pattern = '.*\$Date\s*:\s*([0-9]+)/([0-9]+)/([0-9]+)\s+([0-9]+):([0-9]+):([0-9]+).*$'
    version_pattern = '.*Version\s*:\s*[$]?([A-Za-z0-9.:\s*]*)[$]?"\s*$'
    database_pattern = '.*Database\s*:\s*(\w*)"\s*$'

    # Read the GLIMMON.dec file and store each line in "gfile"
    with open(filename, 'r') as fid:
        gfile = fid.readlines()

    # Initialize the glimmon dictionary
    glimmon = {}

    # Step through each line in the GLIMMON.dec file
    for line in gfile:

        comment_line = line[line.find('#'):].strip()

        # Remove comments
        line = line[:line.find('#')].strip()

        # Assume the line uses whitespace as a delimiter
        words = line.split()

        if words:
            # Only process lines that begin with MLOAD, MLIMIT, MLMTOL, MLIMSW, MLMENABLE,
            # MLMDEFTOL, or MLMTHROW. This means that all lines with equations are
            # omitted; we are only interested in the limits and expected states

            if (words[0] == 'MLOAD') & (len(words) == 2):
                name = words[1]
                glimmon.update({name:{}})

            elif words[0] == 'MLIMIT':
                setnum = int(words[2])
                glimmon[name].update({setnum:{}})
                if glimmon[name].has_key('setkeys'):
                    glimmon[name]['setkeys'].append(setnum)
                else:
                    glimmon[name]['setkeys'] = [setnum,]

                if 'DEFAULT' in words:
                    glimmon[name].update({'default':setnum})

                if 'SWITCHSTATE' in words:
                    ind = words.index('SWITCHSTATE')
                    glimmon[name][setnum].update({'switchstate':words[ind+1]})

                if 'PPENG' in words:
                    ind = words.index('PPENG')
                    glimmon[name].update({'type':'limit'})
                    glimmon[name][setnum].update({'warning_low':
                                                  float(words[ind + 1])})
                    glimmon[name][setnum].update({'caution_low':
                                                  float(words[ind + 2])})
                    glimmon[name][setnum].update({'caution_high':
                                                  float(words[ind + 3])})
                    glimmon[name][setnum].update({'warning_high':
                                                  float(words[ind + 4])})

                if 'EXPST' in words:
                    ind = words.index('EXPST')
                    glimmon[name].update({'type':'expected_state'})
                    glimmon[name][setnum].update({'expst':words[ind + 1]})

            elif words[0] == 'MLMTOL':
                glimmon[name].update({'mlmtol':int(words[1])})

            elif words[0] == 'MLIMSW':
                glimmon[name].update({'mlimsw':words[1]})

            elif words[0] == 'MLMENABLE':
                glimmon[name].update({'mlmenable':int(words[1])})

            elif words[0] == 'MLMDEFTOL':
                glimmon.update({'mlmdeftol':int(words[1])})

            elif words[0] == 'MLMTHROW':
                glimmon.update({'mlmthrow':int(words[1])})

            elif len(re.findall(revision_pattern, line)) > 0:
                version = re.findall(revision_pattern, line)
                glimmon.update({'revision':version[0].strip()})
                glimmon.update({'version':version[0].strip()})

            elif len(re.findall('^XMSID TEXTONLY ROWCOL.*COLOR.*Version', line)) > 0:
                version = re.findall(version_pattern, line)
                glimmon.update({'version':version[0].strip()})

            elif len(re.findall('^XMSID TEXTONLY ROWCOL.*COLOR.*Database', line)) > 0:
                database = re.findall(database_pattern, line)
                glimmon.update({'database':database[0].strip()})

        # elif len(re.findall('^#\$Revision', comment_line)) > 0:
        elif len(re.findall(revision_pattern, comment_line)) > 0:
            revision = re.findall(revision_pattern, comment_line)
            glimmon.update({'revision':revision[0].strip()})

        # elif len(re.findall('^#\$Date', comment_line)) > 0:
        elif len(re.findall(date_pattern, comment_line)) > 0:
            date = re.findall(date_pattern, comment_line)
            glimmon.update({'date':date[0]})

    return glimmon


def parse_comments(filename='/home/greta/AXAFSHARE/dec/G_LIMMON.dec'):

    with open(filename, 'r') as fid:
        gfile = fid.readlines()

    # Start at a point in the comments when they followed a predictable form
    startline = 603
    s = ''.join(gfile[startline:])

    commentstart = '(#\s+([0|1]\d-\d\d-20\d\d)\s+(\w+\s+\w+)\s+(.*))'

    r = re.findall(commentstart, s)

    start = [s.find(m[0]) for m in r]
    start.append(s.find('#' + '=' * 75))
    dates = [m[1] for m in r]
    names = [m[2] for m in r]
    text = [s[start[n]:start[n+1]] for n in range(len(start)-1)]

    def add_changes(t, d):

        msid = '#\s+(\w+):?\s*'
        vtype = '(\w+\s\w*)\s*[=,:]?\s*'
        val = '([0-9fFcC.-]+)\s*'
        dval = '(.*)'
        changelistpattern = (msid + vtype + val + vtype + val + dval)

        # I'm splitting this because regex .* is not behaving as expected with
        # newlines. Operating on a line by line basis is therefor more robust.
        details = t[d.end():].split('\n')

        changedict = {}
        for line in details:
            changes = re.findall(changelistpattern, line)

            if changes:

                msid = changes[0][0].lower()
                changetype = changes[0][1].lower()
                oldval = changes[0][2]
                newval = changes[0][4]
                description = changes[0][5]

                if msid not in changedict.keys():
                    changedict.update({msid:{}})

                if changetype not in changedict[msid].keys():
                    changedict[msid].update({changetype:{}})

                changedict[msid][changetype].update(
                    {'old':oldval, 'new':newval, 'description':description})

        return changedict

    glimmonchanges = {}
    for date, name, t in zip(dates, names, text):

        datestr = date[6:] + '-' + date[:2] + '-' + date[3:5]
        datesec = DateTime(datestr).secs

        detailstart = '#\s+(MSID)?From:?\s+To:?\s*\w*:?'
        d = re.search(detailstart, t, re.IGNORECASE & re.DOTALL)

        messagestart = t.find(name) + len(name)

        if d:
            message = t[messagestart:(d.start()-1)].strip()
            changedict = add_changes(t, d)

        else:
            message = t[messagestart:].strip()
            changedict = {}

        message = re.sub('\s*\n#\s+', ' ', message)
        message = re.sub('\n#', '', message)

        glimmonchanges[datesec] = {'date':DateTime(datestr).date,
                                   'name':name,
                                   'message':message,
                                   'changes':changedict}

    return glimmonchanges

def process_limits_file(filename='limfile.txt'):
    ''' Process the limit file
    '''

    # Load the greta limit file
    infile = open(filename,'r')
    limlines = infile.readlines()
    infile.close()

    limlog = {}

    for line in limlines:
        words = line.split()
        if words:

            tstring = DateTime(words[0],'greta').date
            msid = words[2]
            msg = words[3]
            currentval = words[4]

            try:
                fetchobj = fetch.Msid(msid, start='2001:001:00:00:00',
                                      stop='2001:001:00:05:00')
                owner = fetchobj.tdb.owner_id
                description = fetchobj.tdb.technical_name
            except:
                owner = 'Not Known'
                description = 'Not Known'

            # There should be 5 columns for a return to NOMINAL and 7 colums

            # for a violation. In cases where data gets corrupted for whatever

            # reason, the current value can be left blank. When this gets left

            # blank, treat this as a violation but assign 'none' as the current
            # value.

            if len(words) == 7:
                opr = words[5]
                lim = words[6]
            elif len(words) == 6:
                currentval = 'none'
                opr = words[4]
                lim = words[5]

            # if the current value is equal to none, then skip this
            # line in the limits file
            if currentval != 'none':

                if limlog.has_key(msid):

                    if limlog[msid].has_key('firstviolation'):

                        # if it is nominal, then increase the toggle count
                        if words[3] == 'NOMINAL':

                            limlog[msid]['num'] = limlog[msid]['num'] + 1

                            limlog[msid].update({'endtime':tstring})

                        # if it is not nominal, then all you need to worry

                        # about is determining what the worst violation type

                        # is. This assumes that an msid won't cross a high and
                        # low limit in the same period over which this script
                        # is run.
                        else:

                            # The following if-else statement will not return
                            # return correct results if both a high and a low
                            # limit violation occurs in the same file. This

                            # would only be likely to happen if the telemetry
                            # stream were corrupt.
                            if 'WARNING' in msg:
                                maxval = np.max([float(currentval),
                                                limlog[msid]['max']])
                                minval = np.min([float(currentval),
                                                limlog[msid]['min']])
                                limlog[msid]['worsttype'] = msg
                                limlog[msid]['max'] = maxval
                                limlog[msid]['min'] = minval
                                limlog[msid]['limit'] = lim

                            elif 'CAUTION' in msg:
                                maxval = np.max([float(currentval),
                                                limlog[msid]['max']])
                                minval = np.min([float(currentval),
                                                limlog[msid]['min']])
                                if limlog[msid].has_key('worsttype'):
                                    if 'WARNING' not in \
                                                    limlog[msid]['worsttype']:
                                        limlog[msid]['worsttype'] = msg
                                        limlog[msid]['limit'] = lim
                                else:
                                    limlog[msid]['worsttype'] = msg
                                    limlog[msid]['limit'] = lim
                                limlog[msid]['max'] = maxval
                                limlog[msid]['min'] = minval

                            else:
                                # Then this must be an out of state violation
                                limlog[msid]['worsttype'] = msg
                                limlog[msid]['statelog'].append(currentval)

                                # use same name as limits for simplicity
                                limlog[msid]['limit'] = lim

                    # In this case, an msid has already been recorded, but

                    # without a first violation, which means it must have been
                    # a return to nominal (since this msid already has an

                    # entry)
                    else:
                        if msg == 'OUT-OF-STATE':
                            limlog[msid].update({'statelog':[currentval]})
                            limlog[msid].update({'initialvalue':currentval})
                            limlog[msid].update({'limit':lim})
                            limlog[msid].update({'firstviolation':tstring})
                            limlog[msid].update({'worsttype':msg})

                        elif msg == 'NOMINAL':
                            # do nothing, this is a repeat return to nominal
                            junk = 9
                        else:
                            limlog[msid].update({'max':float(currentval)})
                            limlog[msid].update({'min':float(currentval)})
                            limlog[msid].update({'initialvalue':
                                                 float(currentval)})
                            limlog[msid].update({'limit':float(lim)})
                            limlog[msid].update({'firstviolation':tstring})
                            limlog[msid].update({'worsttype':msg})

                else:
                    limlog.update({msid:{}})

                    limlog[msid].update({'owner':owner})
                    limlog[msid].update({'description':description})

                    if words[3] != 'NOMINAL': # if NOT nominal
                        limlog[msid].update({'firstviolation':tstring})
                        limlog[msid].update({'worsttype':msg})
                        limlog[msid].update({'num':0})

                        if msg == 'OUT-OF-STATE':
                            limlog[msid].update({'statelog':[currentval]})
                            limlog[msid].update({'initialvalue':currentval})
                            limlog[msid].update({'limit':lim})
                        else:
                            limlog[msid].update({'max':float(currentval)})
                            limlog[msid].update({'min':float(currentval)})
                            limlog[msid].update({'initialvalue':
                                                 float(currentval)})
                            limlog[msid].update({'limit':float(lim)})

                    else:
                        limlog[msid].update({'num':0})
                        limlog[msid].update({'comment':'return to nominal ' +

                                             'is observed before violation'})

            else:
                print 'Skipped this line in the limits file due to missing' + \
                      ' value:\n%s\n'%line

    return limlog

def parsedecplot(decfile, removewidechars=True):
    '''Parse a GRETA dec plot file to extract plotting data. This will not
    grab text display data.
    '''

    def finddecstring(pattern, string, rtype='string', split=False):
        '''Search a single line in a GRETA dec file for plotting
        information.

        "pattern" is the name of the GRETA keyword
        "string" is the string to be searched
        "rtype" is the returned data type (currently string, int, or float)
        "split" is a flag to allow the user to request the returned data be
            split into a list
        '''

        rtype = str(rtype).lower()
        p1 = re.compile('^' + pattern + '\s+(.*)$', re.MULTILINE)
        r = p1.search(string)
        if not isinstance(r, type(None)):
            rval = r.group(1)
            if split:
                rval = rval.split()
            if rtype == 'string':
                if split:
                    rval = [val.strip() for val in rval]
                else:
                    rval = rval.strip()
            if rtype=='float':
                if split:
                    rval = [float(n) for n in rval]
                else:
                    rval = float(rval)
            if rtype=='int':
                if split:
                    rval = [int(n) for n in rval]
                else:
                    rval = int(rval)
            return rval

    #filename = 'Orbit_Plots/T_STT72_ISIM_ACIS.dec'
    infile = open(decfile,'rb')
    body = infile.read()
    infile.close()

    decplots = {}

    decplots['DTITLE'] = finddecstring('DTITLE', body)
    decplots['DSUBTITLE'] = finddecstring('DSUBTITLE', body)
    decplots['DTYPE'] = finddecstring('DTYPE', body, split=True)
    decplots['DTYPE'][1] = int(decplots['DTYPE'][1])
    xdata = finddecstring('DXAXIS', body, rtype='float', split=True)
    decplots['DXAXIS'] = [60*d for d in xdata]

    r = re.split('\nPINDEX',body) # Newline excludes commented out plots
    decplots['numplots'] = len(r)-1
    plots = {}
    for plotdef in r[1:]:
        num = int(re.match('\s+(\d+)[.\n]*', plotdef).group(1))
        plots[num] = {}
        plots[num]['PINDEX'] = num
        plots[num]['PTRACES'] = finddecstring('PTRACES', plotdef,
                                              rtype='int')
        plots[num]['PBILEVELS'] = finddecstring('PBILEVELS', plotdef,
                                                rtype='int')

        plots[num]['PTITLE'] = finddecstring('PTITLE', plotdef)
        plots[num]['PYLABEL'] = finddecstring('PYLABEL', plotdef)
        plots[num]['PGRID'] = finddecstring('PGRID', plotdef, rtype='int')
        plots[num]['PLEGEND'] = finddecstring('PLEGEND', plotdef,
                                              rtype='int')
        plots[num]['PYAXIS'] = finddecstring('PYAXIS', plotdef,
                                             rtype='float', split=True)
        plots[num]['PYAUTO'] = finddecstring('PYAUTO', plotdef, rtype='int')

        # cycle through all TINDEX in a similar way to how you cycle through
        # PINDEX
        t = re.split('\nTINDEX',plotdef) # Newline excludes commented out msids
        traces = {}
        for tracedef in t[1:]:
            tnum = int(re.match('\s+(\d+)[.\n]*', tracedef).group(1))
            traces[tnum] = {}
            traces[tnum]['TINDEX'] = tnum
            traces[tnum]['TMSID'] = finddecstring('TMSID', tracedef)
            traces[tnum]['TNAME'] = finddecstring('TNAME', tracedef)
            traces[tnum]['TCOLOR'] = finddecstring('TCOLOR', tracedef)
            traces[tnum]['TCALC'] = finddecstring('TCALC', tracedef)
            traces[tnum]['TSTAT'] = finddecstring('TSTAT', tracedef)
            if removewidechars:
                if traces[tnum]['TMSID'] != None:
                    traces[tnum]['TMSID'] = traces[tnum]['TMSID'].replace('_WIDE', '')
                    traces[tnum]['TMSID'] = traces[tnum]['TMSID'].replace('_wide', '')
        plots[num]['traces'] = traces

        # TBLINDEX - do this separate in case they are intermingled with
        # TINDEX definitions
        tb = re.split('\nTBLINDEX',tracedef) # Newline excludes comments
        if len(tb) > 1:
            tbtraces = {}
            for tbtracedef in tb[1:]:
                tbnum = re.match('\s+(\d+)[.\n]*', tbtracedef)
                tbnum = int(tbnum.group(1))
                tbtraces[tbnum] = {}
                tbtraces[tbnum]['TBINDEX'] = tbnum
                tbtraces[tbnum]['TMSID'] = finddecstring('TMSID', tbtracedef)
                tbtraces[tbnum]['TNAME'] = finddecstring('TNAME', tbtracedef)
                tbtraces[tbnum]['TCOLOR'] = finddecstring('TCOLOR', tbtracedef)
                if removewidechars:
                    if traces[tnum]['TMSID'] != None:
                        traces[tnum]['TMSID'] = traces[tnum]['TMSID'].replace('_WIDE', '')
                        traces[tnum]['TMSID'] = traces[tnum]['TMSID'].replace('_wide', '')
            plots[num]['tbtraces'] = tbtraces

    decplots['plots'] = plots

    return decplots
