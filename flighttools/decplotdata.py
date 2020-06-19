
import sys
import numpy as np

import Ska
import Ska.engarchive.fetch_eng as fetch
import Chandra.Time as ct

sys.path.append('/home/mdahmer/Library/Python/FlightTools/flighttools')
import gretafun
import dechelper

def debug(locals):
    import code
    code.interact(local=locals)

class plotdata(object):
    ''' Retrieve, configure, and return requested telemetry.

    This class/set of routines are required for these reasons:

    1) The plotting function this was built for requested a particular stat 
       (based on given data), which may not be available in the archive.

    2) State based telemetry does not include 5min or daily stats (bilevels).

    3) The plotting function expects to see "plotdata" and "plottimes" 
       attributes.

    4) The plotting functions expects to see limit information if available.

    5) Some "MSIDs" do not exist in the archive, but can be calculated. In
       this case, a simulated fetch.Msid class is returned.

    6) There are some time periods that should be removed from the data to 
       make the plots more relevant to monitoring trends during nominal
       operations.

    '''

    def __init__(self, msid, tstart, tstop, plotstat=None, fetchstat=None, type='numeric'):
        self.msid = msid
        self.time1 = tstart
        self.time2 = tstop
        self.plotstat = plotstat # calculated stat as defined in dec file
        self.fetchstat = fetchstat # archive stat ('5min', 'daily', or None)
        self.__dict__.update(self._gettracetelemetry())
        self.__dict__.update(self._getploplotstats())
        
    def _gettracetelemetry(self):
        '''Retrieve, configure and return telemetry.
        '''

        telem = self._fetchhelper(stat=self.fetchstat)

        # This ensures plotstat is defined as a string to make the tests below
        # more straightforward.
        if isinstance(self.plotstat,type(None)):
            self.plotstat = ''

        # Define name to use, this is used so labels can be added without
        # modifying the original msid name
        name = self.msid

        # Grab/calculate the requested data
        if self.plotstat.lower() == 'max':
            # It is assumed that all msids that use this stat are numeric
            if self.fetchstat:
                telem.plotdata = telem.maxes
            else:
                telem.plotdata = np.maximum.accumulate(telem.vals)

            telem.plottimes = telem.times

            name = name + '-max'


        elif self.plotstat.lower() == 'min':
            # It is assumed that all msids that use this stat are numeric
            if self.fetchstat:
                telem.plotdata = telem.mins
            else:
                telem.plotdata = np.minimum.accumulate(telem.vals)

            telem.plottimes = telem.times

            name = name + '-min'


        elif self.plotstat.lower() == 'mean':

            # Just look to see if mean values are present, if not then
            # calculate daily values from the full resolution data.

            if 'means' in telem.__dict__.keys():
                # Only numeric telemetry statistics objects will include means.
                telem.plotdata = telem.means
                telem.plottimes = telem.times

            else:
                # Since heater on/off data is stored as a state value,
                # statistics for these data are not calculated and stored
                # in the engineering archive.
                #
                # Remember that the character values are replaced with their 
                # corresponding raw values in the self._gettelemetry function.
                #
                # Since state based data will require the stats to be 
                # recalculated from the original data, refetch the full 
                # resolution data here and then calculate the means.
                telem = self._fetchhelper(stat=None)
                datadict = self._gettelemstats(telem, stat='daily')

                # Here you are copying over all the new stats, but you only
                # need the means and times
                telem.__dict__.update(datadict)
                telem.plotdata = telem.means
                telem.plottimes = telem.times

            name = name + '-avg'

            
        else:
            telem.plotdata = telem.vals
            telem.plottimes = telem.times

        try:
            safetylimits = gretafun.getSafetyLimits(telem)
        except:
            safetylimits = {}

        try:
            glimmonlimits = gretafun.getGLIMMONLimits(name)
        except KeyError:
            glimmonlimits = {}


        tracedata = {'msid': self.msid,
                     'name': name,
                     'telem':telem,
                     'safetylimits':safetylimits,
                     'glimmonlimits':safetylimits,
                     }

        return tracedata


    def _fetchhelper(self, stat):
        '''Fetch telemetry.

        This implements a set of helper functions that can be used to
        calculate or fetch from greta data that is not in the engineering
        archive. These are located in the dechelper.py file that is expected
        to reside in the current working directory or in the Python library
        path that is added at the top of this file.
        '''

        msid = self.msid.strip() # Sometimes there is a trailing space
        time1 = ct.DateTime(self.time1).secs - 5 * 24 * 3600
        time2 = ct.DateTime(self.time2).secs + 5 * 24 * 3600

        # Much of the code that handles the telemetry is built to expect these
        # fields, even if they are empty. Otherwise there would have to be
        # tests to see if telem exists or not everywhere.
        class emptyfetchobject(Ska.engarchive.fetch.Msid):
            def __init__(self):
                self.times = np.array([])
                self.vals = np.array([])
                self.MSID = ''
                self.datestart = ''
                self.datestop = ''
                self.tstart = ''
                self.tstop = ''

        telem = emptyfetchobject()
       
        try:
            # Try to fetch from the engineering archive
            telem = fetch.Msid(msid, time1, time2, stat=stat)
            
        except ValueError as e:

            print(e)

            try:
                if stat:
                    stat = "'" + str(stat) + "'"
                else:
                    stat = None

                evalstring = "dechelper.%s('%s', '%s', stat=%s)"%\
                             (msid.upper(), time1, time2, stat)
                print('Trying dechelper: %s'%evalstring)
                telem = eval(evalstring)

            except:
                # Then this msid is probably not implemented, move on with
                # the other plots
                #debug(locals())
                print('%s not in engineering archive, and not defined ' \
                      'elsewhere.'%msid)

        
        if any(telem.times):

            # Remove unwanted data, if data exists
            telem = self._removetimescaller(telem, stat)                   

            # Replace character values with their raw values for state based msids
            telem.type = 'numeric'

            if isinstance(telem.vals[0], type('')):
                telem.vals = np.abs(telem.raw_vals)
                telem.type = 'state'

        return telem


    def _removetimescaller(self, telem, stat):
        # There should be a better way to remove bad/unwanted data, but this
        # works for now

        # First remove the padded data
        telem = self._removetimes(telem, stat, 
                                ct.DateTime(self.time1).secs - 10 * 24 * 3600,
                                ct.DateTime(self.time1).secs)
        telem = self._removetimes(telem, stat, ct.DateTime(self.time2).secs,
                                ct.DateTime(self.time2).secs + 10 * 24 * 3600)
        
        telem = self._removetimes(telem, stat, '2011:149:00:00:00',
                                  '2011:153:00:00:00')
        telem = self._removetimes(telem, stat, '2011:186:00:00:00',
                                  '2011:195:00:00:00')
        telem = self._removetimes(telem, stat, '2011:299:00:00:00',
                                  '2011:306:00:00:00')
        telem = self._removetimes(telem, stat, '2012:149:00:00:00',
                                  '2012:152:00:00:00')
        return telem


    def _removetimes(self, telem, stat, t1, t2):
        
        # Remove 2011 Safe Mode Data and October NSM
        ind1 = telem.times < ct.DateTime(t1).secs
        ind2 = telem.times > ct.DateTime(t2).secs
        ind = ind1 | ind2
     
        telem.times = telem.times[ind]
        telem.vals = telem.vals[ind]
        if stat:
            #if hasattr(telem, 'maxes'):
            if 'maxes' in telem.__dict__.keys():
                telem.maxes = telem.maxes[ind]
                telem.mins = telem.mins[ind]
                telem.means = telem.means[ind]
                telem.midvals = telem.midvals[ind]

        return telem

    def _gettelemstats(self, data, stat):

        tstart = data.times[0]
        tstop = data.times[-1]
        dt = np.mean(np.double(np.diff(data.times)))

        if stat.lower() == '5min':
            pts = int(round(328 / dt))
        elif stat.lower() == 'daily':
            pts = int(round(86400 / dt))

        if stat:
            # Note this assumes no missing values...
            numintervals = int(len(data.times) / pts)

            timemat = np.reshape(data.times[:numintervals * pts], 
                                 (numintervals, pts))
            valmat = np.reshape(data.vals[:numintervals * pts], 
                                (numintervals, pts))

            meantimes = np.mean(timemat, axis=1)
            meanvals = np.mean(valmat, axis=1)
            minvals = np.min(valmat, axis=1)       
            maxvals = np.max(valmat, axis=1)
            stds = np.std(valmat, axis=1)
            midvals = valmat[:, round(pts/2)]

            returndict = {'times':meantimes, 'means':meanvals, 'mins':minvals,
                          'maxes':maxvals, 'midvals':midvals, 'stds':stds}
            return returndict


    def _getploplotstats(self):
        if 'maxes' in self.telem.__dict__.keys():
            maxval = np.max(self.telem.maxes)
            minval = np.min(self.telem.mins)

        else:
            maxval = np.max(self.telem.vals)
            minval = np.min(self.telem.vals)

        plotmax = np.max(self.telem.plotdata)
        plotmin = np.min(self.telem.plotdata)
        plotmean = np.mean(np.double(self.telem.plotdata))
        plotstd = np.std(np.double(self.telem.plotdata))

        meanval = np.mean(np.double(self.telem.vals))
        stdval = np.std(np.double(self.telem.vals))
        mintime = np.min(self.telem.times)
        maxtime = np.max(self.telem.times)

        # if there is TDB info, throw this in as well
        if 'tdb' in self.telem.__dict__.keys():
            tdb = self.telem.tdb
        else:
            tdb = None

        return {'plotmax':plotmax, 'plotmin':plotmin, 'plotmean':plotmean, 
                'telemmax':maxval, 'telemmin':minval, 'telemmean':meanval,
                'plotstd':plotstd, 'telemstd':stdval, 'mintime':mintime, 
                'maxtime':maxtime, 'tdb':tdb}

