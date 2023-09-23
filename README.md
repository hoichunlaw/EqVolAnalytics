# Equity Volatility Analytics with Open-Source Data

## Features

* Quant Lib with European and American Pricer/Implied Vol Solver (with discrete dividends)
* Vol surface modeling (implementation of SVI vol surface model)
* Dividend / Repo / Vol Surface fitter with open-source equity option data
* Web API for plug-and-play usage for quant lib
* Web based GUI for market data management and Excel based GUI for vanilla pricer

## Built with

* python and cython for backend computation engine
* dash for front end market data management GUI
* Excel VBA for Excel base vanilla pricer

## List of tools

* Market Data Manager (http://16.163.84.48:8080 username: admin, no password)
* Vanilla Pricer (in Github repo)
* Web API (http://16.163.84.48/docs#/users)

## Usage

### Market Data Manager

* Select Underlying from underlying drop list
* Click "Forward" and then "Option Imp. Div/Repo" to check listed option implied div/repo. Remark Div/Repo as appropriate
* Click "Volatility" and then "Optino Chain" to load option quotes and compute implied vol
* Click "Fit Vol Surf" to fit vol surface to listed option vol
" Click "Load Ref" to load historical vol surface for comparison

![MDM](/images/MDM.jpg)

### Vanilla Pricer

* Input format = "underlying Maturity Strike optionType spotRef", e.g. "NVDA.OQ 3M 90% P"
* Return NPV and Greeks, base on system vol (vol surface in market data manager)
* "F12" to load log and overwrite market data

![VP](/images/VP.jpg)