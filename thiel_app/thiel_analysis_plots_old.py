""" This contains Thiel analysis plots """


# TO DO: change all the data to the form dfsim.metric


import px4tools
import numpy as np
import math
import io
import os
import sys
import errno

#import thiel_analysis
from bokeh.io import curdoc,output_file, show
from bokeh.models.widgets import Div
from bokeh.layouts import column
from scipy.interpolate import interp1d

import plotting
from plotted_tables import *
from configured_plots import *
from os.path import dirname, join

from config import *
from helper import *
from leaflet import ulog_to_polyline
from bokeh.models import CheckboxGroup
from bokeh.models import RadioButtonGroup
from bokeh.models.widgets import FileInput
from bokeh.models.widgets import Paragraph

import pandas as pd
import argparse

from bokeh.layouts import column, row
from bokeh.models import ColumnDataSource, PreText, Select
from bokeh.plotting import figure
from bokeh.server.server import Server
from bokeh.themes import Theme
from bokeh.application.handlers import DirectoryHandler


#pylint: disable=cell-var-from-loop, undefined-loop-variable,

DATA_DIR = join(dirname(__file__), 'datalogs')

DEFAULT_FIELDS = ['XY', 'LatLon', 'VxVy']

simname = 'airtonomysim.ulg'
realname = 'airtonomyreal.ulg'
sim_polarity = 1  # determines if we should reverse the Y data
real_polarity = 1
simx_offset = 0
realx_offset = 0
read_file = True
reverse_sim_data = False
reverse_real_data = False
new_data = True

sim_reverse_button = RadioButtonGroup(
        labels=["Sim Default", "Reversed"], active=0)
sim_reverse_button.on_change('active', lambda attr, old, new: reverse_sim())
real_reverse_button = RadioButtonGroup(
        labels=["Real Default", "Reversed"], active=0)
real_reverse_button.on_change('active', lambda attr, old, new: reverse_real())

# set up widgets

stats = PreText(text='Thiel Coefficient', width=500)
# datatype = Select(value='XY', options=DEFAULT_FIELDS)



@lru_cache()
def load_data_sim(simname):
    fname = join(DATA_DIR, simname)
    ulog = load_ulog_file(fname)
    cur_dataset = ulog.get_dataset('vehicle_local_position')
    dfsim = pd.DataFrame(cur_dataset.data)
#    data = pd.read_csv(fname)
    # ulog = ulog.read_ulog(fname)
    # curdata = ulog.get_dataset('vehicle_local_position')
    # dfsim = pd.DataFrame(curdata.data)
#    dfsim = pd.DataFrame(data)
    return dfsim

@lru_cache()
def load_data_real(realname):
    fname = join(DATA_DIR, realname)
    ulog = load_ulog_file(fname)
    cur_dataset = ulog.get_dataset('vehicle_local_position')
    dfreal = pd.DataFrame(cur_dataset.data)
#    data = pd.read_csv(fname)
    # ulog = px4tools.read_ulog(fname)
    # curdata = ulog.get_dataset('vehicle_local_position')
    # dfreal = pd.DataFrame(curdata.data)
 #   select_data.to_numpy()  # convert to a numpy array
#    dfreal = pd.DataFrame(data)
    return dfreal


@lru_cache()
def get_data(simname,realname):
    global select_data
    dfsim = load_data_sim(simname)
    dfreal = load_data_real(realname)
    data = pd.DataFrame() 
    # data = pd.concat([dfsim, dfreal], axis=1)
    # data = data.dropna()   # remove missing values
    # print("Data,y")
    # print (data.y.1)
    # sim_mean = dfsim.y.mean()  # get the average
    # real_mean = dfreal.y.mean()
    # mean_diff = sim_mean - real_mean 
    # data.realy = data.realy + mean_diff # normalize the two
    data['simy'] = dfsim.y
    data['simx'] = dfsim.x
    data['simt'] = dfsim.timestamp
    data['realy'] = dfreal.y
    data['realx'] = dfreal.x
    data['realt'] = dfreal.timestamp

    select_data=np.asarray(data)  # convert to an array for real selection line
#    original_data = copy.deepcopy(data)
    return data

def update(selected=None):
    global read_file, reverse_sim_data, reverse_real_data, new_data, simsource, simsource_static, realsource, realsource_static,original_data, data, data_static, new_data, select_data, select_datadf
    if (read_file):
        original_data = get_data(simname, realname)
        data = copy.deepcopy(original_data)
        data_static = copy.deepcopy(original_data)
        read_file = False
    print("Sim offset", simx_offset)
    print("Real offset", realx_offset)
    if reverse_sim_data:
        data[['simy']] = sim_polarity * original_data[['simy']]  # reverse data if necessary
        data_static[['simy']] = sim_polarity * original_data[['simy']]  # reverse data if necessary
        simsource.data = data
        simsource_static.data = data_static
        simmax = round(max(data[['simy']].values)[0])  # reset the axis scales as appopriate (auto scaling doesn't work)
        simmin = round(min(data[['simy']].values)[0])
        ts1.y_range.start = simmin - abs((simmax-simmin)/10)
        ts1.y_range.end = simmax + abs((simmax-simmin)/10)
        reverse_sim_data = False
    if reverse_real_data:
        data[['realy']] = real_polarity * original_data[['realy']]
        data_static[['realy']] = real_polarity * original_data[['realy']]
        realsource.data = data
        select_datadf[['realy']] = -1 * select_datadf[['realy']]
        realsource_static.data = select_datadf
        realmax = round(max(data[['realy']].values)[0])
        realmin = round(min(data[['realy']].values)[0])
        ts2.y_range.start = realmin - abs((realmax-realmin)/10)
        ts2.y_range.end = realmax + abs((realmax-realmin)/10)
        reverse_real_data = False
    if new_data:
        simsource.data = data[['simx', 'simy','realx','realy']]
        simsource_static.data = data_static[['simx', 'simy','realx','realy']]
        realsource.data = data[['simx', 'simy','realx','realy']]
        select_datadf = pd.DataFrame({'realx': select_data[:, 2], 'realy': select_data[:, 3]})  # convert back to a pandas dataframe     
        realsource_static.data = select_datadf
        new_data = False
#    select_data = copy.deepcopy(tempdata)
    ts1.title.text, ts2.title.text = 'Sim', 'Real'

def upload_new_data_sim(attr, old, new):
    global simname
    decoded = b64decode(new)
    simname = io.BytesIO(decoded)
    update()

def upload_new_data_real(attr, old, new):
    global realname
    decoded = b64decode(new)
    realname = io.BytesIO(decoded)
    update()

def update_stats(data):
    real = np.array(data['realy'])
    sim = np.array(data['simy'])
    sum1 = 0
    sum2 = 0
    sum3 = 0
    for n in range(len(real)):
        sum1 = sum1 + (real[int(n)]-sim[int(n)])**2
        sum2 = sum2 + real[int(n)]**2
        sum3 = sum3 + sim[int(n)]**2
    sum1 = 1/len(real) * sum1
    sum2 = 1/len(real) * sum2
    sum3 = 1/len(real) * sum3
    sum1 = math.sqrt(sum1)
    sum2 = math.sqrt(sum2)
    sum3 = math.sqrt(sum3)
    TIC = sum1/(sum2 + sum3)
    stats.text = 'Thiel coefficient: ' + str(round(TIC,3))


def simselection_change(attrname, old, new):
    global data_static, new_data, realx_offset, realsource_static,select_data
    selected = simsource_static.selected.indices
    if selected:
        seldata = data.iloc[selected, :]
        sorted_data = seldata.sort_values(by=['simx'])
        start = int(sorted_data.values[0][0])
        print("Start =", start)
    if (len(seldata['simx']) != 0):
        for x in range(len(select_data)):
            select_data[x][2] = 0    #zero out the data
            select_data[x][3] = 0
        for x in range(start, (start+len(sorted_data['simx'])-1)):
            tempx = int(sorted_data['realx'][x] + realx_offset - simx_offset)
            select_data[tempx][2] = realsource.data['realx'][tempx]
            select_data[tempx][3] = realsource.data['realy'][tempx]
        update_stats(seldata)
    new_data = True
    update()

def reverse_sim():
    global sim_polarity, reverse_sim_data
    if (sim_reverse_button.active == 1): sim_polarity = -1
    else: sim_polarity = 1
    reverse_sim_data = True
    update()

def reverse_real():
    global real_polarity, reverse_real_data
    if (real_reverse_button.active == 1): real_polarity = -1
    else: real_polarity = 1
    reverse_real_data = True
    update()

def change_sim_scale(shift):
    global simx_offset, new_data
    simx_offset = shift
    new_data = True
    update()

def change_real_scale(shift):
    global realx_offset, new_data
    realx_offset = shift
    new_data = True
    update()



def sim_change(attrname, old, new):
    global metric
    print("Sim change:", new)
    print(dfdata[new])
    metric = new
    update()   

def get_thiel_analysis_plots(ulog, px4_ulog, db_data, vehicle_data, link_to_main_plots):
    global dfdata, simsource, simsource_static, realsource, realsource_static, usimsource, ts1, ts2, x, y
    """
    get all bokeh plots shown on the Thiel analysis page
    :return: list of bokeh plots
    """
    def _resample(time_array, data, desired_time):
        """ resample data at a given time to a vector of desired_time """
        data_f = interp1d(time_array, data, fill_value='extrapolate')
        return data_f(desired_time)


    sim = False
    if link_to_main_plots.find("sim") is not -1:
        temp_link_to_main_plots = link_to_main_plots.replace('sim','')
        sim = True


    if sim:
        print("do some sim stuff")
    else:
        print("do regular stuff")
        page_intro = """
    <p>
    This page shows the correspondance between a simulated and a real flight log.
    </p>
        """
        # curdoc().template_variables['title_html'] = get_heading_html(
        #     ulog, px4_ulog,db_data, None, [('Open Main Plots', link_to_main_plots,)],
        #     'Thiel Analysis') + page_intro
        curdoc().template_variables['title_html'] = get_heading_html(
            ulog, px4_ulog, db_data, None,
            additional_links=[('Open Main Plots', link_to_main_plots,),("Open Matching Simulation Log", '/browse?search=sim')])


        # set up plots

        simsource = ColumnDataSource(data = dict(x=[],y=[]))
        simsource_static = ColumnDataSource(data = dict(x=[],y=[]))
        realsource = ColumnDataSource(data = dict(realx=[],realy=[]))
        realsource_static = ColumnDataSource(data = dict(realx=[],realy=[]))


        cur_dataset = ulog.get_dataset('vehicle_local_position')
        dfdata = pd.DataFrame(cur_dataset.data)
        print(dfdata['x'])        
        keys = []
        data = ulog.data_list
        for d in data:
            data_keys = [f.field_name for f in d.field_data]
            data_keys.remove('timestamp')
        #        print (data_keys)
            keys.append(data_keys)

        t = cur_dataset.data['timestamp']
        x = cur_dataset.data['x']
        y = cur_dataset.data['y']


        usimsource = ColumnDataSource(data=dict(x=t, y=y))
        usimsource_static = ColumnDataSource(data=dict(x=t, y=y))

        simtools = 'xpan,wheel_zoom,xbox_select,reset'
        realtools = 'xpan,wheel_zoom,reset'

        ts1 = figure(plot_width=900, plot_height=200, tools=simtools, x_axis_type='linear', active_drag="xbox_select")
        ts1.line('x', 'y', source=simsource, line_width=2)
        ts1.circle('x', 'y', size=1, source=simsource_static, color=None, selection_color="orange")

        ts2 = figure(plot_width=900, plot_height=200, tools=realtools, x_axis_type='linear')
        # to adjust ranges, add something like this: x_range=Range1d(0, 1000), y_range = None,
        # ts2.x_range = ts1.x_range
        ts2.line('realx', 'realy', source=realsource, line_width=2)
        ts2.circle('realx', 'realy', size=1, source=realsource_static, color="orange")


        plots = []
        flight_mode_changes = get_flight_mode_changes(ulog)
        x_range_offset = (ulog.last_timestamp - ulog.start_timestamp) * 0.05
        x_range = Range1d(ulog.start_timestamp - x_range_offset, ulog.last_timestamp + x_range_offset)

        # cur_dataset = {}
        # cur_dataset = ulog.get_dataset('vehicle_gps_position')

        # # x = cur_dataset.data['vehicle_local_position']
        # # y = cur_dataset.data['y']
        #     # FIXME: bokeh should be able to handle np.nan values properly, but
        # # we still get a ValueError('Out of range float values are not JSON
        # # compliant'), if x or y contains nan
        # non_nan_indexes = np.logical_not(np.logical_or(np.isnan(x), np.isnan(y)))
        # x = x[non_nan_indexes]
        # y = y[non_nan_indexes]

        # if check_if_all_zero:
        #     if np.count_nonzero(x) == 0 and np.count_nonzero(y) == 0:
        #         raise ValueError()

        # data_source = ColumnDataSource(data=dict(x=x, y=y))
        # data_set['timestamp'] = cur_dataset.data['timestamp']

    # plot positions

    #    datatype = Select(value='XY', options=DEFAULT_FIELDS)
        datatype = Select(value='XY', options=keys[0])

        datatype.on_change('value', sim_change)
    

        file_input = FileInput(accept=".ulg")
        file_input.on_change('value', upload_new_data_sim)
        file_input2 = FileInput(accept=".ulg")
        file_input2.on_change('value', upload_new_data_real)

        intro_text = Div(text="""<H2>Sim/Real Thiel Coefficient Calculator</H2>""",width=500, height=100, align="center")
        sim_upload_text = Paragraph(text="Upload a simulator datalog:",width=500, height=15)
        real_upload_text = Paragraph(text="Upload a corresponding real-world datalog:",width=500, height=15)
        choose_field_text = Paragraph(text="Choose a data field to compare:",width=500, height=15)
        #checkbox_group = CheckboxGroup(labels=["x", "y", "vx","vy","lat","lon"], active=[0, 1])

        simsource_static.selected.on_change('indices', simselection_change)


        # The below are in case you want to see the x axis range change as you pan. Poorly documented elsewhere!
        #ts1.x_range.on_change('end', lambda attr, old, new: print ("TS1 X range = ", ts1.x_range.start, ts1.x_range.end))
        #ts2.x_range.on_change('end', lambda attr, old, new: print ("TS2 X range = ", ts2.x_range.start, ts2.x_range.end))

        ts1.x_range.on_change('end', lambda attr, old, new: change_sim_scale(ts1.x_range.start))
        ts2.x_range.on_change('end', lambda attr, old, new: change_real_scale(ts2.x_range.start))

        # set up layout
        widgets = column(datatype,stats)
        sim_button = column(sim_reverse_button)
        real_button = column(real_reverse_button)
        main_row = row(widgets)
        series = column(ts1, sim_button, ts2, real_button)
        layout = column(main_row, series)

        # initialize
        update()
        curdoc().add_root(intro_text)

        curdoc().add_root(sim_upload_text)
        curdoc().add_root(file_input)
        curdoc().add_root(real_upload_text)
        curdoc().add_root(file_input2)
        curdoc().add_root(choose_field_text)    
        curdoc().add_root(layout)
        curdoc().title = "Flight data"
#        plot_config['custom_tools'] = 'xpan,wheel_zoom,xbox_select,reset'
        
        # Local position
        for axis in ['x', 'y', 'z']:
            data_plot = DataPlot(data, plot_config, 'vehicle_local_position',
                                y_axis_label='[m]', title='Local Position '+axis.upper(),
                                plot_height='small', x_range=x_range)
            data_plot.add_graph([axis], colors2[0:1], [axis.upper()+' Estimated'], mark_nan=True)
            data_plot.change_dataset('vehicle_local_position_setpoint')
            data_plot.add_graph([axis], colors2[1:2], [axis.upper()+' Setpoint'],
                                use_step_lines=True)
            plot_flight_modes_background(data_plot, flight_mode_changes)

            if data_plot.finalize() is not None: plots.append(data_plot)
        
        x_range_offset = (ulog.last_timestamp - ulog.start_timestamp) * 0.05
        x_range = Range1d(ulog.start_timestamp - x_range_offset, ulog.last_timestamp + x_range_offset)


    # exchange all DataPlots with the bokeh_plot

    jinja_plot_data = []
    for i in range(len(plots)):
        if plots[i] is None:
            plots[i] = column(param_changes_button, width=int(plot_width * 0.99))
        if isinstance(plots[i], DataPlot):
            if plots[i].param_change_label is not None:
                param_change_labels.append(plots[i].param_change_label)

            plot_title = plots[i].title
            plots[i] = plots[i].bokeh_plot

            fragment = 'Nav-'+plot_title.replace(' ', '-') \
                .replace('&', '_').replace('(', '').replace(')', '')
            jinja_plot_data.append({
                'model_id': plots[i].ref['id'],
                'fragment': fragment,
                'title': plot_title
                })

    curdoc().template_variables['plots'] = jinja_plot_data
    return plots
