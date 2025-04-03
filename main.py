#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Apr  3 09:42:31 2025

@author: julianhanton
"""

# main.py
import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import os
from dotenv import load_dotenv
import openai
from io import StringIO

# Load environment variables
load_dotenv()
openai.api_key = st.secrets["OPENAI_API_KEY"]

st.set_page_config(page_title="stopswimmingnaked", layout="wide")

# Minimalist UI influenced by Dieter Rams
st.markdown("""
    <style>
    body {
        background-color: #f88c4c;
        color: #a03c44;
        font-family: Helvetica Neue, sans-serif;
    }
    .block-container {
        padding: 2rem 2rem 2rem 2rem;
    }
    h1, h2, h3, h4 {
        font-weight: 400;
        color: #a03c44;
    }
    .stButton button {
        background-color: #000;
        color: #fff;
        border-radius: 0;
        border: none;
        padding: 0.4rem 1rem;
    }
    </style>
""", unsafe_allow_html=True)

st.title('stopswimmingnaked')
st.markdown("""
**A minimalist dashboard for deep company analysis.**
""")

# --- Ticker Input ---
ticker = st.text_input('Ticker Symbol', 'AAPL', help="Enter a US stock ticker, like BRK-A or BRK-B")
timeframe = st.selectbox('Chart Range', ['1d', '5d', '1mo', '6mo', '1y', '5y', '10y'])

# --- Get Price Data and Chart ---
if st.button('Analyze'):
    with st.spinner('Fetching price data...'):
        try:
            stock_data = yf.download(ticker, period=timeframe)
            st.line_chart(stock_data['Close'])
        except Exception as e:
            st.error(f"Failed to fetch price data: {e}")

    # --- SEC EDGAR API for XBRL Financials ---
    st.subheader("Key Financial Metrics (from 10-Q filings)")
    headers = {"User-Agent": "Mozilla/5.0 (compatible; stopswimmingnaked/1.0)"}
    cik = None
    try:
        st.caption("Looking up CIK...")
        url = "https://www.sec.gov/include/ticker.txt"
        r = requests.get(url, headers=headers)
        if r.status_code == 200:
            df = pd.read_csv(StringIO(r.text), sep="|", names=["ticker", "cik"])
            df['ticker'] = df['ticker'].str.upper()
            ticker_input = ticker.upper().replace("-", ".")
            match = df[df['ticker'] == ticker_input]
            if not match.empty:
                cik = str(match.iloc[0]['cik']).zfill(10)

        if cik:
            concept_codes = {
                'Revenue': 'Revenues',
                'Net Income': 'NetIncomeLoss',
                'Operating Margin': 'OperatingIncomeLoss',
                'Net Margin': 'NetIncomeLoss',
                'Cash from Operations': 'NetCashProvidedByUsedInOperatingActivities',
                'Cash from Investing': 'NetCashProvidedByUsedInInvestingActivities',
                'Free Cash Flow': 'FreeCashFlow',
                'Short Term Debt': 'ShortTermDebt',
                'Long Term Debt': 'LongTermDebtNoncurrent',
                'Cash and Equivalents': 'CashAndCashEquivalentsAtCarryingValue'
            }

            summary_data = []

            for label, concept in concept_codes.items():
                url = f"https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/us-gaap/{concept}.json"
                try:
                    facts_res = requests.get(url, headers=headers)
                    if facts_res.status_code != 200:
                        continue
                    facts = facts_res.json()
                    data = facts.get("units", {}).get("USD", [])
                    df = pd.DataFrame(data)
                    df = df[df['form'] == '10-Q']
                    df['end'] = pd.to_datetime(df['end'])
                    df = df.sort_values(by='end', ascending=False).head(5)
                    df = df[['end', 'val']].rename(columns={'val': label})
                    if summary_data == []:
                        summary_data = df
                    else:
                        summary_data = pd.merge(summary_data, df, on='end', how='outer')
                except Exception as e:
                    st.warning(f"Could not fetch {label}: {e}")

            if not isinstance(summary_data, list):
                summary_data = summary_data.sort_values(by='end', ascending=False)
                st.dataframe(summary_data.rename(columns={'end': 'Quarter End'}), use_container_width=True)
            else:
                st.warning("No financial data available for display.")

            st.subheader("Most Recent Net Income")
            try:
                ni_url = f"https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/us-gaap/NetIncomeLoss.json"
                ni_res = requests.get(ni_url, headers=headers)
                ni_data = ni_res.json().get("units", {}).get("USD", [])
                df = pd.DataFrame(ni_data)
                df = df[df['form'].isin(['10-K', '10-Q'])]
                df['end'] = pd.to_datetime(df['end'])
                df = df.sort_values(by='end', ascending=False).head(1)
                st.dataframe(df[['form', 'fy', 'fp', 'end', 'val']].rename(columns={
                    'form': 'Filing', 'fy': 'Year', 'fp': 'Period', 'end': 'End Date', 'val': 'Net Income ($USD)'
                }), use_container_width=True)
            except Exception as e:
                st.warning(f"Could not fetch most recent Net Income: {e}")

        else:
            st.warning("CIK not found for this ticker. Please try another.")
    except Exception as e:
        st.error(f"Failed to fetch SEC data: {e}")
