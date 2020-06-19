import re
import os
import sys
import numpy as np
import matplotlib.pyplot as plt
import matplotlib as mpl
from matplotlib.ticker import AutoMinorLocator
from copy import deepcopy
import pprint

import Ska
import Ska.engarchive.fetch_eng as fetch
import Chandra.Time as ct

import gretafun
import dechelper
import decplotdata

plt.rcParams['xtick.major.pad'] = '10'

#
def debug(locals):
    import code
    code.interact(local=locals)

class plotdec(object):
    ''' Use the GRETA dec file to produce enhanced orbit plots.

    Add more description here

    Time period must be more than one day, preferably more than two, due to
    how daily stats are calculated (specifically daily means)
    '''

    def __init__(self, decfile, time1=None, time2=None, fgcolor=[1,1,1],
                 bgcolor=[0.15, 0.15, 0.15], orientation='landscape',
                 plotltt=False):

        self.decfile = decfile
        self.decplots = gretafun.parsedecplot(self.decfile)
        self.colors = self._importcolors()
        self.plotltt = plotltt
        self.ltttimespan = 365 * 24 * 3600
        self.defaultcolors = ['RED', 'YELLOW', 'GREEN', 'AQUA', 'PINK', 'WHEAT',
                              'GREY', 'BROWN', 'BLUE', 'BLUEVIOLET', 'CYAN',
                              'TURQUIOSE', 'MAGENTA', 'SALMON', 'WHITE']
        self.plotinfo = {'bgcolor':bgcolor,
                         'fgcolor':fgcolor,
                         'top':0.88,
                         'wspace':None,
                         'hspace':0.3,
                         'binarylocation':[None]*self.decplots['numplots']}
        if orientation.lower() == 'landscape':
            sizeparam =  {'width':18,
                          'height':10,
                          'left':0.05,
                          'bottom':0.05,
                          'right':0.78,
                          'stampfontsize':10,
                          'datefontsize':10,
                          'statsfontsize':8,
                          'statsvscalefact':1.3,
                          'lttspace':0.2}
        else:
            sizeparam =  {'width':8.5,
                          'height':11,
                          'left':0.07,
                          'bottom':0.05,
                          'right':0.69,
                          'stampfontsize':6,
                          'datefontsize':6,
                          'statsfontsize':6,
                          'statsvscalefact':1.1,
                          'lttspace':0.2}
        self.plotinfo.update(sizeparam)
        self.plotinfo['location'] = self._getplotloc()
        self._addbinaryplotloc()

        if plotltt:
            self._addlttsplots()
            
        if time2:
            self.time2 = ct.DateTime(time2).date
        else:
            self.time2 = ct.DateTime().date

        if time1:
            self.time1 = ct.DateTime(time1).date
        else:
            self.time1 = ct.DateTime(ct.DateTime(time2).secs - 10*24*3600).date

        self._plotfigure()
        plt.draw()

    def _addlttsplots(self):
        ''' Make space for LTT plots on the left.

        This fills out the location array for all LTT plots based on the 
        number of plots.
        '''
        
        self.plotinfo['lttslocation'] = deepcopy(self.plotinfo['location'])
        for loc in self.plotinfo['lttslocation']:
            loc[0] = self.plotinfo['left']
            loc[2] = self.plotinfo['lttspace']
        

    def _getplotloc(self):
        ''' Generate the location and sizing for all primary plots.

        This does not include LTT and binary plots, Binary and LTT plot sizing
        are defined in another function. This function will shift the primary 
        plots to make room for LTT plots if LTT plots are requested.
        '''
        numplots = self.decplots['numplots']
        hspace = self.plotinfo['hspace']
        top = self.plotinfo['top']
        bottom = self.plotinfo['bottom']
        wspace = self.plotinfo['wspace']
        right = self.plotinfo['right']

        if self.plotltt:
            left = self.plotinfo['left'] + self.plotinfo['lttspace'] + 0.05
        else:
            left = self.plotinfo['left']
        
        # Spacing between each plot is a fraction of the available space for
        # each plot
        spacing = hspace * (top - bottom) / numplots

        # Total available space to plot stuff / number of plots
        plotspace = (top - bottom - spacing * (numplots - 1)) / numplots

        plotloc = []
        for n in range(numplots - 1, -1, -1):
            # Origin and size of each plot
            # [x, y, width, height]
            plotloc.append([left, bottom + plotspace * n + spacing * n,
                            right - left, plotspace])

        return plotloc
    

    def _addbinaryplotloc(self):
        ''' Define location and sizing for binary plots.

        This is intended to mimic the binary plotting capabilities included 
        in GRETA. The addition of binary data should decrease the size of the 
        primary plot.
        '''

        # these two are in the figure coordinate system
        baseheight = 0.01 # Height without any traces yet
        traceheight = 0.007 # Amount to add for each trace

        # Step through each plot
        for p in list(self.decplots['plots'].keys()):

            # if the binary plot key doesn't have a NoneType
            if self.decplots['plots'][p]['PBILEVELS']:
                
                # This is the number of binary traces for a particular plot
                # You could get this number either from PBILEVELS or just
                # counting the number of keys as is done below.
                numtbtraces = len(self.decplots['plots'][p]['tbtraces'].keys())

                # Total height for the binary trace plot (fits under regular
                # plot, which is required)
                totalheight = baseheight + traceheight * numtbtraces

                # Copy over the primary plot parameters
                binaryloc = deepcopy(self.plotinfo['location'][p])

                # Only need to change the height, and then make room by
                # modifying/shrinking the primary plot
                binaryloc[3] = totalheight
                self.plotinfo['location'][p][1] = \
                                  self.plotinfo['location'][p][1] + totalheight
                self.plotinfo['location'][p][3] = \
                                  self.plotinfo['location'][p][3] - totalheight

                # Copy over the new binary plot parameters
                self.plotinfo['binarylocation'][p] = binaryloc


    def _importcolors(self):
        ''' Return a dictionary of colors along with their hex and RGB values'''

        filename = '/home/mdahmer/Library/Python/FlightTools/flighttools/colors.csv'
        fields = ['color','hex','r','g','b']
        colorarray = np.genfromtxt(filename, delimiter=',', dtype=None, names=fields,
                               comments=None)
        colordict = {}
        
        for (name,hexval,r,g,b) in colorarray:

            name = name.decode('utf-8')
            hexval = hexval.decode('utf-8')
            
            if r > 1 or g > 1 or b > 1:
                r = r/255.0
                g = g/255.0
                b = b/255.0
                
            colordict[name] = {'hex':hexval, 'rgb':[r,g,b]}

        return colordict
    

    def _getcolor(self, tcolor=None, tracenum=0):
        if isinstance(tcolor, type(None)):
            tcolor = self.defaultcolors[tracenum]
        elif tcolor.lower() in list(self.colors.keys()):
            tcolor = self.colors[tcolor.lower()]['rgb']
        else:
            tcolor = self.defaultcolors[tracenum]
        return tcolor


    def _generategrid(self, ax):
        #ax.xaxis.set_minor_locator(AutoMinorLocator())
        #ax.yaxis.set_minor_locator(AutoMinorLocator())
        #ax.tick_params(axis='both', which='minor', length=6, color=[0.8, 0.8, 0.8])
        ax.grid(b=True, which='both', color=self.plotinfo['fgcolor'])
        ax.set_facecolor(self.plotinfo['bgcolor'])
        ax.set_axisbelow(True)

    
    def _generatelegend(self, ax, plotnum):
        bbox_to_anchor = (0, 1, 1, 0.03)

        numtraces = len(self.decplots['plots'][plotnum]['traces'].keys())
        leg = ax.legend(bbox_to_anchor=bbox_to_anchor, loc=8, ncol=numtraces,
                                     mode="expand", prop= {'size':10},
                                     borderaxespad=0.,handletextpad=0.1)
        frame  = leg.get_frame()  
        frame.set_facecolor(self.plotinfo['bgcolor'])

        for t in leg.get_texts():
            t.set_fontsize(self.plotinfo['statsfontsize'])
            t.set_color(self.plotinfo['fgcolor'])


    def _configurexaxis(self, ax, plotnum, t1=None, t2=None, numticks=11):
        ''' Define x axis ticks.

        Only plots tick marks, date labels are plotted separately

        '''

        if not t1:
            t1 = ct.DateTime(self.time1).secs

        if not t2:
            t2 = ct.DateTime(self.time2).secs

        # Generate a list of tick mark locations, the corresponding labels will
        # empty strings, the actual date labels are only plotted at the bottom
        # in the figure coordinate system, not the axis coordinate system.
        xtik = np.linspace(t1, t2, numticks)

        xlab = ['']

        ax.set_xticks(xtik)
        ax.set_xticklabels(xlab)

        ax.set_xlim(t1, t2)


    def _plotdatelabels(self, plotloc, t1=None, t2=None, numticks=11, 
                        lttplot=False):
        ''' Define x axis labels/ticks.

        This plots the time stamps manually as annotations in the figure 
        coordinate system. This should be plotted in the figure coordinate
        system to avoid conflicts with binary plots. If the bottom plot
        includes a binary plot, the primary plot axis can't be used to show
        the axis labels (the binary plot will cover these labels). Rather 
        than writing the logic to place the labels in one plot function or 
        another, and to remember the right vertical location for plotting
        the LTT date labels, the date label function is kept separate.

        '''

        if not t1:
            t1 = ct.DateTime(self.time1).secs

        if not t2:
            t2 = ct.DateTime(self.time2).secs

        # Vertical location of date labels
        yloc = plotloc[1] - 0.01

        # Generate a list of tick mark locations, the corresponding labels will
        # either include date stamps, or empty strings so that only the bottom 
        # plot shows the dates.
        xtik = np.linspace(t1, t2, numticks)

        # Generate date labels
        xlabels = ct.DateTime(xtik).date
        xlabels = [name[:8] + ' \n' + name[9:17] + ' ' for name in xlabels]

        # Generate version of xtik in axis coordinate system
        xtik_ax = np.linspace(0, 1, numticks)

        # Convert axes x coordinate to figure coordinate system
        #
        # new x = axes ratio / axes width in fig coord. + axes left coord.
        if lttplot:
            xtik_fig = [x_ax * self.plotinfo['lttspace'] + 
                        self.plotinfo['left'] for x_ax in xtik_ax]
        else:
            xtik_fig = [x_ax * plotloc[2] + plotloc[0] for x_ax in xtik_ax]
            

        for xloc, xlab in zip(xtik_fig, xlabels):
            self.fig.text(xloc, yloc, xlab, ha="center", va="top",
                          size=self.plotinfo['datefontsize'],
                          color=self.plotinfo['fgcolor'])


   
    def _configureyaxis(self, ax, tracestats=None):
       
        ax.tick_params(axis='y', labelsize=10,
                       labelcolor=self.plotinfo['fgcolor'],
                       color=self.plotinfo['fgcolor'])
        if tracestats:

            miny = 1e6
            maxy = -1e6
            for statkey in tracestats:
                miny = np.min((miny, tracestats[statkey].plotmin))
                maxy = np.max((maxy, tracestats[statkey].plotmax))
        else:
            miny = 0
            maxy = 1
        
        miny = miny - (maxy - miny) * 0.05
        maxy = maxy + (maxy - miny) * 0.05
        ax.set_ylim(miny, maxy)
        

    def _writestats(self, tracestats, plotnum):

        # Find longest msid name string
        longest = 9 # minimum width
        for stat in list(tracestats.keys()):
            longest = np.max((longest, len(tracestats[stat].name[4:])))

        msidpad = longest + 1
        stringconstructor = '%' + str(msidpad) + 's%9s%9s%10s%10s\n'

        text = stringconstructor%('', 'Trending', 'Trending', '', 'Max This')
        text = text + stringconstructor%('Trace', 'Caution', 'Caution', 'Prior',
                                             'Time')
        text = text + stringconstructor%('Name', 'Low', 'High', 'Year Max',
                                             'Period')
        text = text + '\n'

        for name in list(tracestats.keys()):
            if name[:3] == 'stt':
                if 'glimmonlimits' in tracestats[name].__dict__.keys():
                    if 'caution_low' in list(tracestats[name].glimmonlimits.keys()):
                        cautionlow = str(tracestats[name].glimmonlimits\
                                         ['caution_low'])
                        cautionhigh = str(tracestats[name].glimmonlimits\
                                          ['caution_high'])
                    else:
                        cautionlow = 'None'
                        cautionhigh = 'None'                    
                else:
                    cautionlow = 'None'
                    cautionhigh = 'None'

                # Most yearly data will have maxes, since only the daily statistics
                # are fetched (to save memory). Some yearly data, such as heater
                # state data need to be queried at full resolution so that the
                # daily statistics can be manually calculated. If this data is
                # manually calculated, then the data is not stored in the maxes,
                # instead it is merely stored in the yeartelem.plotdata attribute.
                lttname = 'ltt' + name[3:]
                if lttname in list(tracestats.keys()):
                    yearmax = str('%10.5f'%tracestats[lttname].telemmax)
                else:
                    yearmax = 'None'

                # Recent data is not based on statistics so it will not likely have
                # a 'maxes' attribute
                recentmax = tracestats[name].telemmax   
                maxplotted = str('%10.5f'%recentmax)
                
                text = text + stringconstructor%(name[4:], cautionlow, cautionhigh,
                                                 yearmax, maxplotted)

        xloc = self.plotinfo['right'] + 0.01
        yloc = self.plotinfo['location'][plotnum][1] + \
               self.plotinfo['location'][plotnum][3] + 0.02
        
        stats = self.fig.text(xloc, yloc, text, ha="left", va="top",
                             size=self.plotinfo['statsfontsize'],
                             family='monospace', color=self.plotinfo['fgcolor'])


    def _getplotdata(self, plotnum, tracenum, time1=None, 
                     fetchstat=None, plotstat=None, binaryplot=False):

        # Figure out what the MSID name is
        if binaryplot:
            tmsid = self.decplots['plots'][plotnum]['tbtraces'][tracenum]['TMSID']
            tcalc = None
            tstat = None
        else:
            tmsid = self.decplots['plots'][plotnum]['traces'][tracenum]['TMSID']
            tcalc = self.decplots['plots'][plotnum]['traces'][tracenum]['TCALC']
            tstat = self.decplots['plots'][plotnum]['traces'][tracenum]['TSTAT']

        # If no initial time is specified, use the initial time passed to 
        # this class. Remember you can't use self to initialize another 
        # keyword in the function definition above.
        if not time1:
            time1 = self.time1

        if tcalc:
            name = tcalc
        elif tmsid:
            name = tmsid
        else:
            raise ValueError("MSID name missing")

        # if plotstat is currently None, and the decfile included a tstat, use
        # the stat calculation requested by tstat
        if (not plotstat) and tstat:
            plotstat=tstat

        telem = None
        tracedata = None
        try:
            tracedata = decplotdata.plotdata(name, time1, self.time2, 
                                             plotstat=tstat, 
                                             fetchstat=fetchstat)
            telem = tracedata.telem
            del tracedata.telem

        except ValueError as e:
            # debug(locals())
            print('Empty plot.')
            print('Returned Error (in self._plotaxis): %s'%e)

        return telem, tracedata


    def _plotaxis(self, plotnum):

        # Define attributes to keywords to simplify
        bgcolor = self.plotinfo['bgcolor']
        fgcolor = self.plotinfo['fgcolor']
        ax = self.axlist[plotnum]

        # Add title and other plot info at this level
        ax.set_title(self.decplots['plots'][plotnum]['PTITLE'], fontsize=12,
                     color=fgcolor, position=[0.5, 1.15])


        tracestats = {}
        for tracenum in list(self.decplots['plots'][plotnum]['traces'].keys()):

            telem, tracedata = self._getplotdata(plotnum, tracenum)


            # Plot the data if telem (and tracestats) were defined
            if telem:
        
                tracestats['stt_' + tracedata.name] = tracedata

                # Define color to use
                tcolor = self.decplots['plots'][plotnum]['traces'][tracenum]\
                                      ['TCOLOR']
                tcolor = self._getcolor(tcolor=tcolor, tracenum=tracenum)        
        
                ax.plot(telem.plottimes, telem.plotdata, color=tcolor, 
                        label=tracedata.name, linewidth=1)  
                plt.draw()

    

        # Add Y label
        ax.set_ylabel(self.decplots['plots'][0]['PYLABEL'],
                      color=self.plotinfo['fgcolor'])

        # Configure y axis
        self._configureyaxis(ax, tracestats=tracestats)

        # Configure x axis
        self._configurexaxis(ax, plotnum)

        # Configure legend if data exists
        if tracestats:

            # Configure legend
            self._generatelegend(ax, plotnum)


        # Add a grid
        self._generategrid(ax)

        return tracestats




    def _plotlttaxis(self, plotnum):

        # Define attributes to keywords to simplify
        bgcolor = self.plotinfo['bgcolor']
        fgcolor = self.plotinfo['fgcolor']
        ax = self.axlist[plotnum]
        lttax = self.lttaxlist[plotnum]

        lttax.set_title('Long Term Trends', fontsize=12, color=fgcolor,
                        position=[0.5, 1.01])

        tracestats = {}
        for tracenum in list(self.decplots['plots'][plotnum]['traces'].keys()):

            tstat = self.decplots['plots'][plotnum]['traces'][tracenum]['TSTAT']
            
            oneyearago = ct.DateTime(self.time2).secs - self.ltttimespan
            oneyearago = ct.DateTime(oneyearago).date
            telem, tracedata = self._getplotdata(plotnum, tracenum, 
                                                  time1=oneyearago,
                                                  fetchstat='daily')

            # Plot the data
            if telem:

                tracestats['ltt_' + tracedata.name] = tracedata
        
                # Define color to use
                tcolor = self.decplots['plots'][plotnum]['traces'][tracenum]\
                                      ['TCOLOR']
                tcolor = self._getcolor(tcolor=tcolor, tracenum=tracenum)      

                # When plotting the LTTs, disregard the plottimes and 
                # plotdata, instead plot the mins-to-maxes for each day,
                # unles this is a state based MSID or if a particular stat
                # was requested, in which case you want to use the plottimes 
                # and plotdata.
                if (telem.type == 'state') or tstat:
                    # Generate the trace data from the means
                    plottimes = telem.plottimes
                    plotdata = telem.plotdata
                else:
                    # Generate the trace data from the mins and maxes
                    plottimes = np.array(list(zip(telem.times, telem.times + 1)))
                    plottimes = plottimes.flatten()     
                    plotdata = np.array(list(zip(telem.mins, telem.maxes)))
                    plotdata = plotdata.flatten()

                lttax.plot(plottimes, plotdata, color=tcolor, 
                           label=tracedata.name, linewidth=1)  
            
            time1secs = ct.DateTime(self.time1).secs
            time2secs = ct.DateTime(self.time2).secs
            lttax.axvspan(time1secs, time2secs, color=[.6, .6, .6], alpha=0.2)

            t1 = ct.DateTime(self.time2).secs - self.ltttimespan
            self._configurexaxis(lttax, plotnum, t1=t1, numticks=2)        
        
        #
        # This was moved to the figure level function, since it requires info 
        # from both the short term and long term plots/axes.
        #
        #if tracestats:
        #    
            # Configure y axes for both primary and ltt plots to be equal
            # self._configureyaxis(lttax, tracestats=tracestats)
            # self._configureyaxis(ax, tracestats=tracestats)

        self._generategrid(lttax)

        return tracestats





    def _plotbinaryaxis(self, plotnum):

        bgcolor = self.plotinfo['bgcolor']
        fgcolor = self.plotinfo['fgcolor']
        bax = self.baxlist[plotnum]
        ax = self.axlist[plotnum]

        msidkey = {}
        for tbtracenum in list(self.decplots['plots'][plotnum]['tbtraces'].keys()):

            # Fetch telemetry and return name of MSID/Data
            tbtelem, tbtracedata = self._getplotdata(plotnum, tbtracenum, 
                                                     binaryplot=True)

            offval = tbtracenum * 2
            onval = offval + 1
            
            # First set all the values to stepped up off value
            bin = np.array([offval] * len(tbtelem.vals))

            # Then set all the on values to the stepped up on value
            bin[tbtelem.vals == 1] = onval  

            # Plot the data
            if tbtelem:
        
                # Define color to use
                tcolor = self.decplots['plots'][plotnum]['tbtraces']\
                                      [tbtracenum]['TCOLOR']
                tcolor = self._getcolor(tcolor=tcolor, tracenum=tbtracenum)        


                bax.plot(tbtelem.times, bin, color=tcolor, 
                         label=tbtracedata.name, linewidth=1)

                msidkey[tbtracenum] = tbtracedata.msid



        # Configure the y axis labels for the binary data (heater
        # states)

        bax.set_xticklabels('')
        bax.set_xlim(tbtracedata.mintime - 360, tbtracedata.maxtime + 360)

        # Configure binary trace y axis
        ymaxlim =  np.max(list(msidkey.keys())) * 2
        ytick = range(0, ymaxlim + 2, 2)
        ylab = [''] * len(ytick)
        for n in msidkey.keys():
            ylab[n] = msidkey[n]

        bax.set_ylim(-1, ymaxlim+3)
        bax.set_yticks(ytick)
        bax.set_yticklabels(ylab, fontsize=6, color=self.plotinfo['fgcolor'])
        bax.tick_params(axis='y', which='major', length=6, direction='out',
                        color=[0.8, 0.8, 0.8])

        # Reposition title since the reshaping of the figure affects
        # the y scaling of where the title is located.
        ax.set_title(self.decplots['plots'][plotnum]['PTITLE'], fontsize=12,
                     color=fgcolor, position=[0.5, 1.2])                




    def _plotfigure(self):
        
        # Define figure attributes to keywords to simplify
        bgcolor = self.plotinfo['bgcolor']
        fgcolor = self.plotinfo['fgcolor']
        figsize = (self.plotinfo['width'], self.plotinfo['height'])
        

        # Create figure
        plt.rc('axes', edgecolor=fgcolor)
        fig = plt.figure(figsize=figsize, facecolor=bgcolor)
        self.fig = fig


        #---------------------------------------------------------------------
        # Figure Annotations

        # Create title and subtitle
        pagetitle = fig.text(0.5, 0.98, self.decplots['DTITLE'], ha="center",
                             va="center", size=14, color=fgcolor)
        pagesubtitle = fig.text(0.5, 0.96, self.decplots['DSUBTITLE'], 
                                ha="center", va="center", size=12, 
                                color=fgcolor)

        # Create source file info (for upper lefthand corner)
        decname = 'Filename: %s\n'%os.path.basename(self.decfile)
        timeperiod = 'Date Range: %s to \n            %s\n'%(self.time1,
                                                            self.time2)
        generated = 'Generated: %s\n'%ct.DateTime().date
        datasource = 'From: Engineering Telemetry Archive'

        sourceinfo = fig.text(0.01, 0.99, decname + timeperiod + generated +
                              datasource, ha="left", va="top",
                              size=self.plotinfo['stampfontsize'],
                              family='monospace', color=fgcolor)


        #---------------------------------------------------------------------
        # Axis Handle Placeholders

        # Create empty axes lists for the primary axis, the binary sub
        # axes (in case they are required), and LTT axes.
        self.axlist = [None for n in range(self.decplots['numplots'])]

        self.baxlist = [None for n in range(self.decplots['numplots'])]

        if self.plotltt:
            self.lttaxlist = [None for n in range(self.decplots['numplots'])]
        

        #---------------------------------------------------------------------
        # Main loop for generating all plots 

        for plotnum in np.sort(list(self.decplots['plots'].keys())):

            print('plot %d = %s'%(plotnum,
                                  self.decplots['plots'][plotnum]['PTITLE']))
            

            # Create Main Axes
            plotloc = self.plotinfo['location'][plotnum]
            self.axlist[plotnum] = fig.add_axes(plotloc, facecolor=bgcolor)


            # Create Primary Plots
            tracestats = self._plotaxis(plotnum)


            # Configure y axes for primary plot
            self._configureyaxis(self.axlist[plotnum], tracestats=tracestats)


            if self.plotltt:
                lttplotloc = self.plotinfo['lttslocation'][plotnum]
                self.lttaxlist[plotnum] = fig.add_axes(lttplotloc, facecolor=bgcolor)
                
                ltttracestats = self._plotlttaxis(plotnum)

                if ltttracestats:
                    # Use the LTT stats, this will be used to scale the y axes.
                    # It is assumed that the LTT plot will include the primary
                    # plot data, so the LTT stats (extrema) can be used 
                    # instead.
                    tracestats.update(ltttracestats)

                # Configure y axes for both primary and ltt plots to be equal
                self._configureyaxis(self.axlist[plotnum], 
                                     tracestats=tracestats)
                self._configureyaxis(self.lttaxlist[plotnum], 
                                     tracestats=tracestats)


            # Create binary axes if defined (i.e. if it isn't None)
            if self.plotinfo['binarylocation'][plotnum]:
                binaryplotloc = self.plotinfo['binarylocation'][plotnum]
                bincolor = axisbg=self.plotinfo['bgcolor']
                self.baxlist[plotnum] = fig.add_axes(binaryplotloc, 
                                                     axisbg=bincolor)

                self._plotbinaryaxis(plotnum)



            # Write the stats text for the current plot to the right of the 
            # plot.
            self._writestats(tracestats, plotnum)

            
        # Plot date labels in figure coordinate system
        #
        # plotloc should correspond to the bottom plot
        if self.plotinfo['binarylocation'][plotnum]:
            self._plotdatelabels(binaryplotloc)
        else:
            self._plotdatelabels(plotloc)

        if self.plotltt:
            lttstart = ct.DateTime(self.time2).secs - self.ltttimespan
            self._plotdatelabels(plotloc, t1=lttstart, t2=None, numticks=2, 
                                 lttplot=True)

        # # Format the date axis
        # fig.autofmt_xdate(rotation=0, ha='center')


        #---------------------------------------------------------------------
        # Save the plot to a file

        basename = os.path.basename(self.decfile).split('.')[0]

        t1 = ct.DateTime(self.time1).greta
        t2 = ct.DateTime(self.time2).greta
        
        filename = os.getcwd()+'/' + basename + '_' +t1 + '-' + t2 + '.png'

        fig.savefig(filename, facecolor=self.plotinfo['bgcolor'],
                    edgecolor=self.plotinfo['bgcolor'])

        print('Saved plot to %s'%filename)

               
        # Add ability to manually adjust y axis

