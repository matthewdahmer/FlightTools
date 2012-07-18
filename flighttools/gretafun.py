
import json
import pickle
import numpy as np
import re
import subprocess as sp

import Ska.engarchive.fetch_eng as fetch_eng
import Chandra.Time as ct




def runDec(time1, time2, outfile, decfile, envfile):
    '''runDec(t1.date, t2.date, "junk.txt", decfile, envfile)
    '''
    
    def readENV(envfile):
        fid = open(envfile,'r')
        env = fid.readlines()
        fid.close()
        envvar = {}
        for line in env:
            pair = line.strip().split('=',1)
            envvar[pair[0]]=pair[1]
    return envvar

    
    t1 = (time1[:4] + time1[5:8] + '.' + time1[9:11] + time1[12:14]
          + time1[15:17] + time1[18:21])
    t2 = (time2[:4] + time2[5:8] + '.' + time2[9:11] + time2[12:14]
          + time2[15:17] + time2[18:21])

    decomcommand = ('decom98 -d ' + decfile + ' -m 3 -f ztlm_autoselect@' + 
                    str(t1) + '-' + str(t2) + ' -a ' + outfile)
    print('running:\n  %s\n'%decomcommand)
    
    d = sp.call(decomcommand, shell=True, env=envvar)


    
def readGLIMMON(filename='/home/greta/AXAFSHARE/dec/G_LIMMON.dec'):

    # Read the GLIMMON.dec file and store each line in "gfile"
    filehandle = open(filename,'r')
    gfile = filehandle.readlines()
    filehandle.close()

    # Initialize the glimmon dictionary
    glimmon = {}

    # Step through each line in the GLIMMON.dec file
    for line in gfile:

        # Assume the line uses whitespace as a delimiter
        words = line.split()

        if words:
            # Only process lines that begin with MLOAD, MLIMIT, MLMTOL, MLIMSW,
            # or MLMENABLE. This means that all lines with equations are
            # omitted; we are only interested in the limits and expected states
            
            if words[0] == 'MLOAD':
                name = words[1]
                glimmon.update({name:{}})
            elif words[0] == 'MLIMIT':
                setnum = int(words[2])
                glimmon[name].update({setnum:{}})

                if 'DEFAULT' in words:
                    glimmon[name].update({'default':setnum})

                if 'SWITCHSTATE' in words:
                    ind = words.index('SWITCHSTATE')
                    glimmon[name][setnum].update({'switchstate':words[ind+1]})

                if 'PPENG' in words:
                    ind = words.index('PPENG')
                    glimmon[name][setnum].update({'type':'limit'})
                    glimmon[name][setnum].update({'warning_low':float(words[ind + 1])})
                    glimmon[name][setnum].update({'caution_low':float(words[ind + 2])})
                    glimmon[name][setnum].update({'caution_high':float(words[ind + 3])})
                    glimmon[name][setnum].update({'warning_high':float(words[ind + 4])})

                if 'EXPST' in words:
                    ind = words.index('EXPST')
                    glimmon[name][setnum].update({'type':'state'})
                    glimmon[name][setnum].update({'expst':words[ind + 1]})

            elif words[0] == 'MLMTOL':
                glimmon[name].update({'mlmtol':int(words[1])})

            elif words[0] == 'MLIMSW':
                glimmon[name].update({'mlimsw':words[1]})

            elif words[0] == 'MLMENABLE':
                glimmon[name].update({'mlmenable':int(words[1])})

    return glimmon


def getGLIMMONLimits(MSID, glimmon=None):
    """ Get the GLIMMON limits from the glimmon datastructure
    """
    if not glimmon:
        glimmon = readGLIMMON()
	
    glimits = {}
    
    if MSID in glimmon.keys():
        if glimmon[MSID].has_key('default'):
            gdefault = glimmon[MSID]['default']
        else:
            gdefault = 0

        glimits['warning_low'] = glimmon[MSID][gdefault]['warning_low']
        glimits['caution_low'] = glimmon[MSID][gdefault]['caution_low']
        glimits['caution_high'] = glimmon[MSID][gdefault]['caution_high']
        glimits['warning_high'] = glimmon[MSID][gdefault]['warning_high']
    
    return glimits


def getSafetyLimits(telem):
    """ Update the current database limits
        
    The database limits are replaced with the G_LIMMON limits if the
    G_LIMMON limits are more permissive (which would only be the case if
    the database limits are outdated). Only those individual limits that
    are more permissive are replaced, not the entire set.
    
    For MSIDs that have numeric limits, update any database limit if the
    corresponding GLIMMON limit is outside of the database limit.

    The updated limit set is returned in a separate dictionary, regardless
    of whether or not any updates were made.
    
    This is meant to generate a pseudo-P010 database limit set. This assumes
    that the GLIMMON limit set reflects the new database limits. However often
    GLIMMON limits will be set within newly adjusted database limits, so the
    values returned by this routine may be more conservative than necessary.
    
    glimmon is a dictionary of limits and expected states read in from a
    GLIMMON file, for all msids in GLIMMON.
    
    telem is a single telemetry data class instance generated using the
    Ska.engarchive.fetch_eng.Msid function. (single MSID)
    
    In the future this function can add the ability to traverse all limit sets
    for a single MSID
    
    #FIXME PRIORITY LOW Add the ability to update multiple limit sets for a
    a single msid#
    """
    
    def getTDBLimits(telem):
        """ Retrieve the TDB limits from the telem object

        Returns an empty dict object if there are no limits specified in the
        database
        """

        safetylimits = {}

        try:
            # Get the TDB default set num, this is the only limit set that is
            # modified.
            tdbdefault = telem.tdb.limit_default_set_num

            limits = telem.tdb.Tlmt
            
            if limits:

                if len(telem.tdb.Tlmt) == 1:
                    #In this case there is only one limit set
                    safetylimits['warning_low'] = limits['WARNING_LOW']
                    safetylimits['caution_low'] = limits['CAUTION_LOW']
                    safetylimits['caution_high'] = limits['CAUTION_HIGH']
                    safetylimits['warning_high'] = limits['WARNING_HIGH']

                else:
                    # Then assume there is more than one limit set and use the
                    # default set.
                    mask = telem.tdb.Tlmt['LIMIT_SET_NUM'].data == tdbdefault

                    safetylimits['warning_low'] = \
                                        limits['WARNING_LOW'].data[mask][0]
                    safetylimits['caution_low'] = \
                                        limits['CAUTION_LOW'].data[mask][0]
                    safetylimits['caution_high'] = \
                                        limits['CAUTION_HIGH'].data[mask][0]
                    safetylimits['warning_high'] = \
                                        limits['WARNING_HIGH'].data[mask][0]
        except KeyError as e:
            print('%s does not have limits in Engineering Archive TDB'%telem.MSID)

        return safetylimits


    # Set the safetylimits dict here. An empty dict is returned if there are no
    # limits specified. This is intended and relied upon later.
    safetylimits = getTDBLimits(telem)


    # Make it simpler to index into the glimmon dict, where msids names are all
    # upper case.
    MSID = telem.msid.upper()


    # Read the GLIMMON file
    glimmon = readGLIMMON()
    

    # Generate GLIMMON tests for use later
    msid_has_glimmon_limits = False # Initialize to False
    msid_in_glimmon = MSID in glimmon.keys()
    if msid_in_glimmon:
        if glimmon[MSID].has_key(0):
            if glimmon[MSID][0].has_key('type'):
                msid_has_glimmon_limits = glimmon[MSID][0]['type'] == 'limit'


    # If there are no limits in the TDB but there are in GLIMMON, use the
    # GLIMMON limits
    if not safetylimits and  msid_in_glimmon and msid_has_glimmon_limits:
        safetylimits = getGLIMMONLimits(MSID, glimmon)


    # If there are limits in both GLIMMON and the TDB use the set that
    # is most permissive.
    if safetylimits and  msid_in_glimmon and msid_has_glimmon_limits:
        glimits = getGLIMMONLimits(MSID, glimmon)

        if glimits['warning_low'] < safetylimits['warning_low']:
            safetylimits['warning_low'] = glimits['warning_low']
            print('Updated warning low safety limit for %s'%telem.msid)

        if glimits['caution_low'] < safetylimits['caution_low']:
            safetylimits['caution_low'] = glimits['caution_low']
            print('Updated caution low safety limit for %s'%telem.msid)
  
        if glimits['warning_high'] > safetylimits['warning_high']:
            safetylimits['warning_high'] = glimits['warning_high']
            print('Updated warning high safety limit for %s'%telem.msid)

        if glimits['caution_high'] > safetylimits['caution_high']:
            safetylimits['caution_high'] = glimits['caution_high']
            print('Updated caution high safety limit for %s'%telem.msid)

    return safetylimits





def parsedecplot(decfile):
    '''Parse a GRETA dec plot file to extract plotting data. This will not
    grab text display data.
    '''

    def finddecstring(pattern,string,rtype='string',split=False):
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
        if not isinstance(r,type(None)):
            rval = r.group(1)
            if split:
                rval = rval.split()
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
            traces[tnum]['TMSID'] = finddecstring('TMSID', tracedef).strip()
            traces[tnum]['TNAME'] = finddecstring('TNAME', tracedef)
            traces[tnum]['TCOLOR'] = finddecstring('TCOLOR', tracedef)
            traces[tnum]['TCALC'] = finddecstring('TCALC', tracedef)
            traces[tnum]['TSTAT'] = finddecstring('TSTAT', tracedef)
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
                tbtraces[tbnum]['TMSID'] = finddecstring('TMSID', tbtracedef).strip()
                tbtraces[tbnum]['TNAME'] = finddecstring('TNAME', tbtracedef)
                tbtraces[tbnum]['TCOLOR'] = finddecstring('TCOLOR', tbtracedef)
            plots[num]['tbtraces'] = tbtraces

    decplots['plots'] = plots


    return decplots
