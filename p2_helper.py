import numpy as np
import pandas as pd

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px




class Model():
    def __init__(self, pollution_lim=False, sensitivity=False):
        self.constants = {
            # initial values 
            "p0": 100, # pollution 
            "b0": 500, # building
            "c0": 25_000, # coal 
            "s0": 5000, # solar 
            # inflow rates 
            "dels+": 0.3, # solar inflow 
            "delb+": 0.1, # building inflow 
            # outflow rates 
            "dels-": 0.1, # solar outflow 
            "delc-": 0.2, # coal outflow 
            "delb-": 0.05, # building outflow 
            # other params 
            "pi0": 1.2, # pollution intensity 
            "ap": 2500, # pollution threshold 
            "lambda": 2, # pollution decay parameter 
            # initial values for variable rates 
            "u0": 0,
            "d0": 0,
            "ec0": 100, 
            "es0": 500,
            "r0": 1500, 
        }
        self.pollution_lim = pollution_lim
        self.sensitivity = sensitivity


    def init_sim(self,time_steps=10):
        constants = self.constants

        time = np.arange(time_steps)
        init = np.zeros(time_steps)

        # ! ---------- initialize empty dataframes  ----------

        _stocks = {
            "pollution": init,
            "buildings": init,
            "coal": init,
            "solar": init,
        }

        _inflows = {
            "pollution": init,
            "buildings": init,
            "coal": init,
            "solar": init,
        }

        _outflows = {
            "pollution": init,
            "buildings": init,
            "coal": init,
            "solar": init,
        }

        stocks = pd.DataFrame(_stocks)
        inflows = pd.DataFrame(_inflows)
        outflows = pd.DataFrame(_outflows)

        # ! ---------- stocks  ---------- 
        stocks["pollution"][0] = constants["p0"]
        stocks["buildings"][0] = constants["b0"]
        stocks["coal"][0] = constants["c0"]
        stocks["solar"][0] = constants["s0"]


        # ! ----------  inflows ---------- 
        inflows["pollution"][0] =  0 # 3000 when do this => constants["pi0"]*constants["c0"] # TODO check this, in excel, its coal_outflow(t=1), which doesnt make sense # updated from celine 05/15 
        inflows["buildings"][0] = stocks["buildings"][0] * constants["delb+"]
        inflows["coal"][0] = 0
        inflows["solar"][0] = constants["r0"]

        # ! ----------  outflows ---------- 
        outflows["pollution"][0] = 0 
        outflows["buildings"][0] = stocks["buildings"][0] * constants["delb-"]
        outflows["coal"][0] = constants["ec0"]
        outflows["solar"][0] =  constants["es0"]

        #! ------ other ------
        pollution_intensity = init 
        pollution_intensity[0] = constants["pi0"]

        self.inflows = inflows
        self.outflows = outflows
        self.stocks = stocks 
        self.time = time 
        self.pollution_intensity = pollution_intensity

        return 


    def step_sim(self, t=1):
        stocks = self.stocks
        inflows = self.inflows
        outflows = self.outflows
        constants = self.constants
        pollution_intensity = self.pollution_intensity
        
        # ! ---------- stocks  ---------- 
        concerns = ["pollution", "buildings", "coal", "solar"] 
        vals = {}
        for c in concerns:
            vals[c] = stocks[c][t-1]  + inflows[c][t-1] - outflows[c][t-1]

        stocks["pollution"][t] = vals["pollution"]
        stocks["buildings"][t] = vals["buildings"]
        stocks["coal"][t] =  vals["coal"] if vals["coal"] > 0 else 0
        stocks["solar"][t] = vals["solar"] if vals["solar"] > 0 else 0

        # used often for inflows and outflows 
        building_change = stocks["buildings"][t] - stocks["buildings"][t-1]

        # ! ----------  inflows ---------- 
        # pollution, increases as coal is depleted, 
        coal_change = np.abs(stocks["coal"][t] - stocks["coal"][t-1])
        coal_init = stocks["coal"][0]

        # pollition intensity dependent on coal use
        pollution_intensity[t] = pollution_intensity[t - 1 ] ** (1 + coal_change/coal_init)

        # pollution => pol. intensity * coal use 
        if self.pollution_lim:
            # if coal is depleted, then no more pollution inflows with pollution limit consideration 
            inflows["pollution"][t] = pollution_intensity[t-1] * outflows["coal"][t-1] if stocks["coal"][t] > 0 else 0 
        else: 
            inflows["pollution"][t] = pollution_intensity[t-1] * outflows["coal"][t-1]

        # buildings
        inflows["buildings"][t] = stocks["buildings"][t] * constants["delb+"] if stocks["pollution"][t] < constants["ap"] else 0 

        # coal -> non-renewable resource, so no inflows 
        inflows["coal"][t] = 0

        # solar -> renwable resource dependent on number of buildings 
        # limit on density : stocks["buildings"][t] < min_buildings 
        min_buildings = 3 * stocks["buildings"][0] 
        building_dif = stocks["buildings"][t] - min_buildings # < 0   
        # different conditions based on density 
        increasing_inflow = inflows["solar"][t-1] + constants["dels+"]* (building_change) 
        decreasing_inflow = inflows["solar"][t-1] * (1 - ( building_dif/min_buildings)) if stocks["solar"][t] > 0 else 0
        # have increasing inflows of solar unless buildings are too dense 
        inflows["solar"][t] = increasing_inflow if building_dif < 0 else decreasing_inflow


        # ! ----------  outflows ---------- 
        outflows["pollution"][t] = stocks["pollution"][t] * np.exp(-1 * constants["lambda"])

        outflows["buildings"][t] =  constants["delb-"] * stocks["buildings"][t]

        out_coal_t =  outflows["coal"][t-1] + constants["delc-"]*(building_change) 
        outflows["coal"][t] =  out_coal_t if stocks["coal"][t] > 0 else 0

        outflows["solar"][t] = outflows["solar"][t-1] + building_change * constants["dels-"] #if stocks["solar"][t] > 0 else 0

        if self.sensitivity:
            # if run out of coal, and we have sufficient solar resource, then use 2x rate of solar resouce 
            if stocks["coal"][t] <= 0:
                outflows["solar"][t] = outflows["solar"][t-1] + building_change * 2 * constants["dels-"] if stocks["solar"][t] > 0 else 0


        self.inflows = inflows
        self.outflows = outflows
        self.stocks = stocks 

        return 


    def run_sim(self, time_steps=10):
        # print(f"pollution lim = {self.pollution_lim}")
        # initialize simulation with a given number of time_steps 
        self.init_sim(time_steps)

        # run the simulation 
        for t in self.time[1:]:
            self.step_sim(t)
        return 


    def print_values(self):
        print(f"stocks \n {self.stocks}")
        print(f"in \n {self.inflows}")
        print(f"out \n {self.outflows}")



    def plot_sim(self, log=False, first_legend=True):
        results = [self.stocks, self.inflows, self.outflows]
        fig = make_subplots(rows=1, cols=3, shared_xaxes=True, subplot_titles=("Stocks", "Inflows", "Outflows"))

        colors = list(px.colors.qualitative.Plotly)

        for ix, df in enumerate(results):
            show_legend_bool = True if ix == 0 else first_legend
            cnt = 0
            for col in df:
                fig.add_trace(go.Scatter(
                    x=self.time,
                    y=df[col], 
                    mode='lines',
                    marker_color=colors[cnt],
                    name=col,
                    showlegend=show_legend_bool,
                ), row=1, col=ix+1, )

                if log:
                    fig.update_yaxes(type="log")

                cnt+=1
        return fig 
        