import requests
import numpy as np
import pandas as pd
import os, json, time, getpass
from datetime import date, datetime, timedelta
from ast import literal_eval

#api_url = "http://127.0.0.1:8000/"
#api_url = "http://192.168.0.100:8000/"
api_url = "http://43.198.72.206:80/"

sess = requests.Session()

# helper functions
def mergeDict(d1, d2):

    return {k:v for k,v in list(d1.items())+list(d2.items())}

def fetch_underlyingDatabase():

    req = api_url + "api/v1/fetchUnderlyingDatabase"
    
    response = sess.post(req)
    
    return json.loads(response.text)

def get_RIC(undlName):
    
    req = api_url + "api/v1/getRIC"
    body = {"undlName": undlName}
    
    response = sess.post(req, json=body)

    result = json.loads(response.text)
    try:
        if "error" in result.keys():
            return None
        else:
            return result["result"]
    except:
        return None

def get_BBG(undlName):
    
    req = api_url + "api/v1/getBBG"
    body = {"undlName": undlName}
    
    response = sess.post(req, json=body)
    
    result = json.loads(response.text)
    try:
        if "error" in result.keys():
            return None
        else:
            return result["result"]
    except:
        return None

def get_OBB(undlName):
    
    req = api_url + "api/v1/getOBB"
    body = {"undlName": undlName}
    
    response = sess.post(req, json=body)
    
    result = json.loads(response.text)
    try:
        if "error" in result.keys():
            return None
        else:
            return result["result"]
    except:
        return None

def get_symbol(undlName):
    
    req = api_url + "api/v1/getSymbol"
    body = {"undlName": undlName}
    
    response = sess.post(req, json=body)
    
    result = json.loads(response.text)
    try:
        if "error" in result.keys():
            return None
        else:
            return result["result"]
    except:
        return None

def get_systemName(undlName):
    
    req = api_url + "api/v1/getSystemName"
    body = {"undlName": undlName}
    
    response = sess.post(req, json=body)
    
    result = json.loads(response.text)
    try:
        if "error" in result.keys():
            return None
        else:
            return result["result"]
    except:
        return None

def get_undlType(undlName):
    
    req = api_url + "api/v1/getUndlType"
    body = {"undlName": undlName}
    
    response = sess.post(req, json=body)
    
    result = json.loads(response.text)
    try:
        if "error" in result.keys():
            return None
        else:
            return result["result"]
    except:
        return None

def get_yieldCurve(ccy, dateRef=None):
    
    req = api_url + "api/v1/getYieldCurve"
    body = {"ccy": "None" if ccy is None else ccy, "date": "None" if dateRef is None else dateRef}
    
    response = sess.post(req, json=body)
    
    return json.loads(response.text)

def get_dividend(undlName, dateRef=None):
    
    req = api_url + "api/v1/getDividend"
    body = {"undlName": undlName, "date": "None" if dateRef is None else dateRef}
    
    response = sess.post(req, json=body)
    
    return json.loads(response.text)

def get_repo(undlName, dateRef=None):
    
    req = api_url + "api/v1/getRepo"
    body = {"undlName": undlName, "date": "None" if dateRef is None else dateRef}
    
    response = sess.post(req, json=body)
    
    return json.loads(response.text)

def get_repoRate(undlName, maturity, repoCurve=None, dateRef=None):
    
    req = api_url + "api/v1/getRepoRate"
    body = {"undlName": undlName, 
            "maturity": maturity, 
            "repo": str(repoCurve) if repoCurve is not None else "None",
            "date": "None" if dateRef is None else dateRef}
    
    response = sess.post(req, json=body)

    try:
        result = json.loads(response.text)
        return result["rate"]

    except Exception as e:
        return {"error": str(e)}

def get_volSurfaceSVI(undlName, dateRef=None):

    req = api_url + "api/v1/getVolSurfaceSVI"
    body = {"undlName": undlName, "date": "None" if dateRef is None else dateRef}

    response = sess.post(req, json=body)

    result = json.loads(response.text)

    if "error" in result.keys():
        return None
    else:
        return result

def get_calendar(undlName):
    
    req = api_url + "api/v1/getCalendar"
    body = {"undlName": undlName}
    
    response = sess.post(req, data=json.dumps(body))
    
    result = json.loads(response.text)
    try:
        if "error" in result.keys():
            return None
        else:
            return result["result"]
    except:
        return None

def get_CCY(undlName):
    
    req = api_url + "api/v1/getCCY"
    body = {"undlName": undlName}
    
    response = sess.post(req, data=json.dumps(body))
    
    result = json.loads(response.text)
    try:
        if "error" in result.keys():
            return None
        else:
            return result["result"]
    except:
        return None

def get_DVDCCY(undlName):
    
    req = api_url + "api/v1/getDVDCCY"
    body = {"undlName": undlName}
    
    response = sess.post(req, data=json.dumps(body))
    
    result = json.loads(response.text)
    try:
        if "error" in result.keys():
            return None
        else:
            return result["result"]
    except:
        return None

def get_listedExerciseType(undlName):
    
    req = api_url + "api/v1/getListedExerciseType"
    body = {"undlName": undlName}
    
    response = sess.post(req, data=json.dumps(body))
    
    result = json.loads(response.text)
    try:
        if "error" in result.keys():
            return None
        else:
            return result["result"]
    except:
        return None

def get_exchange(undlName):
    
    req = api_url + "api/v1/getExchange"
    body = {"undlName": undlName}
    
    response = sess.post(req, data=json.dumps(body))
    
    result = json.loads(response.text)
    try:
        if "error" in result.keys():
            return None
        else:
            return result["result"]
    except:
        return None

def get_spot(undlName, delay=0):
    
    req = api_url + "api/v1/getSpot"
    body = {"undlName": undlName, "n": delay}
    
    response = sess.post(req, data=json.dumps(body))

    result = json.loads(response.text)
    if "error" in result.keys():
        return {"error": response.text}
    else:
        return result

def get_FX(undlName, delay=0):
    
    req = api_url + "api/v1/getFX"
    body = {"undlName": undlName, "n": delay}
    
    response = sess.post(req, data=json.dumps(body))

    result = json.loads(response.text)
    if "error" in result.keys():
        return {"error": response.text}
    else:
        return result

def get_exchangeDate(calendar):
    
    req = api_url + "api/v1/getExchangeDate"
    body = {"calendar": calendar}
    
    response = sess.post(req, json=body)
    
    result = json.loads(response.text)
    try:
        if "error" in result.keys():
            return None
        else:
            return result["result"]
    except:
        return None

def get_exchangeTimeZone(calendar):

    req = api_url + "api/v1/getExchangeTimeZone"

    if calendar is None:
        body = {"calendar": "None"}
    else:
        body = {"calendar": calendar}
    
    response = sess.post(req, json=body)

    result = json.loads(response.text)
    try:
        if "error" in result.keys():
            return None
        else:
            return result["result"]
    except:
        return None
    
def get_holidayCalendar(calendar, dateRef=None):

    req = api_url + "api/v1/getHolidayCalendar"

    if dateRef is None:
        body = {"date": datetime.now().strftime("%Y-%m-%d")}
    else:
        body = {"date": dateRef}
    
    response = sess.post(req, json=body)

    result = json.loads(response.text)
    if "error" in result.keys():
        return {"error": response.text}
    else:
        if calendar is None:
            return result
        elif calendar in result.keys():
            return result[calendar]
        else:
            return None
        
def get_VSFBatch():

    req = api_url + "api/v1/getVSFBatch"

    response = sess.get(req)

    return json.loads(response.text)

def get_optionChainVolLazy(undlName):

    req = api_url + "api/v1/getOptionChainVol_lazy"
    body = {"undlName": undlName}

    response = sess.post(req, json=body)

    try:
        result = json.loads(response.text)
        if result["lastVol"] == "None":
            result["lastVol"] = None
    except:
        result = {"error": response.text}

    return result

def get_optionChainVol(optionChainData):

    if optionChainData is None:
        return {"error": None}

    req = api_url + "api/v1/getOptionChainVol"
    body = {"data": str(optionChainData)}

    response = sess.post(req, json=body)

    try:
        result = json.loads(response.text)
    except:
        result = {"error": response.text}

    return result

def get_optionChainRepo(optionChainData):

    if optionChainData is None:
        return {"error": None}

    req = api_url + "api/v1/getOptionChainRepo"
    body = {"data": str(optionChainData)}

    response = sess.post(req, json=body)

    try:
        result = json.loads(response.text)
    except:
        result = {"error": response.text}

    return result

def forecast_stockDiv(undlName, factor=1, forecastYear=8):

    req = api_url + "api/v1/forecastStockDiv"
    body = {"undlName": undlName,
            "factor": factor,
            "forecastYear": forecastYear}
    
    response = sess.post(req, json=body)

    try:
        result = json.loads(response.text)
    except:
        result = {"error": response.text}

    return result

def fit_divGrowthFactor(undlName, impliedDiv):

    req = api_url + "api/v1/fitDivGrowthFactor"
    body = {"undlName": undlName,
            "impliedDiv": str(impliedDiv)}
    
    response = sess.post(req, json=body)

    try:
        result = json.loads(response.text)
    except:
        result = {"error": response.text}

    return result

def get_netBusinessDays(fromDate, toDate, calendar):

    req = api_url + "api/v1/netBusinessDays"
    body = {"fromDate": fromDate, "toDate": toDate, "calendar": calendar}

    response = sess.post(req, json=body)

    try:
        result = json.loads(response.text)
    except:
        result = {"error": response.text}

    return result

def get_nextBusinessDay(refDate, dayShift, calendar):

    req = api_url + "api/v1/nextBusinessDay"
    body = {"refDate": refDate, "dayShift": dayShift, "calendar": calendar}

    response = sess.post(req, json=body)

    try:
        result = json.loads(response.text)
    except:
        result = {"error": response.text}

    return result

def discount_cashFlow(cashFlow, refDate, payDate, yieldCurve):

    req = api_url + "api/v1/discountCashFlow"
    body = {"cashFlow": cashFlow, "refDate": refDate, "payDate": payDate, "yieldCurve": str(yieldCurve)}

    response = sess.post(req, json=body)

    return json.loads(response.text)

def calc_SVIJW_SpotMoney(moneyness, paramsSVI):

    req = api_url + "api/v1/SVIJW_SpotMoney"
    myStrikes = [moneyness] if (type(moneyness) == float or type(moneyness) == int) else moneyness
    body = mergeDict({"moneyness": list(myStrikes)}, paramsSVI)

    response = sess.post(req, json=body)

    result = json.loads(response.text)

    if "error" in result.keys():
        return {"error": response.text}
    else:
        return {float(k): v for k,v in result.items()}
    
def calc_SVIJW_FwdMoney(moneyness, paramsSVI):

    req = api_url + "api/v1/SVIJW_FwdMoney"
    myStrikes = [moneyness] if (type(moneyness) == float or type(moneyness) == int) else moneyness
    body = mergeDict({"moneyness": list(myStrikes)}, paramsSVI)

    response = sess.post(req, json=body)

    result = json.loads(response.text)

    if "error" in result.keys():
        return {"error": response.text}
    else:
        return {float(k): v for k,v in result.items()}

def to_SVI(paramsSVIJW):

    req = api_url + "api/v1/toSVI"

    body = {"vol": paramsSVIJW["vol"],
            "skew": paramsSVIJW["skew"],
            "pWing": paramsSVIJW["pWing"],
            "cWing": paramsSVIJW["cWing"],
            "minVol": paramsSVIJW["minVol"],
            "tau": paramsSVIJW["tau"],
            "forward": paramsSVIJW["forward"]}
    
    response = sess.post(req, json=body)

    result = json.loads(response.text)

    return result

def to_SVIJW(paramsSVIJW):

    req = api_url + "api/v1/toSVIJW"

    body = {"a": paramsSVIJW["a"],
            "b": paramsSVIJW["b"],
            "rho": paramsSVIJW["rho"],
            "m": paramsSVIJW["m"],
            "sigma": paramsSVIJW["sigma"],
            "tau": paramsSVIJW["tau"],
            "forward": paramsSVIJW["forward"]}
    
    response = sess.post(req, json=body)

    result = json.loads(response.text)

    return result

def get_vol(undlName, maturity, strike, volSurfaceSVI=None, historicalDate=None):

    req = api_url + "api/v1/getVol"

    if type(strikes) == float or type(strikes) == int:
        strikes = [strikes]
    body = {"undlName": undlName, 
            "maturity": maturity, 
            "strike": strike,
            "volSurfaceSVI": "None" if volSurfaceSVI is None else str(volSurfaceSVI),
            "historicalDate": "None" if historicalDate is None else historicalDate}

    response = sess.post(req, json=body)

    result = json.loads(response.text)

    return result

def get_volSmile(undlName, maturity, strikes, volSurfaceSVI=None, historicalDate=None):

    req = api_url + "api/v1/getVolSmile"

    if type(strikes) == float or type(strikes) == int:
        strikes = [strikes]
    body = {"undlName": undlName, 
            "maturity": maturity, 
            "strikes": list(strikes),
            "volSurfaceSVI": "None" if volSurfaceSVI is None else str(volSurfaceSVI),
            "historicalDate": "None" if historicalDate is None else historicalDate}

    response = sess.post(req, json=body)

    result = json.loads(response.text)

    return result

def get_volGrid(undlName, maturities, strikes, volSurfaceSVI=None, marketData=None, historicalDate=None):

    req = api_url + "api/v1/getVolGrid"

    if type(strikes) == float or type(strikes) == int:
        strikes = [strikes]
    if type(maturities) == str:
        maturities = [maturities]

    body = {"undlName": undlName, 
            "maturities": list(maturities), 
            "strikes": list(strikes),
            "volSurfaceSVI": "None" if volSurfaceSVI is None else str(volSurfaceSVI),
            "marketData": "None" if marketData is None else str(marketData),
            "historicalDate": "None" if historicalDate is None else historicalDate}

    response = sess.post(req, json=body)

    result = json.loads(response.text)

    return result

def check_volSurfaceArb(volSurfaceSVI, marketDataDict, valueDate):

    req = api_url + "api/v1/checkVolSurfaceArb"

    body = {"volSurfaceSVI": str(volSurfaceSVI), "marketData": str(marketDataDict), "valueDate": valueDate}

    response = sess.post(req, json=body)

    result = json.loads(response.text)

    return result

def calc_European(params, calcWhat=["NPV"]):
    
    req = api_url + "api/v1/European"
    body = params
    body["calcWhat"] = calcWhat
    
    response = sess.post(req, json=body)
    
    return json.loads(response.text)

def calc_EuropeanImpliedVol(params):
    
    req = api_url + "api/v1/EuropeanImpliedVol"
    body = params
    
    response = sess.post(req, json=body)
    
    return json.loads(response.text)

def calc_American(params, calcWhat=["NPV"]):
    
    req = api_url + "api/v1/American"
    body = params
    body["calcWhat"] = calcWhat
    
    response = sess.post(req, json=body)
    
    return json.loads(response.text)

def calc_AmericanImpliedVol(params):
    
    req = api_url + "api/v1/AmericanImpliedVol"
    body = params
    
    response = sess.post(req, json=body)
    
    return json.loads(response.text)

def fit_volSurfaceSVI(volData, repoFitted, volModel):

    req = api_url + "api/v1/fitVolSurfaceSVI"
    body = {"volModel": volModel, "volData": str(volData), "repoData": str(repoFitted), "username": os.getlogin()}

    response = sess.post(req, json=body)

    try:
        result = json.loads(response.text)
    except:
        result = {"error": response.text}

    return result

def get_status(identifier):

    req = api_url + "api/v1/status/" + str(identifier)
    
    try:
        response = sess.get(req)
        result = json.loads(response.text)
        if result["status"] == -999:
            return None
        else:
            result  = {"status": result["status"], "result": result["result"]}
            return result
    except:
        return None
    
def get_listedMaturityRule():

    req = api_url + "api/v1/getListedMaturityRule"
    
    try:
        response = sess.get(req)
        result = json.loads(response.text)
        return result
    except Exception as e:
        return {"error": str(e)}

def upload_volSurfaceSVI(volSurfaceSVI):
    
    req = api_url + "api/v1/uploadVolSurfaceSVI"
    body = {"volSurfaceSVIStr": str(volSurfaceSVI)}
    
    response = sess.post(req, json=body)
    
    return json.loads(response.text)

def upload_dividend(divPanel):
    
    req = api_url + "api/v1/uploadDividend"

    div = {"undlName": divPanel["undlName"],
           "lastUpdate": getpass.getuser(),
           "lastUpdateTime": datetime.strftime(datetime.now(), "%Y-%m-%dT%H:%M:%S"),
           "Schedule": divPanel["Schedule"]}

    body = {"divStr": str(div)}
    
    response = sess.post(req, json=body)
    
    return json.loads(response.text)

def upload_repo(repoPanel):
    
    req = api_url + "api/v1/uploadRepo"

    repo = {"undlName": repoPanel["undlName"],
            "lastUpdate": getpass.getuser(),
            "lastUpdateTime": datetime.strftime(datetime.now(), "%Y-%m-%dT%H:%M:%S"),
            "Schedule": repoPanel["Schedule"]}

    body = {"repoStr": str(repo)}
    
    response = sess.post(req, json=body)
    
    return json.loads(response.text)

def upload_yieldCurve(yieldCurvePanel):
    
    req = api_url + "api/v1/uploadYieldCurve"
    body = {"yieldCurveStr": str(yieldCurvePanel)}
    
    response = sess.post(req, json=body)
    
    return json.loads(response.text)

def calc_forward(spotRef, maturity, marketDataParams, valueDate):
    
    req = api_url + "api/v1/calcForward"
    body = {"spotRef": spotRef, "maturity": maturity, 
            "yieldCurve": str(marketDataParams["yieldCurve"]), 
            "divCurve": str(marketDataParams["divCurve"]), 
            "repoCurve": str(marketDataParams["repoCurve"]), 
            "calendar": marketDataParams["calendar"],
            "valueDate": valueDate}

    response = sess.post(req, json=body)
    
    return json.loads(response.text)

def get_listedMaturity(months, calendar_undlType):

    req = api_url + "api/v1/getListedMaturity"
    body = {"months": months, "calendar_undlType": calendar_undlType}

    response = sess.post(req, json=body)
    
    return json.loads(response.text)

def upload_undlNameInfo(infoDcit):

    req = api_url + "api/v1/uploadUndlNameInfo"
    body = infoDcit

    response = sess.post(req, json=body)
    
    return json.loads(response.text)

def delete_undlNameInfo(undlName):

    req = api_url + "api/v1/deleteUndlNameInfo"
    body = {"undlName": undlName}

    response = sess.post(req, json=body)
    
    return json.loads(response.text)
