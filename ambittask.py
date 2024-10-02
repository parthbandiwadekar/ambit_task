import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import traceback
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# Function to safely format values
def safe_format(value, format_spec):
    if value is None:
        return 'N/A'
    try:
        return format(value, format_spec)
    except (ValueError, TypeError):
        return str(value)

# Function to scrape company data using Requests
# def scrape_company_data(symbol):
#     url = f"https://www.screener.in/company/{symbol}/consolidated/"

#     response = requests.get(url)
#     if response.status_code != 200:
#         return None

#     soup = BeautifulSoup(response.content, 'html.parser')

#     def extract_value(text):
#         try:
#             return soup.find(text=text).find_next('span').text.strip().replace(',', '')
#         except AttributeError:
#             return None

#     # Extract values based on HTML structure
#     current_pe = extract_value('PE ratio')
#     market_cap = extract_value('Market Cap')
#     fy23_net_profit = extract_value('Net Profit')

#     try:
#         current_pe = float(current_pe)
#         market_cap = float(market_cap.replace('Cr', '').strip()) * 1e7 if market_cap else None
#         fy23_net_profit = float(fy23_net_profit.replace('Cr', '').strip()) * 1e7 if fy23_net_profit else None
#     except (ValueError, TypeError):
#         current_pe, market_cap, fy23_net_profit = None, None, None

#     # Calculate FY23 PE
#     fy23_pe = market_cap / fy23_net_profit if market_cap and fy23_net_profit else None

#     # Extract 5-yr median RoCE
#     roce = extract_value('5 Years: RoCE %')
#     roce = float(roce.rstrip('%')) if roce else None

#     return {
#         'Symbol': symbol,
#         'Current PE': current_pe,
#         'FY23 PE': fy23_pe,
#         '5-yr median pre-tax RoCE': roce,
#     }

# # Alternative: Function to scrape company data using Selenium for dynamic content
# def scrape_company_data_selenium(symbol):
#     driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
#     driver.get(f"https://www.screener.in/company/{symbol}/consolidated/")
#     soup = BeautifulSoup(driver.page_source, 'html.parser')
#     driver.quit()

#     def extract_value(text):
#         try:
#             return soup.find(text=text).find_next('span').text.strip().replace(',', '')
#         except AttributeError:
#             return None

#     # Extract values based on HTML structure
#     current_pe = extract_value('PE ratio')
#     market_cap = extract_value('Market Cap')
#     fy23_net_profit = extract_value('Net Profit')

#     try:
#         current_pe = float(current_pe)
#         market_cap = float(market_cap.replace('Cr', '').strip()) * 1e7 if market_cap else None
#         fy23_net_profit = float(fy23_net_profit.replace('Cr', '').strip()) * 1e7 if fy23_net_profit else None
#     except (ValueError, TypeError):
#         current_pe, market_cap, fy23_net_profit = None, None, None

#     # Calculate FY23 PE
#     fy23_pe = market_cap / fy23_net_profit if market_cap and fy23_net_profit else None

#     # Extract 5-yr median RoCE
#     roce = extract_value('5 Years: RoCE %')
#     roce = float(roce.rstrip('%')) if roce else None

#     return {
#         'Symbol': symbol,
#         'Current PE': current_pe,
#         'FY23 PE': fy23_pe,
#         '5-yr median pre-tax RoCE': roce,
#     }

def scrape_company_data(symbol):
    url = f"https://reversedcf-fb0dd87970ce.herokuapp.com/val"
    
    response = requests.get(url)
    if response.status_code != 200:
        return None

    soup = BeautifulSoup(response.content, 'html.parser')

    # Extract Current PE
    current_pe_element = soup.find('li', string='Stock P/E')
    current_pe = float(current_pe_element.find('span', class_='number').text.strip()) if current_pe_element else None

    # Extract FY23 PE
    fy23_pe_element = soup.find('li', string='FY23PE')
    fy23_pe = float(fy23_pe_element.find('span', class_='number').text.strip()) if fy23_pe_element else None

    # Extract 5-yr median RoCE
    roce_element = soup.find('li', string='ROCE')
    roce = float(roce_element.find('span', class_='number').text.strip().rstrip('%')) if roce_element else None

    return {
        'Symbol': symbol,
        'Current PE': current_pe,
        'FY23 PE': fy23_pe,
        '5-yr median pre-tax RoCE': roce,
    }


# Function to calculate intrinsic PE using DCF
def calculate_dcf(cost_of_capital, roce, growth_rate, high_growth_period, fade_period, terminal_growth):
    tax_rate = 0.25
    total_years = high_growth_period + fade_period

    # Initialize arrays
    growth_rates = np.zeros(total_years)
    roces = np.zeros(total_years)

    # Set high growth period values
    growth_rates[:high_growth_period] = growth_rate
    roces[:high_growth_period] = roce

    # Set fade period values
    for i in range(high_growth_period, total_years):
        t = i - high_growth_period + 1
        growth_rates[i] = growth_rate - (growth_rate - terminal_growth) * t / fade_period
        roces[i] = roce - (roce - cost_of_capital) * t / fade_period

    # Calculate free cash flow to equity (FCFE)
    reinvestment_rate = growth_rates / roces
    fcfe = (1 - reinvestment_rate) * (1 - tax_rate)

    # Calculate present value factors
    discount_factors = 1 / (1 + cost_of_capital) ** np.arange(1, total_years + 1)

    # Calculate present value of FCFE
    pv_fcfe = fcfe * discount_factors

    # Calculate terminal value
    terminal_value = fcfe[-1] * (1 + terminal_growth) / (cost_of_capital - terminal_growth)
    pv_terminal_value = terminal_value * discount_factors[-1]

    # Calculate total equity value
    total_equity_value = np.sum(pv_fcfe) + pv_terminal_value

    # Calculate intrinsic PE
    intrinsic_pe = total_equity_value / (1 - tax_rate)

    return intrinsic_pe

# Streamlit app
st.set_page_config(layout="wide")
st.title('DCF Valuation Dashboard')

# Company Data Section
st.header('Company Data')
symbol = st.text_input('Enter NSE/BSE Symbol', value='NESTLEIND')
if st.button('Fetch Data'):
    try:
        with st.spinner('Fetching data...'):
            company_data = scrape_company_data(symbol)  # Or use scrape_company_data_selenium(symbol) for dynamic sites
        if company_data:
            st.write(f"Stock Symbol: {company_data['Symbol']}")
            st.write(f"Current PE: {safe_format(company_data['Current PE'], '.1f')}")
            st.write(f"FY23 PE: {safe_format(company_data['FY23 PE'], '.1f')}")
            st.write(f"5-yr median pre-tax RoCE: {safe_format(company_data['5-yr median pre-tax RoCE'], '.1f')}%")
        else:
            st.error(f'Failed to fetch data for {symbol}. Please check the symbol and try again.')
    except Exception as e:
        st.error(f"An error occurred while fetching data: {str(e)}")
        st.error("Stack trace:")
        st.code(traceback.format_exc())

# DCF Inputs Section
st.header('DCF Inputs')
col1, col2 = st.columns(2)
with col1:
    cost_of_capital = st.slider('Cost of Capital (%)', 5.0, 20.0, 10.0, 0.1)
    roce = st.slider('RoCE (%)', 5.0, 50.0, 15.0, 0.1)
    growth_rate = st.slider('Growth Rate (%)', 5.0, 30.0, 10.0, 0.1)
with col2:
    high_growth_period = st.slider('High Growth Period (Years)', 5, 25, 15, 1)
    fade_period = st.slider('Fade Period (Years)', 5, 25, 15, 1)
    terminal_growth = st.slider('Terminal Growth Rate (%)', 2.0, 7.5, 3.0, 0.1)

# Calculate Valuation
if st.button('Calculate Valuation'):
    try:
        intrinsic_pe = calculate_dcf(cost_of_capital / 100, roce / 100, growth_rate / 100, high_growth_period, fade_period, terminal_growth / 100)
        st.write(f"The calculated intrinsic PE is: {safe_format(intrinsic_pe, '.2f')}")

        if 'company_data' in locals() and company_data:
            current_pe = company_data.get('Current PE')
            valuation_status = "undervalued" if intrinsic_pe > current_pe else "overvalued"
            st.success(f"The stock is {valuation_status} based on the calculated intrinsic PE.")
        
        # Visualize the valuation
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=intrinsic_pe,
            title={'text': "Intrinsic PE"},
            gauge={'axis': {'range': [None, 50]},
                   'bar': {'color': "cyan"},
                   'bgcolor': "lightgrey",
                   'steps': [{'range': [0, 20], 'color': "red"},
                             {'range': [20, 35], 'color': "yellow"},
                             {'range': [35, 50], 'color': "green"}]}
        ))

        st.plotly_chart(fig)
    except Exception as e:
        st.error(f"An error occurred while calculating valuation: {str(e)}")
        st.error("Stack trace:")
        st.code(traceback.format_exc())
