import numpy as np
import pandas as pd
import os, json, time, getpass
from ast import literal_eval
from copy import deepcopy
import pyperclip
import dash
import plotly.express as px
import plotly.graph_objs as go
import dash_bootstrap_components as dbc
from dash import Input, Output, dcc, html, dash_table, State
from dash.dash_table.Format import Format, Scheme
import dash_ag_grid as dag
import dash_mantine_components as dmc
from datetime import date, datetime, timedelta

from OptionQuantLibClientAPI import *
import yfinance as yf

percentage1 = dash_table.FormatTemplate.percentage(1)
percentage2 = dash_table.FormatTemplate.percentage(2)
precision2 = Format(precision=2)
precision4 = Format(precision=4)
mthList = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
curveGridStrikes = np.array([0.01 + i*0.01 for i in range(200)])
volGridStrikes = np.array([0.1, 0.25, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 1, 1.05, 1.1, 1.2, 1.3, 1.4, 1.5, 1.75, 2])
yaxis_range = [0, 1]
xaxis_range = [0, 2]

# fetch database
underlyingDatabase = fetch_underlyingDatabase()
#calendars = list(set([v["Calendar"] for k,v in underlyingDatabase.items()]))
expiryCalendars = list(set([v["Calendar"]+"_"+v["Type"] for k,v in underlyingDatabase.items()]))
listedMaturities = {ec:get_listedMaturity(96, ec)["maturities"] for ec in expiryCalendars}

# load user config
useBBGData = 0
if os.path.exists("UserConfig.json"):
    with open("UserConfig.json", "r") as f:
        userConfig = json.load(f)
    useBBGData = userConfig["BBGData"]

# helper functions
def toDate(string, dateFormat="%Y-%m-%d"):
    
    return datetime.strptime(string, dateFormat)

def toDateStr(datetimeObj, dateFormat="%Y-%m-%d"):
    
    return datetime.strftime(datetimeObj, dateFormat)

def toDisplayDate(dateStr):

    dt = datetime.strptime(dateStr, "%Y-%m-%d")
    return dt.strftime("%d-%b-%y")

def toSystemDate2(dateStr):

    if len(dateStr) < 9:
        dateStr = "0"+dateStr

    dt = datetime.strptime(dateStr, "%d-%b-%y")
    return dt.strftime("%Y-%m-%d")

def sortDictByValue(d):

    return {k: v for k, v in sorted(d.items(), key=lambda item: item[1])}

def sortDictByKey(d):

    return {k: d[k] for k in sorted(d)}

def sign(x):
    
    if x >= 0:
        return 1
    else:
        return -1

def getTwoClosestValuesFromList(ref, lst):
    
    if ref <= lst[0]:
        return lst[0], lst[0]
    elif ref >= lst[-1]:
        return lst[-1], lst[-1]
    else:
        i = 0
        while ref > lst[i]:
            i += 1
            
        return lst[i-1], lst[i]
    
def toDisplayDate(dateStr):

    dt = datetime.strptime(dateStr, "%Y-%m-%d")
    return datetime.strftime(dt, "%d-%b-%y")

def toSystemDate(dateStr):

    try:
        if "/" in dateStr:
            dt = datetime.strptime(dateStr, "%m/%d/%y")
        else:
            for m in mthList:
                if m in dateStr.lower():
                    dt = datetime.strptime(dateStr, "%d-%b-%y")
                    break
            else:
                dt = datetime.strptime(dateStr, "%Y-%m-%d")


        return datetime.strftime(dt, "%Y-%m-%d")
    
    except:

        return "Error in date string"

def extractMaturityFromContractSymbol(symbol):
    
    start = 0
    for i in range(len(symbol)):
        if symbol[i].isnumeric() == True:
            start = i
            break
                
    dateStr = symbol[i:i+6]
    datetimeObj = datetime.strptime(dateStr, "%y%m%d")
    return toDateStr(datetimeObj)
    
def extractOptionTypeFromContractSymbol(symbol):
    
    start = 0
    for i in range(len(symbol)):
        if symbol[i].isnumeric() == True:
            start = i
            break
                
    return symbol[i+6]

def retrieveOptionChain(undlName: str):
    
    ticker = yf.Ticker(get_OBB(undlName))
    maturities = ticker.options
    if len(maturities) == 0:
        return []
    
    dfs = []
    for m in maturities:
        data = ticker.option_chain(m)
        dfs.append(data.calls)
        dfs.append(data.puts)
        
    df = pd.concat(dfs)
    spotRef = get_spot(undlName, delay=15)[undlName]
    
    df["spotRef"] = [spotRef for _ in range(len(df))]
    vd = get_exchangeDate(get_calendar(undlName))
    df["valueDate"] = [vd for _ in range(len(df))]
    style = get_listedExerciseType(undlName)
    df["optionStyle"] = [style for _ in range(len(df))]
    
    # filter very old options
    df["lastTradeDate"] = df["lastTradeDate"].apply(lambda x: str(x)[:10])
    #refDate = (datetime.strptime(get_exchangeDate(get_calendar(undlName)), "%Y-%m-%d") + timedelta(days=-5)).strftime("%Y-%m-%d")
    refDate = get_nextBusinessDay(get_exchangeDate(get_calendar(undlName)), dayShift=-3, calendar=get_calendar(undlName))
    if "error" in refDate.keys():
        return None
    
    df = df[df["lastTradeDate"] > refDate["date"]]

    df = df.fillna(0)
    
    return df

def processOptionChainRawData(undlName, df):

    if df is None:
        return None

    if len(df) == 0:
        return None
    
    df["maturity"] = df["contractSymbol"].apply(extractMaturityFromContractSymbol)
    df["optionType"] = df["contractSymbol"].apply(extractOptionTypeFromContractSymbol)
    
    maturities = sorted(set(df["maturity"]))
    optionChainData = {"undlName": undlName, "spotRef": df["spotRef"].values[0], "optionChain": []}
    
    for maturity in maturities:
        df_sub = df[df["maturity"]==maturity]
        
        for i in range(len(df_sub)):
            strike = df_sub["strike"].values[i]
            spotRef = df_sub["spotRef"].values[i]
            optionType = df_sub["optionType"].values[i]
            valueDate = df_sub["valueDate"].values[i]
            optionStyle = df_sub["optionStyle"].values[i]
            bid = df_sub["bid"].values[i]
            ask = df_sub["ask"].values[i]
            
            data = {"maturity": maturity, "strike": strike, "optionType": optionType, "optionStyle": optionStyle,
                   "valueDate": valueDate, "bid": bid, "ask": ask}
            
            optionChainData["optionChain"].append(data)
            
    return optionChainData

def checkDividendTableInput(data):

    def checkValidDateStr(mStr):

        try:
            if len(mStr) < 9:
                d = datetime.strptime("0"+mStr, "%d-%b-%y").strftime("%Y-%m-%d")
            else:
                d = datetime.strptime(mStr, "%d-%b-%y").strftime("%Y-%m-%d")
            return True
        except Exception as e:
            return False
        
    def checkFloat(nStr):

        try:
            a = float(nStr)
            return True
        except:
            return False

    try:
        for line in data.split("\r\n"):
            data = line.split("\t")
            if data[0] != "Date" and data[0] != "":
                if checkValidDateStr(data[0]) == False:
                    return False

                if checkFloat(data[1]) == False:
                    return False
            
                if data[2] not in ["Normal", "Forecast", ""]:
                    return False
            
        return True
    except:

        return False

# market data functions
def getHKEXDivFuture(code):
    
    if code == "DHH":
        url = "https://www1.hkex.com.hk/hkexwidget/data/getderivativesfutures?lang=eng&token=evLtsLsBNAUVTPxtGqVeGwy9J646tNfnaPwFVw3xNEXWA9iAynOrHP/OiSSivHGc&ats=DHH&type=0&qid=1682927480247&callback=jQuery35106080067934701374_1682927478205&_=1682927478209"
    elif code == "DHS":
        url = "https://www1.hkex.com.hk/hkexwidget/data/getderivativesfutures?lang=eng&token=evLtsLsBNAUVTPxtGqVeG/7rBj38l30esewRjUBCU99D0JHtBorLDm4km1BGN9LH&ats=DHS&type=0&qid=1682929308948&callback=jQuery351005460122779005161_1682929306878&_=1682929306883"
    else:
        return {"error": "invalid code"}
        
    result = requests.get(url)
    
    start = result.text.find("(")
    
    result = literal_eval(result.text[start+1:-1])
    
    try:
        divFutDict = {}
        for d in result["data"]["futureslist"]:
            divFutDict[d["ric"]] = {"bid": d["bd"], "ask": d["as"]}
            
        return divFutDict
    except Exception as e:
        return {"error": str(e)}

SIDEBAR_STYLE = {
    "position": "fixed",
    "top": 0,
    "left": 0,
    "bottom": 0,
    "width": "21rem",
    "padding": "2rem 1rem",
    "background-color": "#f8f9fa",
}

CONTENT_STYLE = {
    "margin-left": "21rem",
    "margin-right": "2rem",
    "padding": "2rem 1rem",
}

tableUdlInfo = dag.AgGrid(id="tableUndlInfo",
                          rowData=[],
                          columnDefs=[{"field": "Field", "minWidth": 110, "maxWidth": 110, "pinned": "left"}, 
                                      {"field": "Value", "maxWidth": 160, "minWidth": 160, "editable": False}], 
                          columnSize="autoSize",
                          className="ag-theme-balham ag-theme-custom",
                          dashGridOptions={"rowHeight": 30},
                          style={"width": 300, "height": 340, "margin-top": "0px", "margin-bottom": "25px"})

tableMarketDataCheck = dag.AgGrid(id="tableMarketDataCheck",
                          rowData=[],
                          columnDefs=[{"field": "Data", "minWidth": 160, "maxWidth": 160, "pinned": "left"}, 
                                      {"field": "Check", "maxWidth": 110, "minWidth": 110, "editable": False,
                                       "cellStyle": {"styleConditions": [{"condition": "params.value == 'Missing'", "style": {"color": "red"}}], 
                                                     "defaultStyle": {"color": "black"}},}], 
                          columnSize="autoSize",
                          className="ag-theme-balham ag-theme-custom",
                          dashGridOptions={"rowHeight": 30},
                          style={"width": 300, "height": 220, "margin-top": "10px"})

sidebar = html.Div(
    [   
        dcc.ConfirmDialog(id="confirm-fetchDB", message="Database fetched"), 
        dcc.Store(id="memory"),
        html.Div([
            html.Div([html.H4("Market Data Manager", className="display-8", style={"margin-bottom": "20px"}), 
                  dbc.Button("Undl DB", id="button-undlDB", outline=True, color="primary", href="/addUndlName", n_clicks=0, className="me-2"),
                  dbc.Button("Fetch DB", id="button-fetchDB", outline=True, color="primary", n_clicks=0, className="me-2"),
                  dbc.Button("Setting", id="button-setting", outline=True, color="primary", href="/setting", n_clicks=0, className="me-2")]),
            html.Hr(),
            html.Div([dcc.Dropdown(sorted(list(underlyingDatabase.keys())), id='undlName-dropdown', placeholder="Underlying", style={'color': '#999999'})]),
            html.H6(""),
            dbc.Nav(
                [
                    dbc.NavLink("Home", href="/", active="exact"),
                    dbc.NavLink("Forward", href="/forward", active="exact"),
                    dbc.NavLink("Volatility", href="/volatility", active="exact"),
                ],
                vertical=False,
                pills=True
            ),
            html.H4(" "),
            html.Hr(),
            html.H4(" "),
            html.Div([html.H6("    Underlying Info"), tableUdlInfo, html.H4(" "), html.H6("    Underlying Data Check"), tableMarketDataCheck]),
            html.Div([html.H6(id="text-checkRate"), html.H6(id="text-checkDiv")]),
            html.Div(html.H6(" "), style={"height": "100px", "width": "100%"}),
            html.Div([dcc.Loading([dcc.Store(id='memory-vol'), dcc.Store(id='memory-fwd')], type="default", color="#466590")], style={"width": "100%"}),
        ], style={"height": "88vh", "width": "100%"}),
        #html.Div(html.H6(" "), style={"height": "440px", "width": "100%"}),
        html.Div(
            [
                dbc.Button("Other Market Data", id="button-otherMarketData", outline=True, color="primary", 
                           href="/otherMarketData", n_clicks=0, className="me-2", style={"width": "100%", "margin-top": "5px", "margin-bottom": "5px"}),
                dbc.Button("Vol Sur Fit Batch", id="button-VSFSetting", outline=True, color="primary", 
                           href="/vsfsetting", n_clicks=0, className="me-2", style={"width": "100%", "margin-top": "5px", "margin-bottom": "5px"})
            ]
        ),
    ],
    style=SIDEBAR_STYLE,
)

modalAddMaturity = dbc.Modal(
    [
        dbc.ModalHeader(dbc.ModalTitle("Add Maturity to SVI-JW Params")),
        dbc.ModalBody([dbc.Input(id="input-addMat", placeholder="e.g. 2023-06-16", type="text"),
                       html.H6(""),
                       html.H6("", id="message-modal")]),
        dbc.ModalFooter([dbc.Button("Add", id="add-modal-addMat", className="me-2", outline=True, color="info", n_clicks=0),
                         dbc.Button("Close", id="close-modal-addMat", className="me-2", outline=True, color="info", n_clicks=0)])
    ],
    id="modal-addMat",
    centered=True,
    is_open=False
)

modalLoadRef = dbc.Modal(
    [
        dbc.ModalHeader(dbc.ModalTitle("Load reference surface")),
        dbc.ModalBody([dcc.Dropdown(sorted(list(underlyingDatabase.keys())), id='modal-undlName-dropdown', placeholder="Underlying", style={'color': '#999999', "width": 200}),
                       html.H6(" "),
                       dcc.DatePickerSingle(id='date-picker-loadRef', 
                                            min_date_allowed=date(1989, 5, 21), 
                                            max_date_allowed=datetime.now().date(), 
                                            initial_visible_month=datetime.now().date(),
                                            date=datetime.now().date(),
                                            display_format='YYYY-MM-DD'),
                       html.H6(""),
                       html.H6("", id="message-modal-loadRef")]),
        dbc.ModalFooter([dbc.Button("Load", id="button-modal-load", className="me-2", outline=True, color="info", n_clicks=0),
                         dbc.Button("Close", id="button-modal-close", className="me-2", outline=True, color="info", n_clicks=0)])
    ],
    id="modal-loadRef",
    centered=True,
    is_open=False
)
modalLoadOptionChain = dbc.Modal(
    [
        dbc.ModalHeader(dbc.ModalTitle("Option chain data load type")),
        dbc.ModalBody([dcc.Dropdown(["Live"], id='modal-volData-dropdown', value="Live", style={'color': '#999999', "width": 250}),
                       html.H6(" ")]),
        dbc.ModalFooter([dbc.Button("Load", id="button-modal-loadOptionChain", className="me-2", outline=True, color="info", n_clicks=0),
                         dbc.Button("Close", id="button-modal-closeOptionChain", className="me-2", outline=True, color="info", n_clicks=0)])
    ],
    id="modal-loadOptionChain",
    centered=True,
    is_open=False
)

modalForecastDiv = dbc.Modal(
    [
        dbc.ModalHeader(dbc.ModalTitle("Forecast Dividend")),
        dbc.ModalBody([
            html.H6("Number of years to forecast: "),
            dcc.Input(id="forecastYear", placeholder="e.g. 8"),
            html.H6(" "),
            html.H6("Div growth factor: "),
            dcc.Input(id="divGrowFactor", placeholder="e.g. 0.9"),
            html.H6(" "),
            html.H6(" ")
        ]),
        dbc.ModalFooter([dbc.Button("Fit Growth Factor", id="button-fitDivGrowFactor", className="me-2", outline=True, color="info", n_clicks=0),
                         dbc.Button("Forecast", id="button-modal-forecastDiv", className="me-2", outline=True, color="info", n_clicks=0),
                         dbc.Button("Close", id="button-modal-closeforecastDiv", className="me-2", outline=True, color="info", n_clicks=0)])
    ],
    id = "modal-forecastDiv",
    centered=True,
    is_open=False
)

def createDivSwapNForward(memoryData):

    undlName = memoryData["undlName"]
    spotRef = memoryData["spotRef"]
    div = memoryData["div"]
    repo = memoryData["repo"]
    rate = get_yieldCurve(get_CCY(undlName))
    calendar = get_calendar(undlName)
    undlType = get_undlType(undlName)
    valueDate = memoryData["valueDate"]

    marketDataParams = {"yieldCurve": rate, "divCurve": div, "repoCurve": repo, "calendar": calendar}

    df_div = pd.DataFrame.from_dict({"Date": list(div["Schedule"].keys()), 
                                     "Value": [v["value"] for v in div["Schedule"].values()], 
                                     "Type": [v["type"] for v in div["Schedule"].values()]})
    
    df_repo = pd.DataFrame.from_dict({"Date": list(repo["Schedule"].keys()), 
                                      "Value": list(repo["Schedule"].values())})
    
    df_divSwap = getDivSwapFromDivPanel(div, spotRef)

    maturities = listedMaturities[calendar+"_"+undlType]
    forwards = [calc_forward(spotRef, m, marketDataParams, valueDate)["forward"] for m in maturities]
    df_fwd = pd.DataFrame.from_dict({"Maturity": maturities, "Forward": forwards, "Forward %": np.array(forwards) / spotRef})

    return df_divSwap, df_fwd

def createUndlNameInfoRowData(undlName):

    ric = get_RIC(undlName)
    bbg = get_BBG(undlName)
    obb = get_OBB(undlName)
    symbol = get_symbol(undlName)
    undlType = get_undlType(undlName)
    exchange = get_exchange(undlName)
    calendar = get_calendar(undlName)
    ccy = get_CCY(undlName)
    dvdccy = get_DVDCCY(undlName)
    listedExerciseType = get_listedExerciseType(undlName)
    dataCheck = True

    rowDataUndlInfo = [{"Field": "RIC Code", "Value": ric if ric != None else ""},
                       {"Field": "BBG Code", "Value": bbg if bbg != None else ""},
                       {"Field": "OBB Code", "Value": obb if obb != None else ""},
                       {"Field": "Symbol", "Value": symbol if symbol != None else ""},
                       {"Field": "Type", "Value": undlType if undlType != None else ""},
                       {"Field": "Exchange", "Value": exchange if exchange != None else ""},
                       {"Field": "Calendar", "Value": calendar if calendar != None else ""},
                       {"Field": "Currency", "Value": ccy if ccy != None else ""},
                       {"Field": "Dvd Currency", "Value": dvdccy if dvdccy != None else ""},
                       {"Field": "ETO Exercise", "Value": listedExerciseType if listedExerciseType != None else ""}]
    

    rowDataMarketDataCheck = [{"Data": "Yield Curve", "Check": ""},
                                  {"Data": "Dividend", "Check": ""},
                                  {"Data": "Repo", "Check": ""},
                                  {"Data": "Listed Maturity Rule", "Check": ""},
                                  {"Data": "Holiday Calendar", "Check": ""},
                                  {"Data": "Time Zone", "Check": ""},]
    if undlName != None:
        if ccy != None: 
            rate = get_yieldCurve(ccy)
        div = get_dividend(undlName)
        repo = get_repo(undlName)
        listedCheck = False
        if calendar+"_"+undlType in listedMaturities.keys():
            if listedMaturities[calendar+"_"+undlType] != None:
                listedCheck = True
        if calendar != None: 
            holidayCalendar = get_holidayCalendar(calendar)
            timeZone = get_exchangeTimeZone(calendar)
            if timeZone is not None:
                if timeZone > 0:
                    timeZone = "+" + str(timeZone)
                else:
                    timeZone = str(timeZone)
    
        rowDataMarketDataCheck = [{"Data": "Yield Curve", "Check": "True" if rate != None else "Missing"},
                                  {"Data": "Dividend", "Check": "True" if div["Schedule"] != {} else "No Div"},
                                  {"Data": "Repo", "Check": "True" if repo["Schedule"] != {} else "No Repo"},
                                  {"Data": "Listed Maturity Rule", "Check": "True" if listedCheck == True else "Missing"},
                                  {"Data": "Holiday Calendar", "Check": "True" if holidayCalendar != None else "Missing"},
                                  {"Data": "Time Zone", "Check": "GMT " + timeZone if timeZone != None else "Missing"},]
        
        if rate is None or listedCheck == False or holidayCalendar is None or timeZone is None:
            dataCheck = False

    return rowDataUndlInfo, rowDataMarketDataCheck, dataCheck

def createContentAddUndl(undlName=None):

    topBar = html.Div([html.Div([dbc.Button("Load", id="button-loadUndlName", outline=True, color="danger", className="me-2", n_clicks=0),
                                 dbc.Button("Save", id="button-saveUndlName", outline=True, color="danger", className="me-2", n_clicks=0),
                                 dbc.Button("Clear", id="button-clearUndlName", outline=True, color="danger", className="me-2", n_clicks=0),
                                 dbc.Button("Delete", id="button-delUndlName", outline=True, color="danger", className="me-2", n_clicks=0)], style={'display': 'inline-block'}),
                        html.H6(" "),
                        html.Div("Status:", id="text-undlNamePageStatus"),
                        html.Hr()])
    
    if undlName is None:
        page = html.Div([html.H6("RIC Code:"), dcc.Input(id="ric", placeholder="e.g. AAPL.OQ"), html.H6(" "),
                         html.H6("BBG Code:"), dcc.Input(id="bbg", placeholder="e.g. AAPL UQ Equity"), html.H6(" "),
                         html.H6("OBB Code (Optional):"), dcc.Input(id="obb", placeholder="e.g. AAPL"), html.H6(" "),
                         html.H6("Symbol (Optional):"), dcc.Input(id="symbol", placeholder="e.g. AAPL"), html.H6(" "),
                         html.H6("Type:"), dcc.Input(id="type", placeholder="e.g. Stock"), html.H6(" "),
                         html.H6("Exchange Calendar/Time Zone:"), dcc.Input(id="calendar", placeholder="e.g. NASDAQ"), html.H6(" "),
                         html.H6("Currency:"), dcc.Input(id="ccy", placeholder="e.g. USD"), html.H6(" "),
                         html.H6("Dividend Currency:"), dcc.Input(id="dvdccy", placeholder="e.g. USD"), html.H6(" "),
                         html.H6("Listed Option Exercise Type (None for no ETO):"), dcc.Input(id="ETOExercise", placeholder="e.g. American"), html.H6(" ")], style={'display': 'inline-block'})
    else:
        page = html.Div([html.H6("RIC Code:"), dcc.Input(id="ric", value=get_RIC(undlName)), html.H6(" "),
                         html.H6("BBG Code:"), dcc.Input(id="bbg", value=get_BBG(undlName)), html.H6(" "),
                         html.H6("OBB Code (Optional):"), dcc.Input(id="obb", value=get_OBB(undlName)), html.H6(" "),
                         html.H6("Symbol (Optional):"), dcc.Input(id="symbol", value=get_symbol(undlName)), html.H6(" "),
                         html.H6("Type:"), dcc.Input(id="type", value=get_undlType(undlName)), html.H6(" "),
                         html.H6("Exchange Calendar/Time Zone:"), dcc.Input(id="calendar", value=get_calendar(undlName)), html.H6(" "),
                         html.H6("Currency:"), dcc.Input(id="ccy", value=get_CCY(undlName)), html.H6(" "),
                         html.H6("Dividend Currency:"), dcc.Input(id="dvdccy", value=get_DVDCCY(undlName)), html.H6(" "),
                         html.H6("Listed Option Exercise Type (None for no ETO):"), dcc.Input(id="ETOExercise", value=get_listedExerciseType(undlName)), html.H6(" ")], style={'display': 'inline-block'})
    
    return html.Div([dcc.ConfirmDialog(id="confirm-saveUndl", message="Confirm saving underlying info?"),
                     dcc.ConfirmDialog(id="confirm-delUndl", message="Confirm deleting underlying?"), 
                     topBar, 
                     page])

def createContentSetting():

    topBar = html.Div([html.Div([dbc.Button("Load", id="button-loadSetting", outline=True, color="danger", className="me-2", n_clicks=0),
                                 dbc.Button("Save", id="button-saveSetting", outline=True, color="danger", className="me-2", n_clicks=0)], style={'display': 'inline-block'}),
                        html.H6(" "),
                        html.Div("Status:", id="text-settingPageStatus"),
                        html.Hr()])
    
    useBBGData = 0
    if os.path.exists("UserConfig.json"):
        with open("UserConfig.json", "r") as f:
            data = json.load(f)
        useBBGData = data["BBGData"]
   
    page = html.Div([html.H6("Enable Bloomgberg Data:"), 
                     dcc.Dropdown(["True", "False"], value="True" if useBBGData == 1 else "False", id='dropdown-BBGData', style={'color': '#999999'}),
                     html.H6(" "),
                     ], style={'display': 'inline-block'})
    
    return html.Div([dcc.ConfirmDialog(id="confirm-saveSetting", message="Confirm saving setting?"),
                     topBar, 
                     page])

def createContentOtherMarketData():

    topBar = html.Div([html.Div([dbc.Button("Yield Curve", id="button-downloadYieldCurve", outline=True, color="info", className="me-2", n_clicks=0),
                                 dcc.Download(id="downloadYieldCurve"),
                                 dbc.Button("Time Zone", id="button-downloadTimeZone", outline=True, color="info", className="me-2", n_clicks=0),
                                 dcc.Download(id="downloadTimeZone"),
                                 dbc.Button("Holiday Calendar", id="button-downloadHolidayCalendar", outline=True, color="info", className="me-2", n_clicks=0),
                                 dcc.Download(id="downloadHolidayCalendar"),
                                 dbc.Button("Listed Maturity Rule", id="button-downloadListedMaturityRule", outline=True, color="info", className="me-2", n_clicks=0),
                                 dcc.Download(id="downloadListedMaturityRule"),], 
                                 style={'display': 'inline-block'}),
                        html.H6(" "),
                        #html.Div("Status:", id="text-settingPageStatus"),
                        html.Hr()])
    
    return html.Div([topBar])

def createContentVSFBatch():

    topBar = html.Div([html.Div([dbc.Button("Load", id="button-loadVSFBatch", outline=True, color="danger", className="me-2", n_clicks=0),
                                 dbc.Button("Save", id="button-saveVSFBatch", outline=True, color="danger", className="me-2", n_clicks=0)], style={'display': 'inline-block'}),
                        html.H6(" "),
                        html.Div("Status:", id="text-VSFPageStatus"),
                        html.Hr()])
    
    #with open("VolSurFit_batch/config.json", "r") as f:
    #    VSFConfig = json.load(f)
    VSFConfig = get_VSFBatchConfig()
    
    rowData = []
    for undlName,setting in VSFConfig.items():
        rowData.append({"Underlying": undlName, 
                        "Vol Model": setting["volModel"], 
                        "Save Fitted Forward": setting["saveFittedForward"],
                        "Fit Type": "Full Params Surface Fitting"})

    rowData += [{"Underlying": "", "Vol Model": "", "Fit Repo": "", "Fit Type": ""} for _ in range(10)]

    tableVSF = dag.AgGrid(id="table-VSF",
                          rowData=rowData,
                                columnDefs=[{"field": "Underlying", "minWidth": 150, "maxWidth": 150, "pinned": "left", "editable": True},
                                            {"field": "Vol Model", "maxWidth": 150, "minWidth": 150, "editable": True, "resizable": False,
                                             "cellEditor": "agSelectCellEditor",
                                             "cellEditorParams": {"values": ["SVI-JW", "SVI-S", "SVI-SPX", ""]},
                                             "singleClickEdit": True},
                                             {"field": "Save Fitted Forward", "maxWidth": 175, "minWidth": 175, "editable": True, "resizable": False,
                                             "cellEditor": "agSelectCellEditor",
                                             "cellEditorParams": {"values": ["Dividend", "Repo", "None"]},
                                             "singleClickEdit": True},
                                            {"field": "Fit Type", "maxWidth": 325, "minWidth": 325, "editable": True, "resizable": False}],
                                columnSize="autoSize",
                                className="ag-theme-balham ag-theme-custom",
                                dashGridOptions={"rowHeight": 30},
                                style={"width": 1025, "height": 800})

    page = html.Div([tableVSF])
    
    return html.Div([topBar, page])

def getDivSwapFromDivPanel(divPanel: float, spotRef: float):

    currentYear = get_exchangeDate(calendar=get_calendar(divPanel["undlName"])).split("-")[0]

    divSwap ={}
    for k,v in divPanel["Schedule"].items():
        year = k.split("-")[0]
        if year >= currentYear:
            if year not in divSwap.keys(): divSwap[year] = 0
            divSwap[year] += (0 if v["value"] == "" else float(v["value"]))

    divSwap = {k: round(v, 4) for k,v in divSwap.items()}
    df_divSwap = pd.DataFrame.from_dict({"Year": list(divSwap.keys()), 
                                         "Points": list(divSwap.values()), 
                                         "Yield": np.array(list(divSwap.values()))/spotRef})

    return df_divSwap

def surfaceToDf(volSurfaceSVI, tag="SVI-JW"):

    if volSurfaceSVI == None: 
        if tag == "SVI-JW": 
            return pd.DataFrame.from_dict({"Maturity": [], "Vol": [], "Skew": [], "PWing": [], "CWing": [], "MinVol": [], "Tau": [], "Forward": []})
        elif tag == "SVI-S":
            return pd.DataFrame.from_dict({"Params": ["Short Term", "Long Term", "Strength"], "Vol": [0.2, 0.2, 1], "Skew": [-0.1,-0.1,1], "Convex": [1, 1, 1]})
        elif tag == "SVI-SPX":
            return pd.DataFrame.from_dict({"Maturity": [], "Vol": [], "Skew": [], "PWing": [], "CWing": [], "MinVol": [],
                                           "Loc": [], "W": [], "Tau": [], "Forward": []})

    if tag == "SVI-JW":

        paramsDict = volSurfaceSVI[tag]
        dates = []
        vols = []
        skews = []
        pWings = []
        cWings = []
        minVols = []
        taus = []
        forwards = []
        for k,v in paramsDict.items():
            dates.append(k)
            vols.append(v["vol"])
            skews.append(v["skew"])
            pWings.append(v["pWing"])
            cWings.append(v["cWing"])
            minVols.append(v["minVol"])
            taus.append(v["tau"])
            forwards.append(v["forward"])

        return pd.DataFrame.from_dict({"Maturity": dates, "Vol": vols, "Skew": skews, "PWing": pWings, "CWing": cWings, "MinVol": minVols, "Tau": taus, "Forward": forwards})
    
    elif tag == "SVI-S":

        SVISDf = pd.DataFrame.from_dict({"Params": ["Short Term", "Long Term", "Strength"], 
                                     "Vol": np.array(list(volSurfaceSVI["SVI-S"]["vol"].values())) * 100, 
                                     "Skew": list(volSurfaceSVI["SVI-S"]["skew"].values()), 
                                     "Convex": list(volSurfaceSVI["SVI-S"]["convex"].values())})        
        
        return SVISDf
    
    elif tag == "SVI-SPX":

        paramsDict = volSurfaceSVI[tag]
        dates = []
        vols = []
        skews = []
        pWings = []
        cWings = []
        minVols = []
        locs = []
        ws = []
        taus = []
        forwards = []
        
        for k,v in paramsDict.items():
            dates.append(k)
            vols.append(v["vol"])
            skews.append(v["skew"])
            pWings.append(v["pWing"])
            cWings.append(v["cWing"])
            minVols.append(v["minVol"])
            locs.append(v["loc"])
            ws.append(v["w"])
            taus.append(v["tau"])
            forwards.append(v["forward"])

        return pd.DataFrame.from_dict({"Maturity": dates, "Vol": vols, "Skew": skews, "PWing": pWings, "CWing": cWings, "MinVol": minVols, 
                                       "Loc": locs, "W": ws, "Tau": taus, "Forward": forwards})

def dataToSurface(data):

    surface = {d["Maturity"]:{"vol": float(d["Vol"]), 
                              "skew": float(d["Skew"]), 
                              "pWing": float(d["PWing"]), 
                              "cWing": float(d["CWing"]), 
                              "minVol": float(d["MinVol"]), 
                              "tau": float(d["Tau"]), 
                              "forward": float(d["Forward"])} for d in data}
    return surface

def SVIS(refDate, st, lt, strength, anchorDate=None):
    
    if anchorDate is None:
        myAnchorDate = datetime.now()
    else:
        myAnchorDate = datetime.strptime(anchorDate, "%Y-%m-%d")
        
    myRefDate = datetime.strptime(refDate, "%Y-%m-%d")
    
    l1 = (myRefDate - myAnchorDate).days
    l2 = (myAnchorDate + timedelta(days=365*10) - myRefDate).days
    
    return (st*l2 + lt*(l1**strength)) / (l1**strength+l2)

def SVISToSVIJW(paramsSVIS, maturities):

    undlName = paramsSVIS["undlName"]
    anchorDate = paramsSVIS["anchorDate"]
    anchor = paramsSVIS["anchor"]
    calendar = get_calendar(undlName)
    businessDaysYear = get_netBusinessDays(anchorDate, datetime.strftime(datetime.strptime(anchorDate, "%Y-%m-%d")+timedelta(365), "%Y-%m-%d"), calendar)["days"]
    marketDataParams = {"yieldCurve": get_yieldCurve(get_CCY(undlName)),
                        "divCurve": get_dividend(undlName),
                        "repoCurve": get_repo(undlName),
                        "calendar": get_calendar(undlName)}
    

    SVIJW = {}
    for maturity in maturities:
        SVIJW[maturity] = {}

        vol = SVIS(maturity, 
                   paramsSVIS["SVI-S"]["vol"]["st"], 
                   paramsSVIS["SVI-S"]["vol"]["lt"], 
                   paramsSVIS["SVI-S"]["vol"]["strength"], 
                   anchorDate)
        
        skew = SVIS(maturity, 
                    paramsSVIS["SVI-S"]["skew"]["st"] if round(paramsSVIS["SVI-S"]["skew"]["st"], 4) != 0 else -0.0001, 
                    paramsSVIS["SVI-S"]["skew"]["lt"] if round(paramsSVIS["SVI-S"]["skew"]["lt"], 4) != 0 else -0.0001, 
                    paramsSVIS["SVI-S"]["skew"]["strength"], 
                    anchorDate)
        
        convex = SVIS(maturity, 
                      paramsSVIS["SVI-S"]["convex"]["st"] if round(paramsSVIS["SVI-S"]["convex"]["st"], 4) !=0 else 0.001, 
                      paramsSVIS["SVI-S"]["convex"]["lt"] if round(paramsSVIS["SVI-S"]["convex"]["lt"], 4) != 0 else 0.001, 
                      paramsSVIS["SVI-S"]["convex"]["strength"], 
                      anchorDate)
        
        pWing = convex / 2 - skew 
        cWing = convex / 2 + skew
        minVol = vol * 4 * pWing * cWing / (pWing+cWing)**2

        SVIJW[maturity]["vol"] = vol
        SVIJW[maturity]["skew"] = skew
        SVIJW[maturity]["pWing"] = pWing
        SVIJW[maturity]["cWing"] = cWing
        SVIJW[maturity]["minVol"] = minVol
        SVIJW[maturity]["tau"] = get_netBusinessDays(anchorDate, maturity, calendar)["days"] / businessDaysYear
        SVIJW[maturity]["forward"] = calc_forward(anchor, maturity, marketDataParams, anchorDate)["forward"] / anchor

    paramsSVIJW = {"undlName": undlName, 
                   "anchor": anchor, 
                   "anchorDate": anchorDate,
                   "lastUpdate": os.getlogin(),
                   "lastUpdateTime": datetime.strftime(datetime.now(), "%Y-%m-%dT%H:%M:%S"),
                   "SVI-S": paramsSVIS["SVI-S"],
                   "SVI-JW": SVIJW}
    
    return paramsSVIJW

def genVolGrid(volSurfaceSVI, volTag, spotRef, maturities, strikes=None, returnType="df", historicalDate=None):

    undlName = volSurfaceSVI["undlName"]

    if strikes is None:
        strikes = volGridStrikes

    if volSurfaceSVI[volTag] == {}:
        volGridDict = {}
        gridDf = pd.DataFrame.from_dict(mergeDict({"Maturity": []}, {str(round(k*100))+"%":[volGridDict[m][k] for m in []] for k in strikes}))
    else:
        
        try:
            volGridDict = get_volGrid(undlName, maturities, strikes * spotRef, volSurfaceSVI=volSurfaceSVI, historicalDate=historicalDate)
        except:
            volGridDict = {m:{k:0 for k in strikes * spotRef} for m in maturities}
        volGridDict = {m:{round(float(k)/spotRef, 2):v for k,v in s.items()} for m, s in volGridDict.items()}
        gridDf = pd.DataFrame.from_dict(mergeDict({"Maturity": maturities}, {str(round(k*100))+"%":[volGridDict[m][round(k, 2)] for m in maturities] for k in strikes}))  

    if returnType == "df":
        return gridDf
    else:
        return volGridDict

def displayVolArb(volSurfaceSVI, volTag, spotRef, maturities, checkGrid, strikes=None):

    if strikes is None:
        strikes = volGridStrikes

    anchor = volSurfaceSVI["anchor"]
    result = {k:[] for k in strikes}
    for maturity, slice in checkGrid.items():
        for k,v in slice.items():
            if v == 0:
                refStrike = k * volSurfaceSVI[volTag][maturity]["forward"] * anchor / spotRef
                k1, k2 = getTwoClosestValuesFromList(refStrike, strikes)

                result[k1].append(maturities.index(maturity))
                result[k2].append(maturities.index(maturity))

    for maturity in maturities:
        if maturity not in checkGrid.keys():
            m1, m2 = getTwoClosestValuesFromList(maturity, maturities)
            key1 = maturities.index(m1)
            key2 = maturities.index(m2)
            for k in strikes:
                if key1 in result[k] and key2 in result[k]:
                    result[k].append(maturities.index(maturity))
    #result[maturity] = sorted(list(set(result[maturity])))
    result = {k:sorted(set(list(v))) for k,v in result.items()}    

    columnDefs=[{"field": "Maturity", "maxWidth": 120}] + \
                [{"field": str(round(k*100))+"%", 
                  "valueFormatter": {"function": "d3.format(',.1%')(params.value)"}, 
                  "cellStyle": {"styleConditions": [{"condition": "params.node.id == " + str(idx), "style": {"background-color": "red"}} for idx in result[k]], 
                                "defaultStyle": {"background-color": None}},
                  "maxWidth": 80,
                  "type": "numericColumn"} for k in strikes]

    return columnDefs

def getOptionImpliedDiv(repoFitted, spotRef, div=None, repo=None):

    undlName = repoFitted["undlName"]
    refDate = get_exchangeDate(get_calendar(undlName))
    yieldCurve = get_yieldCurve(get_CCY(undlName))
    if div is None:
        div = deepcopy(get_dividend(undlName)["Schedule"])
    else:
        div = deepcopy(div["Schedule"])

    if repo is None:
        repoRef = get_repo(undlName)
    else:
        repoRef = deepcopy(repo)
    calendar = get_calendar(undlName)
    businessDaysYear = get_netBusinessDays(refDate, datetime.strftime(toDate(refDate)+timedelta(days=365), "%Y-%m-%d"), calendar)["days"]
    
    systemDivPoints = {}
    impliedDivPoints = {}
    totalSystemDiv = 0
    totalDiv = 0
    for maturity, repo in repoFitted["Schedule"].items():

        businessDaysTenor = get_netBusinessDays(refDate, maturity, calendar)["days"]
        tau = businessDaysTenor / businessDaysYear

        divCurve = {k:v["value"] for k,v in div.items() 
                    if ((k>refDate) and (k<=maturity))}

        system = sum([v for d,v in divCurve.items()]) 
        repoRateSystem = get_repoRate(undlName, maturity, repoCurve=repoRef)
        systemDivPoints[maturity] = system - totalSystemDiv
        impliedDivPoints[maturity] = system + spotRef*(repo-repoRateSystem)*tau - totalDiv

        totalSystemDiv = system
        totalDiv = system + spotRef*(repo-repoRateSystem)*tau

    return systemDivPoints, impliedDivPoints

def createContentVolatility(undlName: str, memoryData: dict, dataCheck: bool=True):

    if undlName is None: return html.Div([html.H4("Please select underlying")]), memoryData

    if dataCheck == False: return html.Div([html.H4("Missing Market Data")]), memoryData

    # check if current undlName is same as memory data, else clear memory data
    if memoryData != None:
        if memoryData["undlName"] != undlName:
            memoryData = None
        elif "SVI-JW" in memoryData["volSurfaceSVI"].keys():
            if memoryData["volSurfaceSVI"]["SVI-JW"]== {}:
                memoryData = None
        elif "SVI-SPX" in memoryData["volSurfaceSVI"].keys():
            if memoryData["volSurfaceSVI"]["SVI-SPX"] == {}:
                memoryData = None

    # get undl info
    undlName = get_systemName(undlName)
    spotData = get_spot(undlName)
    if "error" in spotData.keys(): return html.Div([html.H4("Fail to get underlying spot")]), memoryData
    spotRef = spotData[undlName] if memoryData is None else memoryData["spotRef"]
    volSurfaceSVI = get_volSurfaceSVI(undlName) if memoryData is None else memoryData["volSurfaceSVI"]

    if volSurfaceSVI is None:
        paramsSVIS = None
    elif "SVI-S" in volSurfaceSVI:
        paramsSVIS = {"undlName": undlName,
                      "anchor": volSurfaceSVI["anchor"],
                      "anchorDate": volSurfaceSVI["anchorDate"],
                      "SVI-S": volSurfaceSVI["SVI-S"]}
    else:
        paramsSVIS = None

    repoFitted = None if memoryData is None else memoryData["repoFitted"]
    repoTableData = []
    if repoFitted != None:
        repoFitted = memoryData["repoFitted"]

        # calculate
        systemDivPoints, impliedDivPoints = getOptionImpliedDiv(repoFitted, memoryData["volData"]["spotRef"])

        tmpDict = {"Date": list(repoFitted["Schedule"].keys()), 
                   "ImpiledRepo": list(repoFitted["Schedule"].values()), 
                   "SystemDiv": list(systemDivPoints.values()),
                   "ImpliedDiv": [d["ImpliedDiv"] for d in memoryData["repoTableData"]]}
        repoDf = pd.DataFrame.from_dict(tmpDict)
        repoTableData = repoDf.to_dict("records")
        
    valueDate = get_exchangeDate(get_calendar(undlName)) if memoryData is None else memoryData["valueDate"]

    # load latest system remarking info
    systemSVI = get_volSurfaceSVI(undlName)
    volLastUpdateUser = "NIL"; volLastUpdateTime = "NIL"
    if systemSVI != None:
        if "lastUpdate" in systemSVI and "lastUpdateTime" in systemSVI:
            volLastUpdateUser = systemSVI["lastUpdate"]
            volLastUpdateTime = systemSVI["lastUpdateTime"]

    # if no vol surface in system
    if volSurfaceSVI is None:

        volSurfaceSVI = {"undlName": undlName,
                         "anchor": "NIL",
                         "anchorDate": "NIL",
                         "lastUpdate": "NIL",
                         "lastUpdateTime": "NIL",
                         "SVI-JW": {}}

        volTag = "SVI-JW"
        volModel = "SVI-JW"

        m = valueDate

    else:

        if "SVI-S" in volSurfaceSVI.keys():
            volModel = "SVI-S"
        elif "SVI-JW" in volSurfaceSVI.keys():
            volModel = "SVI-JW"
        elif "SVI-SPX" in volSurfaceSVI.keys(): 
            volModel = "SVI-SPX"

        volTag = "SVI-SPX" if volModel == "SVI-SPX" else "SVI-JW"

        # remove past date in vol surface svi
        volSurfaceSVI[volTag] = {m:p for m,p in volSurfaceSVI[volTag].items() if m > valueDate}
    
        m = list(volSurfaceSVI[volTag].keys())[0]

    topBar = html.Div([html.Div([dbc.Button("Load", id="button-loadVol", outline=True, color="danger", className="me-2", n_clicks=0),
                          dbc.Button("Save", id="button-saveVol", outline=True, color="danger", className="me-2", n_clicks=0),
                          dbc.Button("Option Chain", id="button-loadChainVol", outline=True, color="info", className="me-2", n_clicks=0),
                          dbc.Button("Fit Vol Surf", id="button-fitVolSurf", outline=True, color="info", className="me-2", n_clicks=0),
                          dbc.Button("Check Arb", id="button-checkArb", outline=True, color="info", className="me-2", n_clicks=0),
                          dbc.Button("Load Ref", id="button-loadRef", outline=True, color="success", className="me-2", n_clicks=0)], 
                          style={'display': 'inline-block', "margin-bottom": "10px"}),
                        html.H6(" "),
                        html.H6("Status: Successfully Loaded", id="text-volPageStatus", style={"color": "black"}),
                        html.H6(" "),
                        html.H6(f"Vol Surface Last Update: {volLastUpdateUser} ({volLastUpdateTime})", id="text-volLastUpdate"),
                        html.H6(" "),
                        html.H6(" ", id="text-arbCheck", style={"color": "black"}),
                        #html.H6(" "),
                        #html.Div([dcc.Interval(id="progress-interval-vol", n_intervals=0), 
                        #          dbc.Progress(value=100, label="100%", id="progress-vol", animated=False, striped=True)], style={"width": 500}),
                        html.H6(" "),
                        html.Hr()])
    
    if volModel == "SVI-SPX":
        sviDf = surfaceToDf(volSurfaceSVI, tag="SVI-SPX")
    else:
        sviDf = surfaceToDf(volSurfaceSVI)
    style_header={'fontWeight': 'bold', "background-color": "#F4F4F4"}
    
    if paramsSVIS != None:
        SVISDf = pd.DataFrame.from_dict({"Params": ["Short Term", "Long Term", "Strength"], 
                                     "Vol": np.array(list(paramsSVIS["SVI-S"]["vol"].values())) * 100, 
                                     "Skew": list(paramsSVIS["SVI-S"]["skew"].values()), 
                                     "Convex": list(paramsSVIS["SVI-S"]["convex"].values())})
    
        SVISData = SVISDf.to_dict("records")
    else:
        SVISData = []

    paramTableSVIS = dag.AgGrid(id="SVISTable",
                                rowData=[],
                                columnDefs=[{"field": "Params", "minWidth": 140, "maxWidth": 140, "pinned": "left", "type": "rightAligned"},
                                            {"field": "Vol", "maxWidth": 100, "minWidth": 100, "editable": True, "resizable": True,
                                             "valueFormatter": {"function": "d3.format(',.2f')(params.value) + '%'"},
                                             "cellStyle": {"background-color": "#fffee0"}},
                                            {"field": "Skew", "maxWidth": 100, "minWidth": 100, "editable": True, "resizable": True,
                                             "valueFormatter": {"function": "d3.format(',.2f')(params.value)"},
                                             "cellStyle": {"background-color": "#fffee0"}},
                                            {"field": "Convex", "maxWidth": 100, "minWidth": 100, "editable": True, "resizable": True,
                                             "valueFormatter": {"function": "d3.format(',.2f')(params.value)"},
                                             "cellStyle": {"background-color": "#fffee0"}}],
                                columnSize="autoSize",
                                className="ag-theme-balham ag-theme-custom",
                                dashGridOptions={"rowHeight": 30},
                                style={"width": 680, "height": 140})

    if volTag == "SVI-JW":

        columnDefs = [
            {"field": "Maturity", "minWidth": 105, "maxWidth": 105, "pinned": "left"},
            {"field": "Vol", "valueFormatter": {"function": "d3.format(',.2%')(params.value)"}, "type": "numericColumn", "editable": False, "resizable": True,  "singleClickEdit": False, "minWidth": 85, "maxWidth": 85}, 
            {"field": "Skew", "valueFormatter": {"function": "d3.format(',.2f')(params.value)"}, "type": "numericColumn","editable": False, "resizable": True, "singleClickEdit": False, "minWidth": 75, "maxWidth": 75},
            {"field": "PWing", "valueFormatter": {"function": "d3.format(',.2f')(params.value)"}, "type": "numericColumn","editable": False, "resizable": True, "singleClickEdit": False, "minWidth": 75, "maxWidth": 75},
            {"field": "CWing", "valueFormatter": {"function": "d3.format(',.2f')(params.value)"}, "type": "numericColumn","editable": False, "resizable": True, "singleClickEdit": False, "minWidth": 75, "maxWidth": 75},
            {"field": "MinVol", "valueFormatter": {"function": "d3.format(',.2%')(params.value)"}, "type": "numericColumn","editable": False, "resizable": True, "singleClickEdit": False, "minWidth": 80, "maxWidth": 80},
            {"field": "Tau", "valueFormatter": {"function": "d3.format(',.2f')(params.value)"}, "cellStyle": {"background-color": "#F1F1F1"}, "resizable": True, "type": "numericColumn", "minWidth": 75, "maxWidth": 75},
            {"field": "Forward", "valueFormatter": {"function": "d3.format(',.2%')(params.value)"}, "cellStyle": {"background-color": "#F1F1F1"}, "resizable": True, "type": "numericColumn", "minWidth": 85, "maxWidth": 85}
        ]
        
    else:

        columnDefs = [
            {"field": "Maturity", "minWidth": 105, "maxWidth": 105, "pinned": "left"},
            {"field": "Vol", "valueFormatter": {"function": "d3.format(',.2%')(params.value)"}, "type": "numericColumn", "editable": False, "resizable": True,  "singleClickEdit": False, "minWidth": 85, "maxWidth": 85}, 
            {"field": "Skew", "valueFormatter": {"function": "d3.format(',.2f')(params.value)"}, "type": "numericColumn","editable": False, "resizable": True, "singleClickEdit": False, "minWidth": 75, "maxWidth": 75},
            {"field": "PWing", "valueFormatter": {"function": "d3.format(',.2f')(params.value)"}, "type": "numericColumn","editable": False, "resizable": True, "singleClickEdit": False, "minWidth": 75, "maxWidth": 75},
            {"field": "CWing", "valueFormatter": {"function": "d3.format(',.2f')(params.value)"}, "type": "numericColumn","editable": False, "resizable": True, "singleClickEdit": False, "minWidth": 75, "maxWidth": 75},
            {"field": "MinVol", "valueFormatter": {"function": "d3.format(',.2%')(params.value)"}, "type": "numericColumn","editable": False, "resizable": True, "singleClickEdit": False, "minWidth": 80, "maxWidth": 80},
            {"field": "Loc", "valueFormatter": {"function": "d3.format(',.2f')(params.value)"}, "type": "numericColumn","editable": False, "resizable": True, "singleClickEdit": False, "minWidth": 75, "maxWidth": 75},
            {"field": "W", "valueFormatter": {"function": "d3.format(',.2f')(params.value)"}, "type": "numericColumn","editable": False, "resizable": True, "singleClickEdit": False, "minWidth": 75, "maxWidth": 75},
            {"field": "Tau", "valueFormatter": {"function": "d3.format(',.2f')(params.value)"}, "cellStyle": {"background-color": "#F1F1F1"}, "resizable": True, "type": "numericColumn", "minWidth": 75, "maxWidth": 75},
            {"field": "Forward", "valueFormatter": {"function": "d3.format(',.2%')(params.value)"}, "cellStyle": {"background-color": "#F1F1F1"}, "resizable": True, "type": "numericColumn", "minWidth": 85, "maxWidth": 85}
        ]

    paramTable = dag.AgGrid(id="SVITable", 
                            rowData=[],
                            columnDefs=columnDefs,
                            columnSize="autoSize",
                            className="ag-theme-balham ag-theme-custom",
                            dashGridOptions={"rowHeight": 30, "rowSelection": "single"})
    
    refParamTable = dag.AgGrid(id="refSVITable", 
                            rowData=[],
                            columnDefs=columnDefs,
                            columnSize="autoSize",
                            className="ag-theme-balham ag-theme-custom",
                            dashGridOptions={"rowHeight": 30, "rowSelection": "single"})
    
    paramsSubTable = dag.AgGrid(id="SVISubTable",
                                rowData = [],
                                columnDefs=[{"field": "Param", "minWidth": 85, "maxWidth": 85, "pinned": "left", "type": "rightAligned"},
                                            {"field": "Value", "minWidth": 110, 
                                             "valueFormatter": {"function": "d3.format(',.2f')(params.value)"},
                                             "editable": True,
                                             "cellStyle": {"background-color": "#fffee0"},
                                             "type": "numericColumn"}],
                                columnSize="autoSize",
                                className="ag-theme-balham ag-theme-custom",
                                dashGridOptions={"rowHeight": 30},
                                style={"height": 250, "margin-bottom": 10})
    
    paramsSubTable2 = dag.AgGrid(id="SVISubTable2",
                                rowData = [],
                                columnDefs=[{"field": "Ref", "minWidth": 85, "maxWidth": 85, "pinned": "left", "type": "rightAligned"},
                                            {"field": "Value", "minWidth": 110, 
                                             "valueFormatter": {"function": "d3.format(',.2f')(params.value)"},
                                             "editable": False,
                                             "type": "numericColumn"}],
                                columnSize="autoSize",
                                className="ag-theme-balham ag-theme-custom",
                                dashGridOptions={"rowHeight": 30},
                                style={"height": 95, "margin-bottom": 10})
        
    repoFittedTable = dag.AgGrid(id="RepoFittedTable", 
                                 rowData=[],
                                 columnDefs=[{"field": "Date", "maxWidth": 105, "resizable": True, "pinned": "left"}, 
                                             {"field": "ImpiledRepo", "valueFormatter": {"function": "d3.format(',.2%')(params.value)"}, 
                                              "maxWidth": 115, "resizable": True, "type": "numericColumn"},
                                              {"field": "SystemDiv", "valueFormatter": {"function": "d3.format(',.2f')(params.value)"},
                                               "maxWidth": 100, "resizable": True, "type": "numericColumn"},
                                              {"field": "ImpliedDiv", "valueFormatter": {"function": "d3.format(',.2f')(params.value)"}, 
                                               "maxWidth": 110, "resizable": True, "type": "numericColumn"}],
                                 columnSize="sizeToFit",
                                 className="ag-theme-balham ag-theme-custom",
                                dashGridOptions={"rowHeight": 30})

    panelParams = html.Div([html.H6(f"Anchor: {volSurfaceSVI['anchor']}", id="text-anchor"), 
                            html.H6(f"Anchor Date: {volSurfaceSVI['anchorDate']}", id="text-anchorDate"),
                            html.Div([dbc.Button("Re-Anchor", id="button-reanchor", outline=True, color="info", className="me-2", n_clicks=0, style={"margin-bottom": "5px"}),
                                      dbc.Button("Add Mat", id="button-addMat", outline=True, color="info", className="me-2", n_clicks=0, style={"margin-bottom": "5px"}),
                                      dbc.Button("Del Mat", id="button-delMat", outline=True, color="info", className="me-2", n_clicks=0, style={"margin-bottom": "5px"}),]),
                            html.Div(dbc.Collapse([paramTableSVIS], 
                                                  id="collapse-SVIS", is_open=False), style={"width": 680, "height": 0, "margin-bottom": 0}, id="SVIS-DIV"),
                            dbc.Row([html.Div(dbc.Collapse(paramTable, id="collapse-SVI", is_open=True), style={"width": 705, "height": 450, "margin-right":"10px"}),
                                     html.Div(dbc.Collapse(repoFittedTable, 
                                                          id="collapse-repoFitted", 
                                                          is_open=False), style={"width": 500, "height": 450, "margin-left": "0px"}, id="div-repoFitted"),
                                    html.Div(dbc.Collapse(refParamTable, id="collapse-refSVI", is_open=False), style={"width":525, "height": 450, "margin-left": 10})])], 
                                     style={'display': 'inline-block', "width": "1800px"})

    undlDf = pd.DataFrame.from_dict({"Underlying": [undlName], "Spot Ref": [spotRef], "Vol Model": [volTag]})

    undlInfoTable = dag.AgGrid(id="table-volUndlInfo",
                              rowData=[],
                              columnDefs=[{"field": "Underlying"}, 
                                          {"field": "Spot Ref", "editable": True, "cellStyle": {"background-color": "#fffee0"}, "singleClickEdit": False},
                                          {"field": "Vol Model", 
                                           "cellEditor": "agSelectCellEditor",
                                           "cellEditorParams": {"values": ["SVI-SPX"] if undlName==".SPX" else ["SVI-JW", "SVI-S"]},
                                           "clearable": False,
                                           "editable": True,
                                           "cellStyle": {"background-color": "#fffee0"},
                                           #"cellEditorParams": {"options": ["SVI-JW", "SVI-S", "SVI-N"], "clearable": False, "shadow": "xl"},
                                           "cellEditorPopup": False,
                                           "singleClickEdit": True}],
                              columnSize="sizeToFit",
                              className="ag-theme-balham ag-theme-custom",
                              dashGridOptions={"domLayout": "autoHeight", "rowHeight": 30})
    

    undlRefDf = pd.DataFrame.from_dict({"Hist Date": [""], "Vol Model": [""]})

    undlRefTable = dag.AgGrid(id="table-volUndlRef",
                              rowData=undlRefDf.to_dict("records"),
                              #{"field": "date", "cellEditor": {"function": "DatePicker"}}
                              columnDefs=[{"field": "Hist Date", "editable": True, "cellStyle": {"background-color": "#fffee0"}}, 
                                          {"field": "Vol Model"}],
                              columnSize="sizeToFit",
                              className="ag-theme-balham ag-theme-custom",
                              dashGridOptions={"domLayout": "autoHeight", "rowHeight": 30})

    panelUndlInfo = html.Div(dbc.Row([html.Div(undlInfoTable, style={"width": 450, "height": 100, "margin-bottom": "0px"})]))
    
    if volSurfaceSVI[volTag] == {}:
        maturities = [m]
    else:
        if memoryData != None:
            if "maturities" in memoryData.keys():
                maturities = memoryData["maturities"]
            else:
                maturities = sorted(list(set([k for k in volSurfaceSVI[volTag].keys()] + listedMaturities[get_calendar(undlName)+"_"+get_undlType(undlName)])))
                maturities = [m for m in maturities if m > valueDate]
        else:
            maturities = sorted(list(set([k for k in volSurfaceSVI[volTag].keys()] + listedMaturities[get_calendar(undlName)+"_"+get_undlType(undlName)])))
            maturities = [m for m in maturities if m > valueDate]

    strikes = curveGridStrikes
    vols = [0 for k in strikes]
    volDf = pd.DataFrame.from_dict({"Strike": strikes, m: vols})
    fig = px.line(volDf, x="Strike", y=m)
    fig = go.Figure(fig, layout_yaxis_range = yaxis_range, layout_xaxis_range = xaxis_range)
    
    subPanelMaturity = html.Div([dbc.Row(dcc.Dropdown(maturities, value=maturities[0], id='maturity-dropdown', style={'color': '#999999', "margin-top": "30px", "margin-bottom": "5px"})),
                                 dbc.Row([dbc.Col(dbc.Button("Prev", id="button-up", outline=True, color="info", className="me-2", n_clicks=0, style={"width": "80px"})), 
                                          dbc.Col(dbc.Button("Next", id="button-down", outline=True, color="info", className="me-2", n_clicks=0, style={"width": "80px"}))]),
                                html.Div(dbc.Collapse([paramsSubTable, paramsSubTable2, dbc.Button("Restore Params", id="button-restoreParams", outline=True, color="info", className="me-2", n_clicks=0, style={"width": "195px"})], 
                                                      id="collapse-SVISubTable", is_open=False), style={"margin-top": "10px", "width": 200, "height": 100})], 
                                          style={'display': 'inline-block'})
    
    panelFig = html.Div(dbc.Row([
        dbc.Col(html.Div([dcc.Graph(id="graph-volSmile", figure=fig, style={'width': '1500px', 'height': '650px', "margin-left":0, "margin-right": 0})], id="graph-area")), 
                          
        dbc.Col(subPanelMaturity)
    ]), style={'display': 'inline-block', "width": "1800px"})
    
    if memoryData is None:
        curveGrid = genVolGrid(volSurfaceSVI, volTag, spotRef, maturities, curveGridStrikes, returnType="dict")
    else:
        curveGrid = memoryData["curveGrid"]

    if memoryData is None:
        strikes = volGridStrikes
        gridDf = genVolGrid(volSurfaceSVI, volTag, spotRef, maturities, strikes)
        rowData = gridDf.to_dict("records")
    else:
        strikes = volGridStrikes
        rowData = memoryData["volGrid"]

    for i in range(len(rowData)):
        rowData[i]["id"] = i

    gridTable = dag.AgGrid(id="GridTable",
                              rowData = [],
                              columnDefs=[{"field": "Maturity", "maxWidth": 120, "pinned": "left"}] + \
                                        [{"field": str(round(k*100))+"%",
                                          "valueFormatter": {"function": "d3.format(',.1%')(params.value)"}, 
                                          "maxWidth": 80,
                                          "type": "numericColumn"} for k in strikes],
                              columnSize="sizeToFit",
                              className="ag-theme-balham ag-theme-custom",
                              dashGridOptions={"rowHeight": 30, "rowSelection": "single"})
    
    refGridTable = dag.AgGrid(id="refGridTable",
                              rowData = [],
                              columnDefs=[{"field": "Maturity", "maxWidth": 120, "pinned": "left"}] + \
                                        [{"field": str(round(k*100))+"%",
                                          "valueFormatter": {"function": "d3.format(',.1%')(params.value)"}, 
                                          "maxWidth": 80,
                                          "type": "numericColumn"} for k in strikes],
                              columnSize="sizeToFit",
                              className="ag-theme-balham ag-theme-custom",
                              dashGridOptions={"rowHeight": 30})
    
    compareGridTable = dag.AgGrid(id="compareGridTable",
                              rowData = [],
                              columnDefs=[{"field": "Maturity", "maxWidth": 120, "pinned": "left"}] + \
                                        [{"field": str(round(k*100))+"%",
                                          "valueFormatter": {"function": "d3.format(',.1%')(params.value)"}, 
                                          "maxWidth": 80,
                                          "type": "numericColumn",
                                          "cellStyle": {"styleConditions": [
                                              {"condition": "params.value < -0.005 & params.value >= -0.01", "style": {"background-color": "#F5B7B1"}},
                                              {"condition": "params.value < -0.01 & params.value >= -0.02", "style": {"background-color": "#F1948A"}},
                                              {"condition": "params.value < -0.02 & params.value >= -0.03", "style": {"background-color": "#EC7063"}},
                                              {"condition": "params.value < -0.03 & params.value >= -0.05", "style": {"background-color": "#E74C3C"}},
                                              {"condition": "params.value < -0.05 & params.value >= -0.10", "style": {"background-color": "#CB4335"}},
                                              {"condition": "params.value < -0.10 ", "style": {"background-color": "#B03A2E"}},
                                              {"condition": "params.value > 0.005 & params.value <= 0.01", "style": {"background-color": "#A3E4D7"}},
                                              {"condition": "params.value > 0.01 & params.value <= 0.02", "style": {"background-color": "#48C9B0"}},
                                              {"condition": "params.value > 0.02 & params.value <= 0.03", "style": {"background-color": "#48C9B0"}},
                                              {"condition": "params.value > 0.03 & params.value <= 0.05", "style": {"background-color": "#1ABC9C"}},
                                              {"condition": "params.value > 0.05 & params.value <= 0.10", "style": {"background-color": "#17A589"}},
                                              {"condition": "params.value > 0.10 ", "style": {"background-color": "#148F77"}},
                                              ], 
                                                        "defaultStyle": {"background-color": None}}} for k in strikes],
                              columnSize="sizeToFit",
                              className="ag-theme-balham ag-theme-custom",
                              dashGridOptions={"rowHeight": 30})
    
    panelGrid = html.Div([dbc.Button("Show/Hide Grid", id="button-showVolGrid", outline=True, color="info", className="me-2", n_clicks=0, style={"width": "250px", "margin-bottom": "5px"}),
                          dbc.Collapse(gridTable, id="collapse-grid", is_open=True)], style={'display': 'inline-block', "width": "1800px"})
    
    panelGrid2 = html.Div([dbc.Button("Show/Hide Ref Grid", id="button-showRefGrid", outline=True, color="info", className="me-2", n_clicks=0, style={"width": "250px", "margin-top": "5px", "margin-bottom": "5px"}),
                           dbc.Collapse([refGridTable, html.H6(" "), html.H6("Change"), compareGridTable], 
                                        id="collapse-refGrid", is_open=False)], style={'display': 'inline-block', "width": "1800px"})
    
    #panelGrid3 = html.Div([dbc.Button("Show/Hide Option Chain", id="button-showOptionChain", outline=True, color="info", className="me-2", n_clicks=0, style={"width": "250px", "margin-top": "5px", "margin-bottom": "5px"})], 
    #                      style={'display': 'inline-block', "width": "1800px"})

    if memoryData is None:
        refDate = None
        volSurfaceSVI_ref = None
        curveGrid_ref = None
        volGrid_ref = None
    else:
        refDate = memoryData["refDate"]
        volSurfaceSVI_ref = memoryData["volSurfaceSVI_ref"]
        curveGrid_ref = memoryData["curveGrid_ref"]
        volGrid_ref = memoryData["volGrid_ref"]

    # handle memory data
    memoryData = {} if memoryData == None else memoryData
    memoryData["undlName"] = undlName
    memoryData["valueDate"] = valueDate
    memoryData["spotRef"] = spotRef
    memoryData["volModel"] = volModel
    memoryData["maturities"] = maturities
    memoryData["volSurfaceSVI"] = volSurfaceSVI
    memoryData["volSurfaceSVI_backup"] = volSurfaceSVI
    memoryData["curveGrid"] = curveGrid # save a dict format
    memoryData["volGrid"] = rowData # save a record format
    memoryData["repoFitted"] = repoFitted
    memoryData["repoTableData"] = repoTableData
    memoryData["paramsSVIS"] = paramsSVIS
    memoryData["refDate"] = refDate
    memoryData["volSurfaceSVI_ref"] = volSurfaceSVI_ref
    memoryData["curveGrid_ref"] = curveGrid_ref
    memoryData["volGrid_ref"] = volGrid_ref

    return html.Div([dcc.Store(id="memory-vol-subParams"),
                     dcc.Store(id="memory-getOptionChainVol"),
                     dcc.ConfirmDialog(id="confirm-uploadVol", message="Confirm uploading Volatility Surface?"), 
                     dcc.ConfirmDialog(id="confirm-reloadVol", message="Confirm reloading Volatility Surface?"), 
                     dcc.ConfirmDialog(id="confirm-delMat", message="Confirm deleting?"), 
                     modalAddMaturity,
                     modalLoadRef,
                     modalLoadOptionChain,
                     dbc.Row([topBar]), dbc.Row(panelUndlInfo),
                      dbc.Row(panelParams), dbc.Row(panelFig), dbc.Row(panelGrid), dbc.Row(panelGrid2)]), memoryData

def createContentForward(undlName: str, memoryData: dict, dataCheck: bool=True):

    if undlName is None: return html.Div([html.H4("Please select underlying")]), memoryData

    if dataCheck == False: return html.Div([html.H4("Missing Market Data")]), memoryData

    if memoryData != None:
        if memoryData["undlName"] != undlName: memoryData = None

    if memoryData is None:

        spotData = get_spot(undlName)
        if "error" in spotData.keys(): return html.Div([html.H4("Fail to get underlying spot")]), None
        spotRef = spotData[undlName]
        rate = get_yieldCurve(get_CCY(undlName))
        div = get_dividend(undlName)
        repo = get_repo(undlName)
        calendar = get_calendar(undlName)
        undlType = get_undlType(undlName)
        valueDate = get_exchangeDate(calendar)

    else:

        spotRef = memoryData["spotRef"]
        rate = get_yieldCurve(get_CCY(undlName))
        div = memoryData["div"]
        repo = memoryData["repo"]
        calendar = get_calendar(undlName)
        undlType = get_undlType(undlName)
        valueDate = memoryData["valueDate"]

    divLastUpdateUser = (div["lastUpdate"] if "lastUpdate" in div.keys() else "System")
    divLastUpdateTime = (div["lastUpdateTime"] if "lastUpdateTime" in div.keys() else "")
    repoLastUpdateUser = (repo["lastUpdate"] if "lastUpdate" in repo.keys() else "System")
    repoLastUpdateTime = (repo["lastUpdateTime"] if "lastUpdateTime" in repo.keys() else "")

    maturities = listedMaturities[calendar+"_"+undlType]

    divTable = dag.AgGrid(id="table-div",
                          rowData=[],
                          columnDefs=[{"field": "Date", "minWidth": 120, "maxWidth": 120, "pinned": "left", "editable": True, "type": "rightAligned",
                                       "cellStyle": {"background-color": "#fffee0"}}, 
                                      {"field": "Value", "minWidth": 110, "maxWidth": 110, "editable": True, "type": "numericColumn",
                                       "valueFormatter": {"function": "d3.format(',.4f')(params.value)"}, "cellStyle": {"background-color": "#fffee0"},
                                       "cellStyle": {"styleConditions": [{"condition": "params.value == ''", "style": {"background-color": "#fffee0"}}], 
                                                     "defaultStyle": {"background-color": "#fffee0"}}},
                                      {"field": "Type", "minWidth": 110, "maxWidth": 110, "editable": True, "singleClickEdit": True, "type": "rightAligned",
                                       "cellEditor": "agSelectCellEditor", "cellEditorParams": {"values": ["Normal", "Forecast", ""]},
                                       "cellStyle": {"background-color": "#fffee0"},}
                                      ],
                          columnSize="sizeToFit",
                          className="ag-theme-balham ag-theme-custom",
                          dashGridOptions={"rowHeight": 30},
                          style={"width": 400, "height": 650})
    
    repoTable = dag.AgGrid(id="table-repo",
                          rowData=[],
                          columnDefs=[{"field": "Date", "minWidth": 120, "maxWidth": 120, "pinned": "left", "editable": True, "type": "rightAligned",
                                       "cellStyle": {"background-color": "#fffee0"}}, 
                                      {"field": "Value", "minWidth": 110, "maxWidth": 110, "editable": True, "type": "numericColumn",
                                       "valueFormatter": {"function": "d3.format(',.2%')(params.value)"}, "cellStyle": {"background-color": "#fffee0"},
                                       "cellStyle": {"styleConditions": [{"condition": "params.value == ''", "style": {"background-color": "#fffee0"}}], 
                                                     "defaultStyle": {"background-color": "#fffee0"}}}],
                          columnSize="sizeToFit",
                          className="ag-theme-balham ag-theme-custom",
                          dashGridOptions={"rowHeight": 30},
                          style={"width": 400, "height": 450})
    
    repoFittedTable = dag.AgGrid(id="RepoFittedTable-fwd", 
                                 rowData=[],
                                 columnDefs=[{"field": "Date", "maxWidth": 110, "resizable": True, "pinned": "left"}, 
                                             {"field": "ImpRepo", "valueFormatter": {"function": "d3.format(',.2%')(params.value)"}, 
                                              "maxWidth": 90, "resizable": True, "type": "numericColumn"},
                                              {"field": "SysDiv", "valueFormatter": {"function": "d3.format(',.2f')(params.value)"},
                                               "maxWidth": 85, "resizable": True, "type": "numericColumn"},
                                              {"field": "ImpDiv", "valueFormatter": {"function": "d3.format(',.2f')(params.value)"}, 
                                               "maxWidth": 85, "resizable": True, "type": "numericColumn"}],
                                 columnSize="sizeToFit",
                                 className="ag-theme-balham ag-theme-custom",
                                 dashGridOptions={"rowHeight": 30},
                                 style={"width": 400, "height": 650})
    
    divSummaryTable = dag.AgGrid(id="divSummaryTable",
                          rowData=[],
                          columnDefs=[{"field": "Year", "minWidth": 120, "maxWidth": 120, "pinned": "left", "editable": False, "type": "rightAligned"}, 
                                      {"field": "Points", "minWidth": 110, "maxWidth": 110, "type": "numericColumn",
                                       "valueFormatter": {"function": "d3.format(',.4f')(params.value)"}},
                                       {"field": "Yield", "minWidth": 110, "maxWidth": 110, "type": "numericColumn",
                                       "valueFormatter": {"function": "d3.format(',.2%')(params.value)"}}],
                          columnSize="sizeToFit",
                          className="ag-theme-balham ag-theme-custom",
                          dashGridOptions={"rowHeight": 30},
                          style={"width": 400, "height": 650})
    
    forwardTable = dag.AgGrid(id="forwardTable",
                          rowData=[],
                          columnDefs=[{"field": "Maturity", "minWidth": 120, "maxWidth": 120, "pinned": "left", "editable": False, "type": "rightAligned"}, 
                                      {"field": "Forward", "minWidth": 110, "maxWidth": 110, "type": "numericColumn",
                                       "valueFormatter": {"function": "d3.format(',.2f')(params.value)"}},
                                       {"field": "Forward %", "minWidth": 110, "maxWidth": 110, "type": "numericColumn",
                                       "valueFormatter": {"function": "d3.format(',.2%')(params.value)"}}],
                          columnSize="sizeToFit",
                          className="ag-theme-balham ag-theme-custom",
                          dashGridOptions={"rowHeight": 30},
                          style={"width": 400, "height": 650})
    
    topBar = html.Div([html.Div([dbc.Button("Load", id="button-loadFwd", outline=True, color="danger", className="me-2", n_clicks=0),
                                 dbc.Button("Save", id="button-saveFwd", outline=True, color="danger", className="me-2", n_clicks=0),
                                 dbc.Button("Option Imp. Div/Repo", id="button-loadOptionImpDiv", outline=True, color="info", className="me-2", n_clicks=0),
                                 dbc.Button("Forecast Div", id="button-forecastDiv", outline=True, color="info", className="me-2", n_clicks=0)], 
                                 style={'display': 'inline-block'}),
                                 html.H6(" "),
                        html.Div("Status: Successfully Loaded", id="text-divPageStatus"),
                        html.H6(" "),
                        html.Div(f"Dividend Last Update: {divLastUpdateUser} ({divLastUpdateTime}) / Repo Last Update: {repoLastUpdateUser} ({repoLastUpdateTime})", id="text-fwdLastUpdate"),
                        html.Hr()])
    
    undlDf = pd.DataFrame.from_dict({"Underlying": [undlName], "Spot Ref": [spotRef]})

    spotRefTable = dag.AgGrid(id="table-fwdUndlInfo",
                              rowData=[],
                              columnDefs=[{"field": "Underlying"}, 
                                          {"field": "Spot Ref", "editable": True, "cellEditorPopup": False, "singleClickEdit": False, "cellStyle": {"background-color": "#fffee0"},}],
                              columnSize="sizeToFit",
                              className="ag-theme-balham ag-theme-custom",
                              dashGridOptions={"domLayout": "autoHeight", "rowHeight": 30})

    panel0 = html.Div(spotRefTable, style={"margin-bottom": "10px", "width": 400, "height":100})

    panel1 = html.Div([
                html.Div([html.H4("Div Table")]), 
                html.Div([dbc.Button("Export", id="button-exportDiv", className="me-2", outline=True, color="info", n_clicks=0),
                          dbc.Button("Import", id="button-importDiv", className="me-2", outline=True, color="info", n_clicks=0)], style={"margin-bottom": "5px"}),
                html.Div([divTable], style={"width": 400, "height": 650, "margin-bottom": "25px"}), 
                html.H1(" "), 
                html.H4("Repo Table"), 
                html.Div([dbc.Button("Export", id="button-exportRepo", className="me-2", outline=True, color="info", n_clicks=0),
                          dbc.Button("Import", id="button-importRepo", className="me-2", outline=True, color="info", n_clicks=0)], style={"margin-bottom": "5px"}),
                html.Div([repoTable], style={"width": 400, "height": 450, "margin-bottom": "0px"}), 
            ])

    panel2 = html.Div([html.H4("Option Implied Div/Repo"),
                       html.Div([dbc.Button("Export", id="button-exportRRR", className="me-2", outline=True, color="info", n_clicks=0),
                                 dbc.Button("To Repo", id="button-remarkRepo", className="me-2", outline=True, color="info", n_clicks=0)], style={"margin-bottom": "5px"}),
                       repoFittedTable], style={"display": "inline-block"})

    panel3 = html.Div([html.H4("Dividend Swap"), 
                       html.Div([dbc.Button("Export", id="button-exportDivSwap", className="me-2", outline=True, color="info", n_clicks=0)], style={"margin-bottom": "5px"}),
                       divSummaryTable], style={'display': 'inline-block'})

    panel4 = html.Div([html.H4("Forward"), 
                       html.Div([dbc.Button("Export", id="button-exportFwd", className="me-2", outline=True, color="info", n_clicks=0)], style={"margin-bottom": "5px"}),
                       forwardTable], style={'display': 'inline-block'})

    content = html.Div([dbc.Row(panel0), dbc.Row([dbc.Col(panel1), dbc.Col(panel2), dbc.Col(panel3), dbc.Col(panel4)])])

    if memoryData is None:
        memoryData = {}
        memoryData["undlName"] = undlName
        memoryData["valueDate"] = valueDate
        memoryData["spotRef"] = spotRef 
        memoryData["maturities"] = maturities
        memoryData["div"] = div
        memoryData["repo"] = repo
        memoryData["repoFitted"] = None
        memoryData["repoTableData"] = []

    df_divSwap, df_fwd = createDivSwapNForward(memoryData)

    memoryData["divSwapData"] = df_divSwap.to_dict("records")
    memoryData["fwdData"] = df_fwd.to_dict("records")
    
    return html.Div([dcc.ConfirmDialog(id="confirm-reloadFwd", message="Confirm reloading forward data?"), 
                     dcc.ConfirmDialog(id="confirm-saveFwd", message="Confirm saving div and repo?"), 
                     modalForecastDiv,
                     topBar, 
                     content]), memoryData

app = dash.Dash('Market Data Manager', 
                external_stylesheets=[dbc.themes.SPACELAB], 
                suppress_callback_exceptions=True)
app.title = 'Market Data Manager'

content = html.Div(id="page-content", style=CONTENT_STYLE)

app.layout = html.Div([dcc.Location(id="url"), sidebar, content])

# app layout
@app.callback([Output("page-content", "children"), 
               Output("memory-vol", "data", allow_duplicate=True), 
               Output("memory-fwd", "data", allow_duplicate=True), 
               Output("tableUndlInfo", "rowData", allow_duplicate=True),
               Output("tableMarketDataCheck", "rowData", allow_duplicate=True)],
              [Input("url", "pathname"), 
               Input("undlName-dropdown", "value"), 
               State("memory-vol", "data"),
               State("memory-fwd", "data")], prevent_initial_call=True)
def render_page_content(pathname, undlName, memoryVolData, memoryFwdData):

    rowDataUndlInfo, rowDataMarketDataCheck, dataCheck = createUndlNameInfoRowData(undlName)

    if pathname == "/":
        return html.Div(html.H4("Ready")), memoryVolData, memoryFwdData, rowDataUndlInfo, rowDataMarketDataCheck
    elif pathname == "/forward":
        page, memoryFwdData = createContentForward(undlName, memoryFwdData, dataCheck)
        return page, memoryVolData, memoryFwdData, rowDataUndlInfo, rowDataMarketDataCheck
    elif pathname == "/volatility":
        page, memoryVolData = createContentVolatility(undlName, memoryVolData, dataCheck)
        return page, memoryVolData, memoryFwdData, rowDataUndlInfo, rowDataMarketDataCheck
    elif pathname == "/addUndlName":
        return createContentAddUndl(undlName), memoryVolData, memoryFwdData, rowDataUndlInfo, rowDataMarketDataCheck
    elif pathname == "/setting":
        return createContentSetting(), memoryVolData, memoryFwdData, rowDataUndlInfo, rowDataMarketDataCheck
    elif pathname == "/otherMarketData":
        return createContentOtherMarketData(), memoryVolData, memoryFwdData, rowDataUndlInfo, rowDataMarketDataCheck
    elif pathname == "/vsfsetting":
        return createContentVSFBatch(), memoryVolData, memoryFwdData, rowDataUndlInfo, rowDataMarketDataCheck
    # If the user tries to reach a different page, return a 404 message
    return html.Div(
        [
            html.H1("404: Not found", className="text-danger"),
            html.Hr(),
            html.P(f"The pathname {pathname} was not recognised..."),
        ],
        className="p-3 bg-light rounded-3",
    ), memoryVolData, memoryFwdData, rowDataUndlInfo, rowDataMarketDataCheck

@app.callback(Output("undlName-dropdown", "value"), [Input("button-undlDB", "n_clicks")])
def addUndlName(n_clicks):
    if n_clicks > 0:
        return None

# forward Marking    
# change div schedule
@app.callback(Output("memory-fwd", "data", allow_duplicate=True), 
              [Input("table-div", "cellValueChanged"), 
               State("memory-fwd", "data"),
               State("table-div", "rowData")], prevent_initial_call=True)
def changeRowInDivTable(cellChanged, memoryData, rowData):

    if cellChanged is None: return memoryData

    div = deepcopy(memoryData["div"])
    div["Schedule"] = {}
    for data in rowData:
        if data["Date"] != "" and data["Value"] != "":
            div["Schedule"][toSystemDate2(data["Date"])] = {"value": float(data["Value"] if data["Value"] != "" else 0), "type": data["Type"]}
    memoryData["div"] = div

    if cellChanged["colId"] != "Type":
        if cellChanged["data"]["Value"] != "":        

            df_divSwap, df_fwd = createDivSwapNForward(memoryData)
            memoryData["divSwapData"] = df_divSwap.to_dict("records")
            memoryData["fwdData"] = df_fwd.to_dict("records")

    return memoryData

@app.callback(Output("memory-fwd", "data", allow_duplicate=True), 
              [Input("table-repo", "cellValueChanged"), 
               State("memory-fwd", "data"),
               State("table-repo", "rowData")], prevent_initial_call=True)
def changeRowInRepoTable(cellChanged, memoryData, rowData):

    if cellChanged is None: return memoryData

    repo = memoryData["repo"]
    repo["Schedule"] = {}
    for data in rowData:
        if data["Date"] != "" and data["Value"] != "":
            if cellChanged["colId"] == "Value":
                if cellChanged["data"]["Date"] == data["Date"]:
                    repo["Schedule"][toSystemDate2(data["Date"])] = float(data["Value"]) / 100
                else:
                    repo["Schedule"][toSystemDate2(data["Date"])] = float(data["Value"])
            else:
                repo["Schedule"][toSystemDate2(data["Date"])] = float(data["Value"])
    memoryData["repo"] = repo

    if cellChanged["colId"] != "Type":
        if cellChanged["data"]["Value"] != "":        

            df_divSwap, df_fwd = createDivSwapNForward(memoryData)
            memoryData["divSwapData"] = df_divSwap.to_dict("records")
            memoryData["fwdData"] = df_fwd.to_dict("records")

    return memoryData

@app.callback(Output("memory-fwd", "data", allow_duplicate=True),
              [Input("button-remarkRepo", "n_clicks"), State("memory-fwd", "data")], prevent_initial_call=True)
def remarkRepo(n_clicks, memoryData):

    if n_clicks:

        memoryData["repo"]["Schedule"] = memoryData["repoFitted"]["Schedule"]

        df_divSwap, df_fwd = createDivSwapNForward(memoryData)

        memoryData["divSwapData"] = df_divSwap.to_dict("records")
        memoryData["fwdData"] = df_fwd.to_dict("records")

    return memoryData

@app.callback([Output("table-div", "exportDataAsCsv", allow_duplicate=True), 
               Output("table-div", "csvExportParams", allow_duplicate=True)],
              [Input("button-exportDiv", "n_clicks"), State("memory-fwd", "data")], prevent_initial_call=True)
def exportDiv(n_clicks, memoryData):

    if n_clicks:
        undlName = memoryData["undlName"]
        return True, {"fileName": "dividend_"+undlName+".csv", "allColumns": True}
    return False, {"fileName": "dividend.csv", "allColumns": True}

@app.callback(Output("memory-fwd", "data", allow_duplicate=True),
              [Input("button-importDiv", "n_clicks"), State("memory-fwd", "data")], prevent_initial_call=True)
def importDiv(n_clicks, memoryData):

    if n_clicks:

        clipBoard = pyperclip.paste()
        if checkDividendTableInput(clipBoard) == False:
            return memoryData
        
        div = memoryData["div"]
        div["Schedule"] = {}
        
        for line in clipBoard.split("\r\n"):
            data = line.split("\t")
            if data[0].lower() != "date" and data[0] != "":
                date = data[0]
                value = data[1]
                divType = data[2]
                if value != "" and value != 0:
                    div["Schedule"][toSystemDate2(date)] = {"value": float(value), "type": divType}

        memoryData["div"] = div

        df_divSwap, df_fwd = createDivSwapNForward(memoryData)
        memoryData["divSwapData"] = df_divSwap.to_dict("records")
        memoryData["fwdData"] = df_fwd.to_dict("records")

    return memoryData
    
@app.callback([Output("table-repo", "exportDataAsCsv", allow_duplicate=True), 
               Output("table-repo", "csvExportParams", allow_duplicate=True)],
              [Input("button-exportRepo", "n_clicks"), State("memory-fwd", "data")], prevent_initial_call=True)
def exportRepo(n_clicks, memoryData):

    if n_clicks:
        undlName = memoryData["undlName"]
        return True, {"fileName": "repo_"+undlName+".csv", "allColumns": True}
    return False, {"fileName": "repo.csv", "allColumns": True}

@app.callback(Output("memory-fwd", "data", allow_duplicate=True),
              [Input("button-importRepo", "n_clicks"), State("memory-fwd", "data")], prevent_initial_call=True)
def importRepo(n_clicks, memoryData):

    if n_clicks:
        repo = memoryData["repo"]
        repo["Schedule"] = {}

        clipBoard = pyperclip.paste()
        for line in clipBoard.split("\r\n"):
            data = line.split("\t")
            if data[0].lower() != "date" and data[0] != "":
                date = data[0]
                value = data[1]
                if value != "" and value != 0:
                    repo["Schedule"][toSystemDate2(date)] = float(value)

        memoryData["repo"] = repo

        df_divSwap, df_fwd = createDivSwapNForward(memoryData)
        memoryData["divSwapData"] = df_divSwap.to_dict("records")
        memoryData["fwdData"] = df_fwd.to_dict("records")

    return memoryData

@app.callback([Output("divSummaryTable", "exportDataAsCsv", allow_duplicate=True), 
               Output("divSummaryTable", "csvExportParams", allow_duplicate=True)],
              [Input("button-exportDivSwap", "n_clicks"), State("memory-fwd", "data")], prevent_initial_call=True)
def exportDivSwap(n_clicks, memoryData):

    if n_clicks:
        undlName = memoryData["undlName"]
        return True, {"fileName": "divSwap_"+undlName+".csv", "allColumns": True}
    return False, {"fileName": "divSwap.csv", "allColumns": True}

@app.callback([Output("RepoFittedTable-fwd", "exportDataAsCsv", allow_duplicate=True), 
               Output("RepoFittedTable-fwd", "csvExportParams", allow_duplicate=True)],
              [Input("button-exportRRR", "n_clicks"), State("memory-fwd", "data")], prevent_initial_call=True)
def exportRepoFitted(n_clicks, memoryData):

    if n_clicks:
        undlName = memoryData["undlName"]
        return True, {"fileName": "impliedFwd_"+undlName+".csv", "allColumns": True}
    return False, {"fileName": "impliedFwd.csv", "allColumns": True}

@app.callback([Output("modal-forecastDiv", "is_open", allow_duplicate=True),
               Output("button-fitDivGrowFactor", "disabled", allow_duplicate=True)],
              [Input("button-forecastDiv", "n_clicks"), 
               Input("button-modal-closeforecastDiv", "n_clicks"),
               State("modal-forecastDiv", "is_open"),
               State("memory-fwd", "data")], prevent_initial_call=True)
def forecastDivClick(n1, n2, is_open, memoryData):

    
    disabled = False
    if memoryData["repoFitted"] is None: disabled = True

    if n1 or n2:
        return not is_open, disabled
    return is_open, disabled

@app.callback([Output("memory-fwd", "data", allow_duplicate=True),
               Output("modal-forecastDiv", "is_open", allow_duplicate=True)],
              [Input("button-modal-forecastDiv", "n_clicks"), 
               State("forecastYear", "value"),
               State("divGrowFactor", "value"),
               State("memory-fwd", "data")], prevent_initial_call=True)
def toDiv(n_clicks, forecastYear, factor, memoryData):

    if n_clicks:

        if forecastYear != None and factor != None:

            undlName = memoryData["undlName"]
            spotRef = memoryData["spotRef"]
            repoFitted = memoryData["repoFitted"]

            forecastDiv = forecast_stockDiv(undlName, factor, forecastYear)
            memoryData["div"]["Schedule"] = forecastDiv

            df_divSwap, df_fwd = createDivSwapNForward(memoryData)

            memoryData["divSwapData"] = df_divSwap.to_dict("records")
            memoryData["fwdData"] = df_fwd.to_dict("records")

    return memoryData, False

@app.callback(Output("divGrowFactor", "value"),
              [Input("button-fitDivGrowFactor", "n_clicks"), State("memory-fwd", "data")], prevent_initial_call=True)
def fitDivGrowFactor(n_clicks, memoryData):

    if n_clicks:

        undlName = memoryData["undlName"]
        repoFitted = memoryData["repoFitted"]
        systemDivPoints, impliedDivPoints = getOptionImpliedDiv(repoFitted, memoryData["spotRef"], None, memoryData["repo"])
        impliedDiv = {date: div for date, div in zip(list(repoFitted["Schedule"].keys()), list(impliedDivPoints.values()))}

        factor = fit_divGrowthFactor(undlName, impliedDiv)

        if "error" in factor.keys():
            return None
        elif factor["factor"] == -999:
            return None
        else:
            return round(factor["factor"], 4)
        
    return None

@app.callback([Output("forwardTable", "exportDataAsCsv", allow_duplicate=True), 
               Output("forwardTable", "csvExportParams", allow_duplicate=True)],
              [Input("button-exportFwd", "n_clicks"), State("memory-fwd", "data")], prevent_initial_call=True)
def exportFwd(n_clicks, memoryData):

    if n_clicks:
        undlName = memoryData["undlName"]
        return True, {"fileName": "fwd_"+undlName+".csv", "allColumns": True}
    return False, {"fileName": "fwd.csv", "allColumns": True}

@app.callback(Output("memory-fwd", "data", allow_duplicate=True),
              [Input("button-loadOptionImpDiv", "n_clicks"), State("memory-fwd", "data")], prevent_initial_call=True)
def getOptionImpliedFwd(n_clicks, memoryData):

    if n_clicks:

        undlName = memoryData["undlName"]
        OC = retrieveOptionChain(undlName)
        optionChainData = processOptionChainRawData(undlName, OC)

        data = get_optionChainRepo(optionChainData)

        if "error" not in data.keys():
            repoFitted = data["repoFitted"]

            repoTableData = []
            systemDivPoints, impliedDivPoints = getOptionImpliedDiv(repoFitted, memoryData["spotRef"], None, memoryData["repo"])

            tmpDict = {"Date": list(repoFitted["Schedule"].keys()), 
                       "ImpRepo": list(repoFitted["Schedule"].values()), 
                       "SysDiv": list(systemDivPoints.values()),
                       "ImpDiv": list(impliedDivPoints.values())}
            repoDf = pd.DataFrame.from_dict(tmpDict)
            repoTableData = repoDf.to_dict("records")

            #impliedDiv = {date: div for date, div in zip(list(repoFitted["Schedule"].keys()), list(impliedDivPoints.values()))}

            memoryData["repoFitted"] = repoFitted
            memoryData["repoTableData"] = repoTableData

    return memoryData

@app.callback(Output("memory-fwd", "data", allow_duplicate=True),
              [Input("table-fwdUndlInfo", "cellValueChanged"), State("memory-fwd", "data")], prevent_initial_call=True)
def changeFwdSpotRef(cellChanged, memoryData):

    if cellChanged is None: return memoryData

    spotRef = cellChanged["value"]
    if spotRef is None: return memoryData
    spotRef = float(spotRef)
    memoryData["spotRef"] = spotRef

    df_divSwap, df_fwd = createDivSwapNForward(memoryData)
    memoryData["divSwapData"] = df_divSwap.to_dict("records")
    memoryData["fwdData"] = df_fwd.to_dict("records")
    
    return memoryData

@app.callback(Output("confirm-reloadFwd", "displayed"), [Input("button-loadFwd", "n_clicks")], prevent_initial_call=True)
def loadFwd(n_clicks):
    if n_clicks:
        return True
    return False

@app.callback([Output("page-content", "children", allow_duplicate=True), Output("memory-fwd", "data", allow_duplicate=True)],
              [Input("confirm-reloadFwd", "submit_n_clicks"),
               State("undlName-dropdown", "value"),
               State("page-content", "children"),
               State("memory-fwd", "data")], prevent_initial_call=True)
def reloadFwdConfirmed(submit_n_clicks, undlName, content, memoryData):

    if submit_n_clicks:

        return createContentForward(undlName, None)
    
    return content, memoryData

@app.callback(Output("confirm-saveFwd", "displayed"), [Input("button-saveFwd", "n_clicks")], prevent_initial_call=True)
def saveFwd(n_clicks):
    if n_clicks:
        return True
    return False

@app.callback([Output("text-divPageStatus", "children", allow_duplicate=True), Output("button-saveFwd", "n_clicks")], 
              [Input("confirm-saveFwd", "submit_n_clicks"), 
               Input("undlName-dropdown", "value"), 
               Input("table-div", "rowData"), 
               Input("table-repo", "rowData")], prevent_initial_call=True)
def uploadDiv(submit_n_clicks, undlName, divData, repoData):
    if submit_n_clicks:
        
        divPanel = {"undlName": undlName, 
                    "lastUpdate": getpass.getuser(),
                    "lastUpdateTime": datetime.strftime(datetime.now(), "%Y-%m-%dT%H:%M:%S"),
                    "Schedule": {toSystemDate2(d["Date"]): {"value": d["Value"], "type": d["Type"]} for d in divData if d["Date"] != "" and d["Value"] != "" and d["Value"] != 0}}
        repoPanel = {"undlName": undlName, 
                     "lastUpdate": getpass.getuser(),
                     "lastUpdateTime": datetime.strftime(datetime.now(), "%Y-%m-%dT%H:%M:%S"),
                     "Schedule": {toSystemDate2(d["Date"]):d["Value"] for d in repoData if d["Date"] != "" and d["Value"] != "" and d["Value"] != 0}}

        check = 1
        for k,v in divPanel["Schedule"].items():
            if k == "Error in date string":
                check = 0

        for k,v in repoPanel["Schedule"].items():
            if k == "Error in date string":
                check = 0

        if check == 0: return "Error in date string"

        #if divPanel["Schedule"] != {}:
        #    divStatus = upload_dividend(divPanel)
        #else:
        #    divStatus = {"status": "No divs to upload"}
        divStatus = upload_dividend(divPanel)

        #if repoPanel["Schedule"] != {}:
        #    repoStatus = upload_repo(repoPanel)
        #else:
        #    repoStatus = {"status": "No repo to upload"}

        repoStatus = upload_repo(repoPanel)

        return [f"Status: {divStatus['status']} / {repoStatus['status']}"], 0

    else:

        return ["Status: Successfully Loaded"], 0

@app.callback([Output("table-fwdUndlInfo", "rowData", allow_duplicate=True),
               Output("table-div", "rowData", allow_duplicate=True),
               Output("table-repo", "rowData", allow_duplicate=True),
               Output("divSummaryTable", "rowData", allow_duplicate=True),
               Output("forwardTable", "rowData", allow_duplicate=True),
               Output("RepoFittedTable-fwd", "rowData", allow_duplicate=True),],
              [Input("memory-fwd", "data")], prevent_initial_call=True)
def displayMemoryFwdData(memoryData):

    undlName = memoryData["undlName"]
    yieldCurve = get_yieldCurve(get_CCY(undlName))
    calendar = get_calendar(undlName)
    spotRef = memoryData["spotRef"]
    valueDate = memoryData["valueDate"]
    maturities = memoryData["maturities"]
    div = memoryData["div"]
    if div["Schedule"] == {}:
        div["Schedule"] = {get_exchangeDate(calendar): {"value": "", "type": ""}}
    repo = memoryData["repo"]
    if repo["Schedule"] == {}:
        repo["Schedule"] = {get_exchangeDate(calendar): 0}

    marketDataParams = {"yieldCurve": yieldCurve, "divCurve": div, "repoCurve": repo, "calendar": calendar}

    dataUndlinfo = [{"Underlying": undlName, "Spot Ref": spotRef}]

    df_div = pd.DataFrame.from_dict({"Date": [toDisplayDate(dateStr) for dateStr in list(div["Schedule"].keys())], 
                                     "Value": [v["value"] for v in div["Schedule"].values()], 
                                     "Type": [v["type"] for v in div["Schedule"].values()]})
    
    df_repo = pd.DataFrame.from_dict({"Date": [toDisplayDate(dateStr) for dateStr in list(repo["Schedule"].keys())], 
                                      "Value": list(repo["Schedule"].values())})

    return dataUndlinfo, df_div.to_dict("records"), df_repo.to_dict("records"), memoryData["divSwapData"], memoryData["fwdData"], memoryData["repoTableData"]

@app.callback([Output("table-volUndlInfo", "rowData", allow_duplicate=True), 
               Output("text-anchor", "children", allow_duplicate=True),
               Output("text-anchorDate", "children", allow_duplicate=True),
               Output("SVITable", "rowData", allow_duplicate=True),
               Output("maturity-dropdown", "options", allow_duplicate=True),
               Output("maturity-dropdown", "value", allow_duplicate=True),
               Output("GridTable", "rowData", allow_duplicate=True),
               Output("collapse-repoFitted", "is_open", allow_duplicate=True),
               Output("RepoFittedTable", "rowData", allow_duplicate=True),
               Output("collapse-SVIS", "is_open", allow_duplicate=True),
               Output("SVIS-DIV", "style", allow_duplicate=True),
               Output("SVISTable", "rowData", allow_duplicate=True),
               Output("button-fitVolSurf", "disabled", allow_duplicate=True),
               Output("collapse-SVISubTable", "is_open", allow_duplicate=True),
               Output("collapse-SVI", "is_open", allow_duplicate=True),
               Output("button-addMat", "disabled", allow_duplicate=True),
               Output("button-delMat", "disabled", allow_duplicate=True),
               Output("SVITable", "columnDefs", allow_duplicate=True),
               Output("text-arbCheck", "children", allow_duplicate=True),
               Output("refGridTable", "rowData", allow_duplicate=True),
               Output("collapse-refSVI", "is_open", allow_duplicate=True),
               Output("refSVITable", "rowData", allow_duplicate=True),
               Output("div-repoFitted", "style", allow_duplicate=True),
               Output("compareGridTable", "rowData", allow_duplicate=True)], 
               [Input("memory-vol", "data"), State("maturity-dropdown", "value")], prevent_initial_call=True)
def displayMemoryVolData(memoryData, maturity):

    undlName = memoryData["undlName"]
    valueDate = memoryData["valueDate"]
    spotRef = memoryData["spotRef"]
    volModel = memoryData["volModel"]
    volTag = "SVI-SPX" if volModel == "SVI-SPX" else "SVI-JW"
    volSurfaceSVI = memoryData["volSurfaceSVI"]
    volGrid = memoryData["volGrid"]
    volSurfaceSVI_ref = memoryData["volSurfaceSVI_ref"]

    if volTag == "SVI-JW":

        columnDefs = [
            {"field": "Maturity", "minWidth": 105, "maxWidth": 105, "pinned": "left"},
            {"field": "Vol", "valueFormatter": {"function": "d3.format(',.2%')(params.value)"}, "type": "numericColumn", "editable": False, "resizable": True,  "singleClickEdit": False, "minWidth": 85, "maxWidth": 85}, 
            {"field": "Skew", "valueFormatter": {"function": "d3.format(',.2f')(params.value)"}, "type": "numericColumn","editable": False, "resizable": True, "singleClickEdit": False, "minWidth": 75, "maxWidth": 75},
            {"field": "PWing", "valueFormatter": {"function": "d3.format(',.2f')(params.value)"}, "type": "numericColumn","editable": False, "resizable": True, "singleClickEdit": False, "minWidth": 75, "maxWidth": 75},
            {"field": "CWing", "valueFormatter": {"function": "d3.format(',.2f')(params.value)"}, "type": "numericColumn","editable": False, "resizable": True, "singleClickEdit": False, "minWidth": 75, "maxWidth": 75},
            {"field": "MinVol", "valueFormatter": {"function": "d3.format(',.2%')(params.value)"}, "type": "numericColumn","editable": False, "resizable": True, "singleClickEdit": False, "minWidth": 80, "maxWidth": 80},
            {"field": "Tau", "valueFormatter": {"function": "d3.format(',.2f')(params.value)"}, "cellStyle": {"background-color": "#F1F1F1"}, "resizable": True, "type": "numericColumn", "minWidth": 75, "maxWidth": 75},
            {"field": "Forward", "valueFormatter": {"function": "d3.format(',.2%')(params.value)"}, "cellStyle": {"background-color": "#F1F1F1"}, "resizable": True, "type": "numericColumn", "minWidth": 85, "maxWidth": 85}
        ]
        
    else:

        columnDefs = [
            {"field": "Maturity", "minWidth": 105, "maxWidth": 105, "pinned": "left"},
            {"field": "Vol", "valueFormatter": {"function": "d3.format(',.2%')(params.value)"}, "type": "numericColumn", "editable": False, "resizable": True,  "singleClickEdit": False, "minWidth": 85, "maxWidth": 85}, 
            {"field": "Skew", "valueFormatter": {"function": "d3.format(',.2f')(params.value)"}, "type": "numericColumn","editable": False, "resizable": True, "singleClickEdit": False, "minWidth": 75, "maxWidth": 75},
            {"field": "PWing", "valueFormatter": {"function": "d3.format(',.2f')(params.value)"}, "type": "numericColumn","editable": False, "resizable": True, "singleClickEdit": False, "minWidth": 75, "maxWidth": 75},
            {"field": "CWing", "valueFormatter": {"function": "d3.format(',.2f')(params.value)"}, "type": "numericColumn","editable": False, "resizable": True, "singleClickEdit": False, "minWidth": 75, "maxWidth": 75},
            {"field": "MinVol", "valueFormatter": {"function": "d3.format(',.2%')(params.value)"}, "type": "numericColumn","editable": False, "resizable": True, "singleClickEdit": False, "minWidth": 80, "maxWidth": 80},
            {"field": "Loc", "valueFormatter": {"function": "d3.format(',.2f')(params.value)"}, "type": "numericColumn","editable": False, "resizable": True, "singleClickEdit": False, "minWidth": 75, "maxWidth": 75},
            {"field": "W", "valueFormatter": {"function": "d3.format(',.2f')(params.value)"}, "type": "numericColumn","editable": False, "resizable": True, "singleClickEdit": False, "minWidth": 75, "maxWidth": 75},
            {"field": "Tau", "valueFormatter": {"function": "d3.format(',.2f')(params.value)"}, "cellStyle": {"background-color": "#F1F1F1"}, "resizable": True, "type": "numericColumn", "minWidth": 75, "maxWidth": 75},
            {"field": "Forward", "valueFormatter": {"function": "d3.format(',.2%')(params.value)"}, "cellStyle": {"background-color": "#F1F1F1"}, "resizable": True, "type": "numericColumn", "minWidth": 85, "maxWidth": 85}
        ]

    maturities = memoryData["maturities"]
    if maturity not in maturities:
        maturity = maturities[0]

    undlInfo = [{"Underlying": undlName, "Spot Ref": spotRef, "Vol Model": volModel}]
    textAnchor = f"Anchor: {volSurfaceSVI['anchor']}" if volSurfaceSVI_ref is None else f"Anchor: {volSurfaceSVI['anchor']}     /     Ref Anchor: {volSurfaceSVI_ref['anchor']}"
    textAnchorDate = f"Anchor Date: {volSurfaceSVI['anchorDate']}" if volSurfaceSVI_ref is None else f"Anchor Date: {volSurfaceSVI['anchorDate']}     /     Ref Anchor Date: {volSurfaceSVI_ref['anchorDate']}"
    SVIData = surfaceToDf(memoryData["volSurfaceSVI"], volTag).to_dict("records")

    is_open = False if memoryData["repoFitted"] is None else True
    styleDivRepoFitted = {"width": 0, "height": 450, "margin-left": "0px"} if memoryData["repoFitted"] is None else {"width": 500, "height": 450, "margin-left": "0px"}
    repoTableData = memoryData["repoTableData"]

    is_open_SVIS = True if volModel == "SVI-S" else False
    style={"width": 680, "height": 140, "margin-bottom": "5px"} if volModel == "SVI-S" else {"width": 680, "height": 0, "margin-bottom": "0px"}
    SVISData = [] if memoryData["paramsSVIS"] is None else surfaceToDf(memoryData["paramsSVIS"], "SVI-S").to_dict("records")
    volSurFit_disabled = True if (volModel == "SVI-S") or "volData" not in memoryData.keys() else False
    SVISubTable_open = True if volModel != "SVI-S" else False
    SVITable_open = True
    addMatDisabled = True if volModel == "SVI-S" else False
    delMatDisabled = True if volModel == "SVI-S" else False

    volSurfaceSVI_ref = memoryData["volSurfaceSVI_ref"]
    refSVIRowData = []
    if volSurfaceSVI_ref != None:
        if "SVI-SPX" in volSurfaceSVI_ref.keys():
            RefSVIDf = surfaceToDf(volSurfaceSVI_ref, tag="SVI-SPX")
        else:
            RefSVIDf = surfaceToDf(volSurfaceSVI_ref)
        refSVIRowData = RefSVIDf.to_dict("records")
    refGridRowData = [] if memoryData["volGrid_ref"] is None else memoryData["volGrid_ref"]
    is_open_refSVI = False if volSurfaceSVI_ref is None else True

    compareGrid = []
    if memoryData["volGrid_ref"] != None:
        for d1, d2 in zip(memoryData["volGrid"], memoryData["volGrid_ref"]):
            d = {}
            for k in d1.keys():
                if k == "Maturity":
                    d[k] = d1[k]
                elif k != "id":
                    d[k] = d1[k] - d2[k]
            compareGrid.append(d)

    return undlInfo, textAnchor, textAnchorDate, SVIData, maturities, maturity, volGrid, is_open, repoTableData, is_open_SVIS, style, SVISData, volSurFit_disabled, SVISubTable_open, SVITable_open, addMatDisabled, delMatDisabled, columnDefs, "", refGridRowData, is_open_refSVI, refSVIRowData, styleDivRepoFitted, compareGrid

@app.callback(Output("memory-vol", "data", allow_duplicate=True),
              [Input("SVISubTable", "cellValueChanged"), 
               State("memory-vol", "data"),
               State("SVISubTable", "rowData"),
               State("maturity-dropdown", "value")], prevent_initial_call=True)
def updateSVISubTable(cellValueChanged, memoryData, SVISubTableData, maturity):

    if cellValueChanged is None: return memoryData

    undlName = memoryData["undlName"]
    volSurfaceSVI = memoryData["volSurfaceSVI"]
    anchor = volSurfaceSVI["anchor"]
    anchorDate = volSurfaceSVI["anchorDate"]
    spotRef = memoryData["spotRef"]
    maturities = memoryData["maturities"]
    volModel = memoryData["volModel"]
    volTag = "SVI-SPX" if volModel == "SVI-SPX" else "SVI-JW"

    if maturity in volSurfaceSVI[volTag].keys():

        if volTag == "SVI-JW":

            volSurfaceSVI[volTag][maturity] = {"vol": float(SVISubTableData[0]["Value"])/100 if SVISubTableData[0]["Value"] != "" else SVISubTableData[0]["Value"],
                                               "skew": float(SVISubTableData[1]["Value"]) if SVISubTableData[1]["Value"] != "" else SVISubTableData[1]["Value"],
                                               "pWing": float(SVISubTableData[2]["Value"]) if SVISubTableData[2]["Value"] != "" else SVISubTableData[2]["Value"],
                                                "cWing": float(SVISubTableData[3]["Value"]) if SVISubTableData[3]["Value"] != "" else SVISubTableData[3]["Value"],
                                               "minVol": float(SVISubTableData[4]["Value"])/100 if SVISubTableData[4]["Value"] != "" else SVISubTableData[4]["Value"],
                                               "tau":  volSurfaceSVI[volTag][maturity]["tau"],
                                               "forward":  volSurfaceSVI[volTag][maturity]["forward"]}
        elif volTag == "SVI-SPX":
            volSurfaceSVI[volTag][maturity] = {"vol": float(SVISubTableData[0]["Value"])/100 if SVISubTableData[0]["Value"] != "" else SVISubTableData[0]["Value"],
                                               "skew": float(SVISubTableData[1]["Value"]) if SVISubTableData[1]["Value"] != "" else SVISubTableData[1]["Value"],
                                               "pWing": float(SVISubTableData[2]["Value"]) if SVISubTableData[2]["Value"] != "" else SVISubTableData[2]["Value"],
                                                "cWing": float(SVISubTableData[3]["Value"]) if SVISubTableData[3]["Value"] != "" else SVISubTableData[3]["Value"],
                                               "minVol": float(SVISubTableData[4]["Value"])/100 if SVISubTableData[4]["Value"] != "" else SVISubTableData[4]["Value"],
                                               "loc": float(SVISubTableData[5]["Value"]) if SVISubTableData[5]["Value"] != "" else SVISubTableData[5]["Value"],
                                               "w": float(SVISubTableData[6]["Value"]) if SVISubTableData[6]["Value"] != "" else SVISubTableData[6]["Value"],
                                               "tau":  volSurfaceSVI[volTag][maturity]["tau"],
                                               "forward":  volSurfaceSVI[volTag][maturity]["forward"]}
    
    else:

        marketDataParams = {"yieldCurve": get_yieldCurve(get_CCY(undlName)),
                            "divCurve": get_dividend(undlName),
                            "repoCurve": get_repo(undlName),
                            "calendar": get_calendar(undlName)}
        businessDaysYear = get_netBusinessDays(anchorDate, datetime.strftime(datetime.strptime(anchorDate, "%Y-%m-%d")+timedelta(365), "%Y-%m-%d"), get_calendar(undlName))["days"]
        tau = get_netBusinessDays(anchorDate, maturity, get_calendar(undlName))["days"] / businessDaysYear
        forward = calc_forward(anchor, maturity, marketDataParams, anchorDate)["forward"] / anchor

        if volTag == "SVI-JW":
            volSurfaceSVI[volTag][maturity] = {"vol": float(SVISubTableData[0]["Value"])/100 if SVISubTableData[0]["Value"] != "" else SVISubTableData[0]["Value"],
                                               "skew": float(SVISubTableData[1]["Value"]) if SVISubTableData[1]["Value"] != "" else SVISubTableData[1]["Value"],
                                               "pWing": float(SVISubTableData[2]["Value"]) if SVISubTableData[2]["Value"] != "" else SVISubTableData[2]["Value"],
                                                "cWing": float(SVISubTableData[3]["Value"]) if SVISubTableData[3]["Value"] != "" else SVISubTableData[3]["Value"],
                                               "minVol": float(SVISubTableData[4]["Value"])/100 if SVISubTableData[4]["Value"] != "" else SVISubTableData[4]["Value"],
                                               "tau":  tau,
                                               "forward":  forward}
            
        elif volTag == "SVI-SPX":
            volSurfaceSVI[volTag][maturity] = {"vol": float(SVISubTableData[0]["Value"])/100 if SVISubTableData[0]["Value"] != "" else SVISubTableData[0]["Value"],
                                               "skew": float(SVISubTableData[1]["Value"]) if SVISubTableData[1]["Value"] != "" else SVISubTableData[1]["Value"],
                                               "pWing": float(SVISubTableData[2]["Value"]) if SVISubTableData[2]["Value"] != "" else SVISubTableData[2]["Value"],
                                                "cWing": float(SVISubTableData[3]["Value"]) if SVISubTableData[3]["Value"] != "" else SVISubTableData[3]["Value"],
                                               "minVol": float(SVISubTableData[4]["Value"])/100 if SVISubTableData[4]["Value"] != "" else SVISubTableData[4]["Value"],
                                               "loc": float(SVISubTableData[5]["Value"]) if SVISubTableData[5]["Value"] != "" else SVISubTableData[5]["Value"],
                                               "w": float(SVISubTableData[6]["Value"]) if SVISubTableData[6]["Value"] != "" else SVISubTableData[6]["Value"],
                                               "tau":  tau,
                                               "forward":  forward}
    
    volSurfaceSVI[volTag] = {m:volSurfaceSVI[volTag][m] for m in sorted(list(volSurfaceSVI[volTag].keys()))}
    gridDf = genVolGrid(volSurfaceSVI, volTag, spotRef, maturities, volGridStrikes)
    grid = gridDf.to_dict("records")
    #gridDf_records = [d for d in memoryData["volGrid"] if d["Maturity"] < grid[0]["Maturity"]] + grid + [d for d in memoryData["volGrid"] if d["Maturity"] > grid[0]["Maturity"]]

    curveGrid = genVolGrid(volSurfaceSVI, volTag, spotRef, maturities, curveGridStrikes, returnType="dict")
    #curveGrid = memoryData["curveGrid"]
    #curveGrid[maturity] = curveGrid_tmp[maturity]

    memoryData["volSurfaceSVI"] = volSurfaceSVI
    memoryData["volGrid"] = grid
    memoryData["curveGrid"] = curveGrid

    return memoryData

@app.callback(Output("memory-vol", "data", allow_duplicate=True), 
              [Input("isCalc-Vol", "data"), State("memory-vol", "data")], prevent_initial_call=True)
def calcVolPage(isCalc, memoryData):

    if isCalc is None:
        return memoryData
    else:
        volSurfaceSVI = memoryData["volSurfaceSVI"]
        volModel = memoryData["volModel"]
        volTag = "SVI-SPX" if volModel == "SVI-SPX" else "SVI-JW"
        spotRef = memoryData["spotRef"]
        maturities = memoryData["maturities"]

        volGrid = genVolGrid(volSurfaceSVI, volTag, spotRef, maturities, volGridStrikes)
        curveGrid = genVolGrid(volSurfaceSVI, volTag, spotRef, maturities, curveGridStrikes, returnType="dict")

        memoryData["volGrid"] = volGrid.to_dict("records")
        memoryData["curveGrid"] = curveGrid
        memoryData["progress_id"] = None

        return memoryData

@app.callback([Output("graph-area", "children"), 
               Output("SVISubTable", "rowData", allow_duplicate=True),
               Output("SVISubTable2", "rowData", allow_duplicate=True),
               Output("memory-vol-subParams", "data", allow_duplicate=True),
               Output("SVITable", "selectedRows", allow_duplicate=True),
               Output("GridTable", "selectedRows", allow_duplicate=True),
               Output("SVISubTable", "columnDefs")],
              [Input("maturity-dropdown", "value"), 
               State("maturity-dropdown", "options"),
               State("memory-vol", "data"),
               State("SVISubTable", "rowData"),
               State("graph-volSmile", "figure"),
               State("SVITable", "rowData"),
               State("GridTable", "rowData")], prevent_initial_call=True)
def changeMaturity(m, maturities, memoryData, subTableData, figure, rowData_SVI, rowData_Grid):

    undlName = memoryData["undlName"]
    spotRef = memoryData["spotRef"]
    volSurfaceSVI = memoryData["volSurfaceSVI"]
    volSurfaceSVI_backup = memoryData["volSurfaceSVI_backup"]
    volModel = memoryData["volModel"]
    volTag = "SVI-SPX" if volModel == "SVI-SPX" else "SVI-JW"

    columnDefs=[{"field": "Param", "minWidth": 85, "maxWidth": 85, "pinned": "left", "type": "rightAligned"},
                                            {"field": "Value", "minWidth": 110, 
                                             "valueFormatter": {"function": "d3.format(',.2f')(params.value)"},
                                             "editable": True,
                                             "cellStyle": {"background-color": "#fffee0"},
                                             "type": "numericColumn"}]

    if volSurfaceSVI[volTag] != {}:

        if m in memoryData["curveGrid"].keys():
            
            if m in volSurfaceSVI[volTag].keys():
                if sum([1 if v != "" else 0 for v in volSurfaceSVI[volTag][m].values()]) != len(volSurfaceSVI[volTag][m].values()):
                    vols = [0 for v in list(memoryData["curveGrid"][m].values())]
                else:
                    vols = list(memoryData["curveGrid"][m].values())
            else:
                vols = list(memoryData["curveGrid"][m].values())

            volDf = pd.DataFrame.from_dict({"Strike": curveGridStrikes, m: vols})
            fig = px.line(volDf, x="Strike", y=m)

            if m in volSurfaceSVI[volTag].keys():
                subTableData = [{"Param": "Vol", "Value": volSurfaceSVI[volTag][m]["vol"] * 100, "id": 0},
                                {"Param": "Skew", "Value": volSurfaceSVI[volTag][m]["skew"], "id": 1},
                                {"Param": "P Wing", "Value": volSurfaceSVI[volTag][m]["pWing"], "id": 2},
                                {"Param": "C Wing", "Value": volSurfaceSVI[volTag][m]["cWing"], "id": 3},
                                {"Param": "Min Vol", "Value": volSurfaceSVI[volTag][m]["minVol"] * 100, "id": 4}]
                
                if volTag == "SVI-SPX":
                    subTableData += [{"Param": "Loc", "Value": volSurfaceSVI[volTag][m]["loc"], "id": 5},
                                     {"Param": "W", "Value": volSurfaceSVI[volTag][m]["w"], "id": 6}]
                
                subTableData2 = [{"Ref": "Tau", "Value": volSurfaceSVI[volTag][m]["tau"]},
                                {"Ref": "Forward", "Value": volSurfaceSVI[volTag][m]["forward"] * 100}]

            else:
                subTableData = [{"Param": "Vol", "Value": "", "id": 0},
                                {"Param": "Skew", "Value": "", "id": 1},
                                {"Param": "P Wing", "Value": "", "id": 2},
                                {"Param": "C Wing", "Value": "", "id": 3},
                                {"Param": "Min Vol", "Value": "", "id": 4}]
                
                if volTag == "SVI-SPX":
                    subTableData += [{"Param": "Loc", "Value": "", "id": 5},
                                     {"Param": "W", "Value": "", "id": 6}]
                
                subTableData2 = [{"Ref": "Tau", "Value": "Nil"},
                                {"Ref": "Forward", "Value": "Nil"}]

            # highlight changes
            mapDict = {0: "vol", 1: "skew", 2: "pWing", 3: "cWing", 4: "minVol", 5: "loc", 6: "w"}
            if m in volSurfaceSVI_backup[volTag].keys():

                toHighLight = []
                for data in subTableData:
                    if data["id"] in [0, 4]:
                        if data["Value"] != volSurfaceSVI_backup[volTag][m][mapDict[data["id"]]] * 100:
                            toHighLight.append(data["id"])
                    else:
                        if data["Value"] != volSurfaceSVI_backup[volTag][m][mapDict[data["id"]]]:
                            toHighLight.append(data["id"])

                columnDefs = [{"field": "Param", "minWidth": 85, "maxWidth": 85, "pinned": "left", "type": "rightAligned"}] + \
                    [{"field": "Value", 
                      "valueFormatter": {"function": "d3.format(',.2f')(params.value)"}, 
                      "editable": True,
                      "cellStyle": {"styleConditions": [{"condition": "params.node.id == " + str(idx), "style": {"background-color": "red"}} for idx in toHighLight], 
                                    "defaultStyle": {"background-color": "#fffee0"}},
                                    "minWidth": 110,
                                    "type": "numericColumn"}]
                
            else:

                toHighLight = []
                for data in subTableData:
                    if data["Value"] != "":
                        toHighLight.append(data["id"])

                columnDefs = [{"field": "Param", "minWidth": 85, "maxWidth": 85, "pinned": "left", "type": "rightAligned"}] + \
                    [{"field": "Value", 
                      "valueFormatter": {"function": "d3.format(',.2f')(params.value)"}, 
                      "editable": True,
                      "cellStyle": {"styleConditions": [{"condition": "params.node.id == " + str(idx), "style": {"background-color": "red"}} for idx in toHighLight], 
                                    "defaultStyle": {"background-color": "#fffee0"}},
                                    "minWidth": 110,
                                    "type": "numericColumn"}]
            
        else:

            strikes = curveGridStrikes
            vols = [0 for k in strikes]
            volDf = pd.DataFrame.from_dict({"Strike": strikes, m: vols})
            fig = px.line(volDf, x="Strike", y=m)  
            subTableData = [{"Param": "Vol", "Value": ""},
                            {"Param": "Skew", "Value": ""},
                            {"Param": "P Wing", "Value": ""},
                            {"Param": "C Wing", "Value": ""},
                            {"Param": "Min Vol", "Value": ""}]
            
            if volTag == "SVI-SPX":
                subTableData += [{"Param": "Loc", "Value": ""},
                                 {"Param": "W", "Value": ""}]
            
            subTableData2 = [{"Ref": "Tau", "Value": "Nil"},
                                {"Ref": "Forward", "Value": "Nil"}]
            
    else:

        strikes = curveGridStrikes
        vols = [0 for k in strikes]
        volDf = pd.DataFrame.from_dict({"Strike": strikes, m: vols})
        fig = px.line(volDf, x="Strike", y=m)
        subTableData = []
        subTableData2 = []

    if memoryData != None:
        
        if memoryData["curveGrid_ref"] != None:
            if m in memoryData["curveGrid_ref"].keys():

                vols = list(memoryData["curveGrid_ref"][m].values())
                fig.add_scatter(x=curveGridStrikes, y=vols, mode="lines", name="Ref Surface", line=go.scatter.Line(color="Red", width=0.9))

        if "volData" in memoryData.keys():
            volDataSpotRef = float(memoryData["volData"]["spotRef"])
            if m in memoryData["volData"]["call"]["bid"].keys() and memoryData["volData"]["undlName"] == undlName:
                if m in memoryData["volData"]["call"]["bid"].keys():
                    fig.add_scatter(x=np.asarray(list(memoryData["volData"]["call"]["bid"][m].keys()), dtype="float64") * volDataSpotRef / spotRef, 
                                    y=list(memoryData["volData"]["call"]["bid"][m].values()), mode="markers", name="Call Bid", marker=dict(color="#E34A33"))
                if m in memoryData["volData"]["call"]["ask"].keys():
                    fig.add_scatter(x=np.asarray(list(memoryData["volData"]["call"]["ask"][m].keys()), dtype="float64") * volDataSpotRef / spotRef, 
                                    y=list(memoryData["volData"]["call"]["ask"][m].values()), mode="markers", name="Call Ask", marker=dict(color="#31a354"))
                if m in memoryData["volData"]["put"]["bid"].keys():
                    fig.add_scatter(x=np.asarray(list(memoryData["volData"]["put"]["bid"][m].keys()), dtype="float64") * volDataSpotRef / spotRef, 
                                    y=list(memoryData["volData"]["put"]["bid"][m].values()), mode="markers", name="Put Bid", marker=dict(color="Magenta"))
                if m in memoryData["volData"]["put"]["ask"].keys():
                    fig.add_scatter(x=np.asarray(list(memoryData["volData"]["put"]["ask"][m].keys()), dtype="float64") * volDataSpotRef / spotRef, 
                                    y=list(memoryData["volData"]["put"]["ask"][m].values()), mode="markers", name="Put Ask", marker=dict(color="#fec44f"))

    fig = go.Figure(fig, layout_yaxis_range = figure["layout"]["yaxis"]["range"], layout_xaxis_range = figure["layout"]["xaxis"]["range"])

    if m in volSurfaceSVI[volTag].keys():
        memorySubParams = volSurfaceSVI[volTag][m]
    else:
        memorySubParams = None

    selected_SVI = []
    for data in rowData_SVI:
        if data["Maturity"] == m:
            selected_SVI = [data]
            break

    selected_Grid = []
    for data in rowData_Grid:
        if data["Maturity"] == m:
            selected_Grid = [data]
            break

    result = [dcc.Graph(id="graph-volSmile", figure=fig, style={'width': '1500px', 'height': '650px', "margin-left": 0, "margin-right": 0, "margin-top":0 , "margin-bottom": 0}), 
              subTableData, 
              subTableData2, 
              memorySubParams, 
              selected_SVI, 
              selected_Grid,
              columnDefs]
    
    return result

@app.callback(Output("memory-vol", "data", allow_duplicate=True), 
              [Input("SVITable", "cellValueChanged"), 
               State("memory-vol", "data"),
               State("SVITable", "rowData")], prevent_initial_call=True)
def updateSVITable(cellValueChanged, memoryData, SVIData):

    if cellValueChanged is None: return memoryData

    volSurfaceSVI = memoryData["volSurfaceSVI"]
    anchor = volSurfaceSVI["anchor"]
    anchorDate = volSurfaceSVI["anchorDate"]
    spotRef = memoryData["spotRef"]
    maturities = memoryData["maturities"]
    volModel = memoryData["volModel"]
    volTag = "SVI-SPX" if volModel == "SVI-SPX" else "SVI-JW"

    volSurfaceSVI = {"undlName": memoryData["undlName"], 
                     "anchor": anchor, 
                     "anchorDate": anchorDate, 
                     "lastUpdate": os.getlogin(),
                     "lastUpdateTime": datetime.strftime(datetime.now(), "%Y-%m-%dT%H:%M:%S"),
                     volTag: dataToSurface(SVIData)}
    
    gridDf = genVolGrid(volSurfaceSVI, volTag, spotRef, maturities, volGridStrikes)
    curveGrid = genVolGrid(volSurfaceSVI, volTag, spotRef, maturities, curveGridStrikes, returnType="dict")

    memoryData["volSurfaceSVI"] = volSurfaceSVI
    memoryData["volGrid"] = gridDf.to_dict("records")
    memoryData["curveGrid"] = curveGrid

    return memoryData

@app.callback(Output("memory-vol", "data", allow_duplicate=True),
              [Input("SVISTable", "cellValueChanged"), State("memory-vol", "data"), State("SVISTable", "rowData")], prevent_initial_call=True)
def updateSVISTable(cellValueChanged, memoryData, SVISData):

    if cellValueChanged is None: return memoryData

    volSurfaceSVI = memoryData["volSurfaceSVI"]
    anchor = volSurfaceSVI["anchor"]
    anchorDate = volSurfaceSVI["anchorDate"]
    spotRef = memoryData["spotRef"]
    maturities = memoryData["maturities"]
    volModel = memoryData["volModel"]
    volTag = "SVI-SPX" if volModel == "SVI-SPX" else "SVI-JW"

    paramsSVIS = {"undlName": memoryData["undlName"],
                  "anchor": anchor,
                  "anchorDate": anchorDate,
                  "SVI-S": {"vol": {"st": float(SVISData[0]["Vol"])/100, "lt": float(SVISData[1]["Vol"])/100, "strength": float(SVISData[2]["Vol"])/100}, 
                            "skew": {"st": float(SVISData[0]["Skew"]), "lt": float(SVISData[1]["Skew"]), "strength": float(SVISData[2]["Skew"])}, 
                            "convex": {"st": float(SVISData[0]["Convex"]), "lt": float(SVISData[1]["Convex"]), "strength": float(SVISData[2]["Convex"])}}}
    
    volSurfaceSVI = SVISToSVIJW(paramsSVIS, maturities)

    gridDf = genVolGrid(volSurfaceSVI, volTag, spotRef, maturities, volGridStrikes)
    curveGrid = genVolGrid(volSurfaceSVI, volTag, spotRef, maturities, curveGridStrikes, returnType="dict")

    memoryData["paramsSVIS"] = paramsSVIS
    memoryData["volSurfaceSVI"] = volSurfaceSVI
    memoryData["volGrid"] = gridDf.to_dict("records")
    memoryData["curveGrid"] = curveGrid

    return memoryData

@app.callback(Output("maturity-dropdown", "value", allow_duplicate=True),
              [Input("SVITable", "selectedRows"), 
               State("maturity-dropdown", "value"),
               State("GridTable", "rowData"),
               State("GridTable", "selectedRows")], prevent_initial_call=True)
def updateMaturityFromSVITable(selected, maturity, rowData, selected_grid):

    if selected != None and selected != []:
        maturity = selected[0]["Maturity"]

    return maturity

@app.callback(Output("maturity-dropdown", "value", allow_duplicate=True),
              [Input("GridTable", "selectedRows"), 
               State("maturity-dropdown", "value")], prevent_initial_call=True)
def updateMaturityFromGridTable(selected, maturity):

    if selected != None and selected != []:
        maturity = selected[0]["Maturity"]

    return maturity

@app.callback(Output("memory-vol", "data", allow_duplicate=True), 
              [Input("table-volUndlInfo", "cellValueChanged"), 
               State("memory-vol", "data")], prevent_initial_call=True)
def changeVolUndlInfo(cellValueChanged, memoryData):

    if cellValueChanged != None:

        if cellValueChanged["colId"] == "Spot Ref":
            
            spotRef = float(cellValueChanged["value"])

            volSurfaceSVI = memoryData["volSurfaceSVI"]
            maturities = memoryData["maturities"]
            volModel = memoryData["volModel"]
            volTag = "SVI-SPX" if volModel == "SVI-SPX" else "SVI-JW"
            
            #volSurfaceSVI = {"undlName": undlName, "anchor": anchor, "anchorDate": anchorDate, "SVI-JW": dataToSurface(data)}
            gridDf = genVolGrid(volSurfaceSVI, volTag, spotRef, maturities, volGridStrikes)
            curveGrid = genVolGrid(volSurfaceSVI, volTag, spotRef, maturities, curveGridStrikes, returnType="dict")
            memoryData["curveGrid"] = curveGrid

            memoryData["spotRef"] = spotRef
            memoryData["volGrid"] = gridDf.to_dict("records")
            #memoryData["curveGrid"] = curveGrid
        
            return memoryData
        
        if cellValueChanged["colId"] == "Vol Model":
            
            volModel = cellValueChanged["value"]
            volTag = "SVI-SPX" if volModel == "SVI-SPX" else "SVI-JW"
            memoryData["volModel"] = volModel
            
            if cellValueChanged["value"] == "SVI-S":
                
                undlName = memoryData["undlName"]
                spotRef = memoryData["spotRef"]
                valueDate = memoryData["valueDate"]

                if memoryData["paramsSVIS"] is None:
                    paramsSVIS = {"undlName": undlName,
                                  "anchor": spotRef,
                                  "anchorDate": valueDate,
                                  "SVI-S": {"vol": {"st": 0.2, "lt": 0.2, "strength": 1}, 
                                            "skew": {"st": -0.1, "lt": -0.1, "strength": 1}, 
                                            "convex": {"st": 1, "lt": 1, "strength": 1}}}
                else:
                    paramsSVIS = memoryData["paramsSVIS"]

                maturities = sorted(list(set(listedMaturities[get_calendar(undlName)+"_"+get_undlType(undlName)] + memoryData["maturities"])))
                maturities = [m for m in maturities if m > valueDate]
                volSurfaceSVI = SVISToSVIJW(paramsSVIS, maturities)

                gridDf = genVolGrid(volSurfaceSVI, volTag, spotRef, maturities, volGridStrikes)
                curveGrid = genVolGrid(volSurfaceSVI, volTag, spotRef, maturities, curveGridStrikes, returnType="dict")

                memoryData["maturities"] = maturities
                memoryData["paramsSVIS"] = paramsSVIS
                memoryData["volSurfaceSVI"] = volSurfaceSVI
                memoryData["volGrid"] = gridDf.to_dict("records")
                memoryData["curveGrid"] = curveGrid
    
    return memoryData

@app.callback(Output("maturity-dropdown", "value", allow_duplicate=True), 
              [Input("button-up", "n_clicks"), State("maturity-dropdown", "value"), State("maturity-dropdown", "options")], prevent_initial_call=True)
def changeMaturityUp(n_clicks, m, options):

    if n_clicks > 0:
        if m is None:
            loc = 0
        else:
            loc = options.index(m)
        if loc > 0:
            return options[loc-1]
    return m

@app.callback(Output("maturity-dropdown", "value", allow_duplicate=True), 
              [Input("button-down", "n_clicks"), State("maturity-dropdown", "value"), State("maturity-dropdown", "options")], prevent_initial_call=True)
def changeMaturityDown(n_clicks, m, options):

    if n_clicks > 0:
        if m is None:
            loc = 0
        else:
            loc = options.index(m)
        if loc < len(options) - 1:
            return options[loc+1]
    return m

@app.callback(Output("modal-addMat", "is_open", allow_duplicate=True),
              [Input("button-addMat", "n_clicks"), Input("close-modal-addMat", "n_clicks"), State("modal-addMat", "is_open")], prevent_initial_call=True)
def addMaturity(n1, n2, is_open):

    if n1 or n2:
        return not is_open
    return is_open

@app.callback([Output("memory-vol", "data", allow_duplicate=True), 
               Output("message-modal", "children", allow_duplicate=True),
               Output("modal-addMat", "is_open", allow_duplicate=True)],
              [Input("add-modal-addMat", "n_clicks"), State("input-addMat", "value"), State("memory-vol", "data")], prevent_initial_call=True)
def addMaturity2(n_clicks, maturity, memoryData):

    if n_clicks:

        def checkValidDateStr(mStr):

            try:
                d = datetime.strptime(mStr, "%Y-%m-%d").strftime("%Y-%m-%d")
                if d > memoryData["valueDate"]:
                    return True
                else:
                    return False
            except:
                return False
        
        if maturity in memoryData["maturities"]:

            return memoryData, "Maturity already exists", True

        elif checkValidDateStr(maturity):

            maturities = memoryData["maturities"]
            maturities = sorted(list(set(maturities + [maturity])))
            memoryData["maturities"] = maturities

        else:

            return memoryData, "Invalid Date", True

    return memoryData, "", False

@app.callback([Output("modal-loadRef", "is_open", allow_duplicate=True), 
               Output("modal-undlName-dropdown", "options", allow_duplicate=True),
               Output("modal-undlName-dropdown", "value", allow_duplicate=True),
               Output("date-picker-loadRef", "date", allow_duplicate=True),
               Output("message-modal-loadRef", "children", allow_duplicate=True)],
              [Input("button-loadRef", "n_clicks"), 
               Input("button-modal-close", "n_clicks"), 
               State("modal-loadRef", "is_open"), 
               State("undlName-dropdown", "value"),
               State("undlName-dropdown", "options"),
               State("memory-vol", "data")], prevent_initial_call=True)
def loadRef(n1, n2, is_open, undlName, options, memoryData):

    dt = datetime.strptime(memoryData["valueDate"], "%Y-%m-%d")
    if n1 or n2:
        return not is_open, options, undlName, dt.date(), ""
    return is_open, options, undlName, dt.date(), ""

@app.callback([Output("memory-vol", "data", allow_duplicate=True), 
               Output("message-modal-loadRef", "children", allow_duplicate=True),
               Output("message-modal-loadRef", "style", allow_duplicate=True),
               Output("modal-loadRef", "is_open", allow_duplicate=True),
               Output("collapse-refGrid", "is_open", allow_duplicate=True)],
              [Input("button-modal-load", "n_clicks"), 
               State("modal-undlName-dropdown", "value"), 
               State("date-picker-loadRef", "date"),
               State("memory-vol", "data")], prevent_initial_call=True)
def loadRef2(n_clicks, refUndlName, refDate, memoryData):

    if n_clicks:

        if refDate == memoryData["valueDate"]:
            volSurfaceSVI_ref = get_volSurfaceSVI(refUndlName)
            if volSurfaceSVI_ref == None: return memoryData, "Vol Surface doesn't exist currently", {"color": "red"}, True, False
            refDate = None
        else:
            volSurfaceSVI_ref = get_volSurfaceSVI(refUndlName, refDate)
            if volSurfaceSVI_ref == None: return memoryData, "Vol Surface doesn't exist on " + refDate, {"color": "red"}, True, False
        
        undlName = memoryData["undlName"]
        volTag = "SVI-JW" if "SVI-JW" in volSurfaceSVI_ref else "SVI-SPX"
        maturities = memoryData["maturities"]

        if undlName == refUndlName:

            spotRef = memoryData["spotRef"]
            gridDf = genVolGrid(volSurfaceSVI_ref, volTag, spotRef, maturities, volGridStrikes, historicalDate=refDate)
            curveGrid = genVolGrid(volSurfaceSVI_ref, volTag, spotRef, maturities, curveGridStrikes, returnType="dict", historicalDate=refDate)

            memoryData["refDate"] = refDate
            memoryData["volSurfaceSVI_ref"] = volSurfaceSVI_ref
            memoryData["volGrid_ref"] = gridDf.to_dict("records")
            memoryData["curveGrid_ref"] = curveGrid

        else:

            spotRef = volSurfaceSVI_ref["anchor"]
            gridDf = genVolGrid(volSurfaceSVI_ref, volTag, spotRef, maturities, volGridStrikes, historicalDate=refDate)
            curveGrid = genVolGrid(volSurfaceSVI_ref, volTag, spotRef, maturities, curveGridStrikes, returnType="dict", historicalDate=refDate)

            memoryData["refDate"] = refDate
            memoryData["volSurfaceSVI_ref"] = volSurfaceSVI_ref
            memoryData["volGrid_ref"] = gridDf.to_dict("records")
            memoryData["curveGrid_ref"] = curveGrid

    return memoryData, "", {}, False, True

@app.callback([Output("confirm-delMat", "displayed", allow_duplicate=True), Output("confirm-delMat", "message", allow_duplicate=True)],
              [Input("button-delMat", "n_clicks"), State("memory-vol", "data"), State("SVITable", "selectedRows")], prevent_initial_call=True)
def delMat(n, memoryData, selected):

    if n:
        if selected is None:
            return True, "No maturity selected"
        if selected == []:
            return True, "No maturity selected"
        if selected != []:
            return True, "Confirm deleting " + selected[0]["Maturity"] + "?"

    return False, ""

@app.callback(Output("memory-vol", "data", allow_duplicate=True),
              [Input("confirm-delMat", "submit_n_clicks"), State("memory-vol", "data"), State("SVITable", "selectedRows")], prevent_initial_call=True)
def delMatConfirmed(submit_n_clicks, memoryData, selected):

    if submit_n_clicks:

        if selected != None and selected != []:

            volSurfaceSVI = memoryData["volSurfaceSVI"]
            volModel = memoryData["volModel"]
            volTag = "SVI-SPX" if volModel == "SVI-SPX" else "SVI-JW"
            maturity = selected[0]["Maturity"]

            if maturity in volSurfaceSVI[volTag].keys():

                volSurfaceSVI[volTag].pop(selected[0]["Maturity"])
                spotRef = memoryData["spotRef"]
                maturities = memoryData["maturities"]

                gridDf = genVolGrid(volSurfaceSVI, volTag, spotRef, maturities, volGridStrikes)
                curveGrid = genVolGrid(volSurfaceSVI, volTag, spotRef, maturities, curveGridStrikes, returnType="dict")

                memoryData["volSurfaceSVI"] = volSurfaceSVI
                memoryData["volGrid"] = gridDf.to_dict("records")
                memoryData["curveGrid"] = curveGrid
    
    return memoryData

@app.callback(Output("confirm-reloadVol", "displayed"), 
              [Input("button-loadVol", "n_clicks"),], prevent_initial_call=True)
def loadVol(n_clicks):

    if n_clicks:

        return True
    
    return False

@app.callback([Output("page-content", "children", allow_duplicate=True), Output("memory-vol", "data", allow_duplicate=True)],
              [Input("confirm-reloadVol", "submit_n_clicks"), 
               State("undlName-dropdown", "value"),
               State("page-content", "children"),
               State("memory-vol", "data")], prevent_initial_call=True)
def reloadVolConfirmed(submit_n_clicks, undlName, content, memoryData):

    if submit_n_clicks:
        
        return createContentVolatility(undlName, None)
    
    return content, memoryData

@app.callback(Output("page-content", "children", allow_duplicate=True), 
              [Input("button-loadSetting", "n_clicks"),], prevent_initial_call=True)
def loadSetting(n_clicks):

    if n_clicks:

        return createContentSetting()
    
    return createContentSetting()

@app.callback(Output("text-settingPageStatus", "children", allow_duplicate=True), 
              [Input("button-saveSetting", "n_clicks"), State("dropdown-BBGData", "value")], prevent_initial_call=True)
def saveSetting(n_clicks, value):

    if n_clicks:

        if value == "True":
            data = {"BBGData": 1}
            useBBGData = 1
        else:
            data = {"BBGData": 0}
            useBBGData = 0

        with open("UserConfig.json", "w") as f:
            json.dump(data, f, indent=2)
        
        return "Status: successfully saved"

    return "Status: "

@app.callback(Output("confirm-uploadVol", "displayed"), 
              [Input("button-saveVol", "n_clicks"),])
def uploadVolSurf(n_clicks):

    if n_clicks:

        return True
    
    return False

@app.callback([Output("text-volPageStatus", "children", allow_duplicate=True), 
               Output("text-volPageStatus", "style", allow_duplicate=True)],
              [Input("confirm-uploadVol", "submit_n_clicks"), State("memory-vol", "data"), State("text-volPageStatus", "children")], prevent_initial_call=True)
def uploadVolSurfConfirmed(submit_n_clicks, memoryData, statusChildren):

    if submit_n_clicks:
        volSurfaceSVI = memoryData["volSurfaceSVI"]
        volSurfaceSVI["lastUpdate"] = os.getlogin()
        volSurfaceSVI["lastUpdateTime"] = datetime.strftime(datetime.now(), "%Y-%m-%dT%H:%M:%S")
        volModel = memoryData["volModel"]
        volTag = "SVI-SPX" if volModel == "SVI-SPX" else "SVI-JW"
        volSurfaceSVI[volTag] = {m:p for m,p in volSurfaceSVI[volTag].items() if sum([1 if v != "" else 0 for v in volSurfaceSVI[volTag][m].values()]) == len(volSurfaceSVI[volTag][m].values())}
        
        if volSurfaceSVI[volTag] == {}:
            return "Status: No Vol Surface to upload", {"color": "red"}
        
        status = upload_volSurfaceSVI(volSurfaceSVI)

        if status["status"] == "Vol Surface uploaded":
            return f"Status: {status['status']}", {"color": "green"}
        else:
            return f"Status: {status['status']}", {"color": "red"}
    
    return statusChildren, {"color": "black"}

@app.callback([Output("text-arbCheck", "children"), Output("GridTable", "columnDefs"), Output("text-arbCheck", "style")],
              [Input("button-checkArb", "n_clicks"), 
               State("memory-vol", "data")], prevent_initial_call=True)
def checkVolSurfaceArb(n_clicks, memoryData):

    undlName = memoryData["undlName"]
    spotRef = memoryData["spotRef"]
    maturities = memoryData["maturities"]
    volSurfaceSVI = memoryData["volSurfaceSVI"]
    volModel = memoryData["volModel"]
    volTag = "SVI-SPX" if volModel == "SVI-SPX" else "SVI-JW"
    
    #if memoryData is None:
    #    repo = get_repo(undlName)
    #elif "repoFitted" not in memoryData.keys():
    #    repo = get_repo(undlName)
    #else:
    #    repo = memoryData["repoFitted"]
    # use system repo for arb check
    repo = get_repo(undlName)
    marketDataDict = {"yieldCurve": get_yieldCurve(get_CCY(undlName)),
                      "divCurve": get_dividend(undlName),
                      "repoCurve": repo,
                      "calendar": get_calendar(undlName)}
    valueDate = memoryData["valueDate"]

    result = check_volSurfaceArb(volSurfaceSVI, marketDataDict, valueDate)

    butterflyArb = result["butterfly"]
    calendarArb = result["calendar"]
    checkGrid = result["checkGrid"]

    butterflyArb = {k: int(v) for k,v in butterflyArb.items()}
    calendarArb = {float(k): int(v) for k,v in calendarArb.items()}
    checkGrid = {m:{float(k):int(v) for k,v in smile.items()} for m,smile in checkGrid.items()}

    bfCheck = "Pass" if sum(list(butterflyArb.values()))==len(butterflyArb.items()) else "Fail"
    calCheck = "Pass" if sum(list(calendarArb.values()))==len(calendarArb.items()) else "Fail"

    columnDefs = displayVolArb(volSurfaceSVI, volTag, spotRef, maturities, checkGrid, strikes=None)

    if bfCheck == "Pass" and calCheck == "Pass":
        return f"Butterfly Arbitrage Check: {bfCheck} / Calendar Arbitrage Check: {calCheck}", columnDefs, {"color": "green"}
    else:
        return f"Butterfly Arbitrage Check: {bfCheck} / Calendar Arbitrage Check: {calCheck}", columnDefs, {"color": "red"}

@app.callback(Output("collapse-grid", "is_open"),
              [Input("button-showVolGrid", "n_clicks")],
              [State("collapse-grid", "is_open")],)
def toggle_collapse(n, is_open):
    if n:
        return not is_open
    return is_open

@app.callback(Output("collapse-refGrid", "is_open"),
              [Input("button-showRefGrid", "n_clicks")],
              [State("collapse-refGrid", "is_open")],)
def toggle_collapse2(n, is_open):
    if n:
        return not is_open
    return is_open


@app.callback(Output("memory-vol", "data", allow_duplicate=True),
              [Input("button-reanchor", "n_clicks"), State("memory-vol", "data")], prevent_initial_call=True)
def reanchor(n_clicks, memoryData):

    if n_clicks:

        undlName = memoryData["undlName"]
        volModel = memoryData["volModel"]
        spotRef = memoryData["spotRef"]
        volTag = "SVI-JW" if volModel != "SVI-SPX" else "SVI-SPX"

        if volModel == "SVI-S":

            paramsSVIS = memoryData["paramsSVIS"]
            maturities = memoryData["maturities"]
            paramsSVIS["anchor"] = spotRef
            paramsSVIS["anchorDate"] = memoryData["valueDate"]
            volSurfaceSVI = SVISToSVIJW(paramsSVIS, memoryData["maturities"])

            gridDf = genVolGrid(volSurfaceSVI, volTag, spotRef, maturities, volGridStrikes)
            curveGrid = genVolGrid(volSurfaceSVI, volTag, spotRef, maturities, curveGridStrikes, returnType="dict")

            memoryData["paramsSVIS"] = paramsSVIS
            memoryData["volSurfaceSVI"] = volSurfaceSVI
            memoryData["volGrid"] = gridDf.to_dict("records")
            memoryData["curveGrid"] = curveGrid

            return memoryData
        
        elif volModel == "SVI-JW" or volModel == "SVI-SPX":
            
            volSurfaceSVI = memoryData["volSurfaceSVI"]
            maturities = memoryData["maturities"]

            anchor = spotRef
            anchorDate = memoryData["valueDate"]

            volSurfaceSVI["anchor"] = anchor
            volSurfaceSVI["anchorDate"] = anchorDate

            calendar = get_calendar(undlName)
            businessDaysYear = get_netBusinessDays(anchorDate, datetime.strftime(datetime.strptime(anchorDate, "%Y-%m-%d")+timedelta(365), "%Y-%m-%d"), calendar)["days"]
            marketDataParams = {"yieldCurve": get_yieldCurve(get_CCY(undlName)),
                                "divCurve": get_dividend(undlName),
                                "repoCurve": get_repo(undlName),
                                "calendar": calendar}

            for maturity in volSurfaceSVI[volTag].keys():
                
                if maturity > anchorDate:

                    tau = get_netBusinessDays(anchorDate, maturity, calendar)["days"] / businessDaysYear
                
                    forward = calc_forward(anchor, maturity, marketDataParams, anchorDate)["forward"] / anchor
                    volSurfaceSVI[volTag][maturity]["tau"] = tau
                    volSurfaceSVI[volTag][maturity]["forward"] = forward

            volSurfaceSVI[volTag] = {m:p for m,p in volSurfaceSVI[volTag].items() if m > anchorDate}

            gridDf = genVolGrid(volSurfaceSVI, volTag, spotRef, maturities, volGridStrikes)
            curveGrid = genVolGrid(volSurfaceSVI, volTag, spotRef, maturities, curveGridStrikes, returnType="dict")

            memoryData["volSurfaceSVI"] = volSurfaceSVI
            memoryData["volGrid"] = gridDf.to_dict("records")
            memoryData["curveGrid"] = curveGrid

            return memoryData
    
    return memoryData

@app.callback([Output("modal-loadOptionChain", "is_open", allow_duplicate=True),
               Output("modal-volData-dropdown", "options", allow_duplicate=True)],
              [Input("button-loadChainVol", "n_clicks"), 
               Input("button-modal-closeOptionChain", "n_clicks"), 
               State("modal-loadOptionChain", "is_open"), 
               State("memory-vol", "data")], prevent_initial_call=True)
def loadOptionChainType(n1, n2, is_open, memoryData):

    if n1 or n2:
        
        result = get_optionChainVolLazy(memoryData["undlName"])
        if "error" in result.keys(): 
            return not is_open, ["Live"]
        elif result["lastVol"] is None:
            return not is_open, ["Live"]
        else:
            return not is_open, ["Live", str(result["lastVol"])]
        
    return is_open, ["Live"]

@app.callback([Output("memory-vol", "data", allow_duplicate=True),
               Output("button-loadVol", "disabled", allow_duplicate=True),
               Output("button-saveVol", "disabled", allow_duplicate=True),
               Output("button-loadChainVol", "disabled", allow_duplicate=True),
               Output("button-fitVolSurf", "disabled", allow_duplicate=True),
               Output("button-checkArb", "disabled", allow_duplicate=True),
               Output("button-loadRef", "disabled", allow_duplicate=True),
               Output("button-restoreParams", "disabled", allow_duplicate=True),
               Output("button-reanchor", "disabled", allow_duplicate=True),
               Output("button-addMat", "disabled", allow_duplicate=True),
               Output("button-delMat", "disabled", allow_duplicate=True)],
              [Input("memory-getOptionChainVol", "data"),
               State("memory-vol", "data")], prevent_initial_call=True)
def loadOptionChainVol2(tmpData, memoryData):

    if tmpData != None:

        undlName = memoryData["undlName"]
        volSurfaceSVI = memoryData["volSurfaceSVI"]
        volModel = memoryData["volModel"]
        volTag = "SVI-SPX" if volModel == "SVI-SPX" else "SVI-JW"

        # get data
        OC = retrieveOptionChain(undlName)
        optionChainData = processOptionChainRawData(undlName, OC)
        result = get_optionChainVol(optionChainData)

        if "error" not in result.keys():

            repoFitted = result["repoFitted"]
            optionChain = result["optionChain"]
            volData = result["volData"]

            maturities = sorted(list(set(list(repoFitted["Schedule"].keys()) + listedMaturities[get_calendar(undlName)+"_"+get_undlType(undlName)] + list(memoryData["volSurfaceSVI"][volTag].keys()))))
            maturities = [m for m in maturities if m > memoryData["valueDate"]]

            repoTableData = []
            systemDivPoints, impliedDivPoints = getOptionImpliedDiv(repoFitted, volData["spotRef"])
            tmpDict = {"Date": list(repoFitted["Schedule"].keys()), 
                        "ImpiledRepo": list(repoFitted["Schedule"].values()), 
                        "SystemDiv": list(systemDivPoints.values()),
                        "ImpliedDiv": list(impliedDivPoints.values())}
            repoDf = pd.DataFrame.from_dict(tmpDict)
            repoTableData = repoDf.to_dict("records")

            volGrid = genVolGrid(memoryData["volSurfaceSVI"], volTag, memoryData["spotRef"], maturities, volGridStrikes)
            curveGrid = genVolGrid(memoryData["volSurfaceSVI"], volTag, memoryData["spotRef"], maturities, curveGridStrikes, returnType="dict")

            memoryData["spotRef"] = volData["spotRef"]
            memoryData["optionChain"] = optionChain
            memoryData["repoFitted"] = repoFitted
            memoryData["volData"] = volData
            memoryData["repoTableData"] = repoTableData
            memoryData["maturities"] = maturities
            memoryData["volGrid"] = volGrid.to_dict("records")
            memoryData["curveGrid"] = curveGrid

    return memoryData, False, False, False, False, False, False, False, False, False, False

@app.callback([Output("memory-vol", "data", allow_duplicate=True), 
               Output("modal-loadOptionChain", "is_open", allow_duplicate=True),
               Output("memory-getOptionChainVol", "data"),
               Output("button-loadVol", "disabled", allow_duplicate=True),
               Output("button-saveVol", "disabled", allow_duplicate=True),
               Output("button-loadChainVol", "disabled", allow_duplicate=True),
               Output("button-fitVolSurf", "disabled", allow_duplicate=True),
               Output("button-checkArb", "disabled", allow_duplicate=True),
               Output("button-loadRef", "disabled", allow_duplicate=True),
               Output("button-restoreParams", "disabled", allow_duplicate=True),
               Output("button-reanchor", "disabled", allow_duplicate=True),
               Output("button-addMat", "disabled", allow_duplicate=True),
               Output("button-delMat", "disabled", allow_duplicate=True)], 
              [Input("button-modal-loadOptionChain", "n_clicks"), 
               State("memory-vol", "data"),
               State("modal-volData-dropdown", "value")], prevent_initial_call=True)
def loadOptionChainVol(n_clicks, memoryData, loadType):

    if n_clicks:

        if loadType == "Live":

            return memoryData, False, True, True, True, True, True, True, True, True, True, True, True
        
        else:

            undlName = memoryData["undlName"]
            volModel = memoryData["volModel"]
            volTag = "SVI-JW" if volModel != "SVI-SPX" else "SVI-SPX"

            result = get_optionChainVolLazy(memoryData["undlName"])
            optionChain = result["data"]["optionChain"]
            repoFitted = result["data"]["repoFitted"]
            volData = result["data"]["volData"]

            maturities = sorted(list(set(list(repoFitted["Schedule"].keys()) + listedMaturities[get_calendar(undlName)+"_"+get_undlType(undlName)] + list(memoryData["volSurfaceSVI"][volTag].keys()))))
            maturities = [m for m in maturities if m > memoryData["valueDate"]]

            repoTableData = []
            systemDivPoints, impliedDivPoints = getOptionImpliedDiv(repoFitted, volData["spotRef"])
            tmpDict = {"Date": list(repoFitted["Schedule"].keys()), 
                        "ImpiledRepo": list(repoFitted["Schedule"].values()), 
                        "SystemDiv": list(systemDivPoints.values()),
                        "ImpliedDiv": list(impliedDivPoints.values())}
            repoDf = pd.DataFrame.from_dict(tmpDict)
            repoTableData = repoDf.to_dict("records")

            volGrid = genVolGrid(memoryData["volSurfaceSVI"], volTag, memoryData["spotRef"], maturities, volGridStrikes)
            curveGrid = genVolGrid(memoryData["volSurfaceSVI"], volTag, memoryData["spotRef"], maturities, curveGridStrikes, returnType="dict")

            memoryData["repoTableData"] = repoTableData
            memoryData["optionChain"] = optionChain
            memoryData["repoFitted"] = repoFitted
            memoryData["volData"] = volData
            memoryData["maturities"] = maturities
            memoryData["volGrid"] = volGrid.to_dict("records")
            memoryData["curveGrid"] = curveGrid

            return memoryData, False, None, False, False, False, False, False, False, False, False, False, False
    
    else:

        return memoryData, False, None, False, False, False, False, False, False, False, False, False, False

@app.callback(Output("memory-vol", "data", allow_duplicate=True), 
              [Input("button-fitVolSurf", "n_clicks"), 
               State("memory-vol", "data")], prevent_initial_call=True)
def fitVolSurface(n_clicks, memoryData):

    if n_clicks:

        if memoryData != None:

            if "volData" in memoryData.keys():
                
                if memoryData["volData"]["call"]["bid"] != {} and memoryData["volData"]["put"]["bid"] != {}:

                    undlName = memoryData["undlName"]
                    spotRef = memoryData["spotRef"]
                    volModel = memoryData["volModel"]
                    volTag = "SVI-SPX" if volModel == "SVI-SPX" else "SVI-JW"
                    maturities = memoryData["maturities"]

                    result = fit_volSurfaceSVI(volModel=volModel, volData=memoryData["volData"], repoFitted=get_repo(undlName))

                    if "error" not in result.keys():
                        volSurfaceSVI = result["result"]
                        volGrid = genVolGrid(volSurfaceSVI, volTag, spotRef, maturities, volGridStrikes)
                        curveGrid = genVolGrid(volSurfaceSVI, volTag, spotRef, maturities, curveGridStrikes, returnType="dict")

                        memoryData["volSurfaceSVI"] = volSurfaceSVI
                        memoryData["volSurfaceSVI_backup"] = volSurfaceSVI
                        memoryData["volGrid"] = volGrid.to_dict("records")
                        memoryData["curveGrid"] = curveGrid

                    return memoryData

    return memoryData

@app.callback(Output("memory-vol", "data", allow_duplicate=True),
              [Input("button-restoreParams", "n_clicks"), 
               State("memory-vol", "data"),
               State("maturity-dropdown", "value")], prevent_initial_call=True)
def restoreParams(n_clicks, memoryData, maturity):

    if n_clicks:
        volSurfaceSVI = memoryData["volSurfaceSVI"]
        volModel = memoryData["volModel"]
        volTag = "SVI-SPX" if volModel == "SVI-SPX" else "SVI-JW"
        spotRef = memoryData["spotRef"]
        maturities = memoryData["maturities"]
        volSurfaceSVI_backup = memoryData["volSurfaceSVI_backup"]

        if volSurfaceSVI_backup is None:
            if maturity in volSurfaceSVI[volTag].keys():

                volSurfaceSVI[volTag].pop(maturity)
                gridDf = genVolGrid(volSurfaceSVI, volTag, spotRef, maturities, volGridStrikes)
                curveGrid = genVolGrid(volSurfaceSVI, volTag, spotRef, maturities, curveGridStrikes, returnType="dict")

                memoryData["volSurfaceSVI"] = volSurfaceSVI
                memoryData["volGrid"] = gridDf.to_dict("records")
                memoryData["curveGrid"] = curveGrid

        else:

            if volTag in volSurfaceSVI_backup.keys():

                if maturity in volSurfaceSVI_backup[volTag].keys():

                    volSurfaceSVI[volTag][maturity] =  volSurfaceSVI_backup[volTag][maturity]
                    volSurfaceSVI[volTag] = sortDictByKey(volSurfaceSVI[volTag])
                    gridDf = genVolGrid(volSurfaceSVI, volTag, spotRef, maturities, volGridStrikes)
                    curveGrid = genVolGrid(volSurfaceSVI, volTag, spotRef, maturities, curveGridStrikes, returnType="dict")

                    memoryData["volSurfaceSVI"] = volSurfaceSVI
                    memoryData["volGrid"] = gridDf.to_dict("records")
                    memoryData["curveGrid"] = curveGrid

                else:

                    m = list(volSurfaceSVI[volTag].keys())[0]
                    volSurfaceSVI[volTag].pop(maturity)
                    #volSurfaceSVI[volTag][maturity] = {k:"" for k in volSurfaceSVI[volTag][m].keys()}
                    #volSurfaceSVI[volTag] = sortDictByKey(volSurfaceSVI[volTag])
                    gridDf = genVolGrid(volSurfaceSVI, volTag, spotRef, maturities, volGridStrikes)
                    curveGrid = genVolGrid(volSurfaceSVI, volTag, spotRef, maturities, curveGridStrikes, returnType="dict")

                    memoryData["volSurfaceSVI"] = volSurfaceSVI
                    memoryData["volGrid"] = gridDf.to_dict("records")
                    memoryData["curveGrid"] = curveGrid

    return memoryData

#@app.callback([Output("SVITable", "rowData"), "grid"])

@app.callback([Output("ric", "value"), Output("bbg", "value"), Output("obb", "value"), Output("symbol", "value"),
               Output("type", "value"), Output("calendar", "value"), Output("ccy", "value"), Output("dvdccy", "value"), 
               Output("text-undlNamePageStatus", "children", allow_duplicate=True)],
              [Input("button-clearUndlName", "n_clicks")], prevent_initial_call=True)
def clearUndlName(n_clicks):
    if n_clicks > 0:
        return "", "", "", "", "", "", "", "", "Status:"
    
@app.callback([Output("ric", "value", allow_duplicate=True),
               Output("bbg", "value", allow_duplicate=True), Output("obb", "value", allow_duplicate=True), 
               Output("symbol", "value", allow_duplicate=True), Output("type", "value", allow_duplicate=True), 
               Output("calendar", "value", allow_duplicate=True), Output("ccy", "value", allow_duplicate=True), 
               Output("dvdccy", "value", allow_duplicate=True), Output("ETOExercise", "value", allow_duplicate=True), 
               Output("text-undlNamePageStatus", "children", allow_duplicate=True)],
              [Input("button-loadUndlName", "n_clicks"), State("ric", "value")], prevent_initial_call=True)
def loadUndlName(n_clicks, ric):

    if ric == None or ric == "": return "", "", "", "", "", "", "", "", "Status:"
    if get_RIC(ric) == None: exit

    return ric, get_BBG(ric), get_OBB(ric), get_symbol(ric), get_undlType(ric), get_calendar(ric), get_CCY(ric), get_DVDCCY(ric), get_listedExerciseType(ric), "Status:"

@app.callback([Output("text-undlNamePageStatus", "children", allow_duplicate=True),
               Output("ric", "value", allow_duplicate=True), Output("bbg", "value", allow_duplicate=True), 
               Output("obb", "value", allow_duplicate=True), Output("symbol", "value", allow_duplicate=True),
               Output("type", "value", allow_duplicate=True), Output("calendar", "value", allow_duplicate=True), 
               Output("ccy", "value", allow_duplicate=True), Output("dvdccy", "value", allow_duplicate=True),
               Output("ETOExercise", "value", allow_duplicate=True)],
              [Input("confirm-saveUndl", "submit_n_clicks"), 
               State("ric", "value"), State("bbg", "value"), State("obb", "value"), State("symbol", "value"),
               State("type", "value"), State("calendar", "value"), State("ccy", "value"), State("dvdccy", "value"), State("ETOExercise", "value")], prevent_initial_call=True)
def uploadUndlNameConfirmed(submit_n_clicks, ric, bbg, obb, symbol, undlType, calendar, ccy, dvdccy, ETOExercise):

    if submit_n_clicks:
        if ric in [None, ""] or bbg in [None, ""] or \
            undlType in [None, ""] or calendar in [None, ""] or ccy in [None, ""] or dvdccy in [None, ""] or ETOExercise in [None, ""]:
            return ["Invalid value"], ric, bbg, obb, symbol, undlType, calendar, ccy, dvdccy, ETOExercise
    
        exchange = ("Z" if undlType == "Index" else ric.split(".")[1])

        if obb == "": 
            if undlType == "Index":
                obb = "^"+ric[1:]
            else:
                if exchange in ["N", "Q"]:
                    obb = ric.split(".")[0]
                else:
                    obb =ric

        if symbol == "": symbol = ric

        infoDict = {"system": ric, "ric": ric, "bbg": bbg, "obb": obb, "symbol": symbol, "undlType": undlType, 
                    "exchange": exchange, "calendar": calendar,
                    "ccy": ccy, "dvdccy": dvdccy, "ETOExercise": ETOExercise}
    
        status = upload_undlNameInfo(infoDict)

        return "Status: "+status["status"], ric, bbg, obb, symbol, undlType, calendar, ccy, dvdccy, ETOExercise
    
    return "Status:", ric, bbg, obb, symbol, undlType, calendar, ccy, dvdccy, ETOExercise

@app.callback(Output("confirm-saveUndl", "displayed", allow_duplicate=True),
              [Input("button-saveUndlName", "n_clicks")], prevent_initial_call=True)
def uploadUndlName(n_clicks):

    if n_clicks:
        return True
    return False

@app.callback(Output("text-undlNamePageStatus", "children", allow_duplicate=True),
              [Input("confirm-delUndl", "submit_n_clicks"), 
               State("ric", "value")], prevent_initial_call=True)
def delUndlNameConfirmed(submit_n_clicks, ric):

    if submit_n_clicks:
        status = delete_undlNameInfo(ric)

        if "error" in status.keys():
            return "Status: " + status["error"]
        else:
            return "Status: " + status["status"]

    return "Status:"

@app.callback(Output("confirm-delUndl", "displayed", allow_duplicate=True),
              [Input("button-delUndlName", "n_clicks")], prevent_initial_call=True)
def delUndlName(n_clicks):

    if n_clicks:
        return True
    return False

@app.callback([Output("undlName-dropdown", "options", allow_duplicate=True),
               Output("confirm-fetchDB", "displayed", allow_duplicate=True)], 
              [Input("button-fetchDB", "n_clicks"), State("undlName-dropdown", "options")], prevent_initial_call=True)
def fetchDB(n_clicks, options):

    if n_clicks > 0:
        underlyingDatabase = fetch_underlyingDatabase()
        options = sorted(list(underlyingDatabase.keys()))
        return options, True
    
@app.callback(Output("downloadYieldCurve", "data"),
              Input("button-downloadYieldCurve", "n_clicks"), prevent_initial_call=True)
def dlYC(n_clicks):
    if n_clicks:
        data = get_yieldCurve(ccy=None)
        with open("tmp/YieldCurve.json", "w") as f:
            json.dump(data, f, indent=2)
        return dcc.send_file("tmp/YieldCurve.json")

@app.callback(Output("downloadTimeZone", "data"),
              Input("button-downloadTimeZone", "n_clicks"), prevent_initial_call=True)
def dlTZ(n_clicks):
    if n_clicks:
        data = get_exchangeTimeZone(calendar=None)
        with open("tmp/ExchangeTimeZone.json", "w") as f:
            json.dump(data, f, indent=2)
        return dcc.send_file("tmp/ExchangeTimeZone.json")
    
@app.callback(Output("downloadHolidayCalendar", "data"),
              Input("button-downloadHolidayCalendar", "n_clicks"), prevent_initial_call=True)
def dlHC(n_clicks):
    if n_clicks:
        data = get_holidayCalendar(calendar=None)
        with open("tmp/HolidayCalendar.json", "w") as f:
            json.dump(data, f, indent=2)
        return dcc.send_file("tmp/HolidayCalendar.json")

@app.callback(Output("downloadListedMaturityRule", "data"),
              Input("button-downloadListedMaturityRule", "n_clicks"), prevent_initial_call=True)
def dlLHR(n_clicks):

    if n_clicks:
        data = get_listedMaturityRule()
        with open("tmp/ListedMaturityRule.json", "w") as f:
            json.dump(data, f, indent=2)
        return dcc.send_file("tmp/ListedMaturityRule.json")

@app.callback(Output("page-content", "children", allow_duplicate=True), 
              Input("button-loadVSFBatch", "n_clicks"), prevent_initial_call=True)
def reloadVSF(n_clicks):

    if n_clicks:
        return createContentVSFBatch()
    return createContentVSFBatch()

@app.callback(Output("text-VSFPageStatus", "children", allow_duplicate=True), 
              [Input("button-saveVSFBatch", "n_clicks"),
               State("table-VSF", "rowData")], prevent_initial_call=True)
def saveVSF(n_clicks, rowData):

    if n_clicks:
        
        VSFConfig = {}
        for data in rowData:
            if data["Underlying"] != "":
                VSFConfig[data["Underlying"]] = {"volModel": data["Vol Model"],
                                                 "saveFittedForward": data["Save Fitted Forward"],
                                                 "fitType": "full"}

        #with open("VolSurFit_batch/config.json", "w") as f:
        #    json.dump(VSFConfig, f, indent=2)
        result = upload_VSFBatchConfig(VSFConfig)

        if "error" in result.keys():
            return result["error"]
    
    return "Status: Saved"

if __name__ == '__main__':
    app.run_server(debug=True)