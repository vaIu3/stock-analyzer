import pandas as pd
import plotly.express as px
import streamlit as st
import yfinance as yf
import streamlit_analytics

# ۱. پیکربندی صفحه حتماً باید اولین دستور Streamlit باشد
st.set_page_config(
    page_title="Smart Fundamental Analysis & Valuation Dashboard",
    page_icon="📈",
    layout="wide",
)

# استایل اختصاصی
st.markdown(
    """
    <style>
    div[data-testid="stMetricValue"] { font-size: 24px; }
    .stSelectbox label, .stMultiSelect label { font-weight: bold; font-size: 16px; }
    </style>
    """,
    unsafe_allow_html=True,
)


# تابع دریافت داده و محاسبات ارزش‌گذاری (کاش‌شده جهت افزایش سرعت)
@st.cache_data(ttl=3600)
def analyze_stock(
    ticker_symbol,
    wacc_percent=8.5,
    industry_avg_roic=8.0,
    terminal_growth_rate=2.5,
):
    try:
        stock = yf.Ticker(ticker_symbol)
        income_stmt = stock.income_stmt
        cash_flow = stock.cashflow
        balance_sheet = stock.balance_sheet
        info = stock.info

        if income_stmt.empty or balance_sheet.empty:
            return None

        # ۱. صورت سود و زیان (Income Statement)
        try:
            revenue = float(income_stmt.loc["Total Revenue"].iloc[0])
        except KeyError:
            revenue = float(income_stmt.loc["Operating Revenue"].iloc[0])

        try:
            cogs = float(income_stmt.loc["Cost Of Revenue"].iloc[0])
        except KeyError:
            try:
                cogs = float(income_stmt.loc["Reconciled Cost Of Revenue"].iloc[0])
            except KeyError:
                cogs = 0.0

        try:
            operating_income = float(income_stmt.loc["Operating Income"].iloc[0])
        except KeyError:
            op_rev = (
                float(income_stmt.loc["Operating Revenue"].iloc[0])
                if "Operating Revenue" in income_stmt.index
                else revenue
            )
            op_exp = (
                float(income_stmt.loc["Operating Expense"].iloc[0])
                if "Operating Expense" in income_stmt.index
                else 0.0
            )
            operating_income = op_rev - op_exp

        try:
            pretax_income = float(income_stmt.loc["Pretax Income"].iloc[0])
        except KeyError:
            pretax_income = float(income_stmt.loc["Income Before Tax"].iloc[0])

        try:
            tax_provision = float(income_stmt.loc["Tax Provision"].iloc[0])
        except KeyError:
            tax_provision = float(income_stmt.loc["Income Tax Expense"].iloc[0])

        try:
            net_income = float(income_stmt.loc["Net Income"].iloc[0])
        except KeyError:
            net_income = float(
                income_stmt.loc["Net Income Common Stockholders"].iloc[0]
            )

        gross_profit = revenue - cogs
        gross_margin = (gross_profit / revenue) * 100 if revenue != 0 else 0.0
        effective_tax_rate = (
            (tax_provision / pretax_income)
            if (pretax_income > 0 and tax_provision >= 0)
            else 0.21
        )
        nopat = operating_income * (1 - effective_tax_rate)

        # ۲. صورت جریان نقدینگی (Cash Flow)
        try:
            ocf = float(cash_flow.loc["Operating Cash Flow"].iloc[0])
        except KeyError:
            ocf = float(
                cash_flow.loc["Total Cash From Operating Activities"].iloc[0]
            )

        try:
            capex = float(abs(cash_flow.loc["Capital Expenditure"].iloc[0]))
        except KeyError:
            try:
                capex = float(abs(cash_flow.loc["Capital Expenditures"].iloc[0]))
            except KeyError:
                capex = 0.0

        fcf = ocf - capex
        fcfcr = fcf / net_income if net_income != 0 else 0.0

        # ۳. ترازنامه (Balance Sheet)
        try:
            short_term_debt = float(balance_sheet.loc["Current Debt"].iloc[0])
        except KeyError:
            try:
                short_term_debt = float(
                    balance_sheet.loc["Short Long Term Debt"].iloc[0]
                )
            except KeyError:
                short_term_debt = 0.0

        try:
            long_term_debt = float(balance_sheet.loc["Long Term Debt"].iloc[0])
        except KeyError:
            long_term_debt = 0.0

        if short_term_debt > 0 or long_term_debt > 0:
            total_debt = short_term_debt + long_term_debt
        else:
            try:
                total_debt = float(balance_sheet.loc["Total Debt"].iloc[0])
            except KeyError:
                total_debt = 0.0

        try:
            equity = float(balance_sheet.loc["Stockholders Equity"].iloc[0])
        except KeyError:
            equity = float(
                balance_sheet.loc["Total Stockholder Equity"].iloc[0]
            )

        try:
            cash = float(
                balance_sheet.loc[
                    "Cash Cash Equivalents And Short Term Investments"
                ].iloc[0]
            )
        except KeyError:
            try:
                cash = float(
                    balance_sheet.loc["Cash And Cash Equivalents"].iloc[0]
                )
            except KeyError:
                cash = 0.0

        invested_capital = total_debt + equity - cash
        roic = (nopat / invested_capital) * 100 if invested_capital != 0 else 0
        debt_to_equity = total_debt / equity if equity != 0 else 0
        economic_spread = roic - wacc_percent

        # ۴. محاسبه ROIC تاریخی
        historical_roics = []
        num_years = min(len(income_stmt.columns), len(balance_sheet.columns))
        for i in range(num_years):
            try:
                op_inc = float(income_stmt.loc["Operating Income"].iloc[i])
                p_inc = float(income_stmt.loc["Pretax Income"].iloc[i])
                t_prov = float(income_stmt.loc["Tax Provision"].iloc[i])
                t_rate = (t_prov / p_inc) if p_inc > 0 and t_prov >= 0 else 0.21
                h_nopat = op_inc * (1 - t_rate)

                st_d = (
                    float(balance_sheet.loc["Current Debt"].iloc[i])
                    if "Current Debt" in balance_sheet.index
                    else 0.0
                )
                lt_d = (
                    float(balance_sheet.loc["Long Term Debt"].iloc[i])
                    if "Long Term Debt" in balance_sheet.index
                    else 0.0
                )

                if st_d > 0 or lt_d > 0:
                    tot_d = st_d + lt_d
                else:
                    tot_d = (
                        float(balance_sheet.loc["Total Debt"].iloc[i])
                        if "Total Debt" in balance_sheet.index
                        else 0.0
                    )

                eq = (
                    float(balance_sheet.loc["Stockholders Equity"].iloc[i])
                    if "Stockholders Equity" in balance_sheet.index
                    else float(
                        balance_sheet.loc["Total Stockholder Equity"].iloc[i]
                    )
                )
                c_sh = (
                    float(
                        balance_sheet.loc[
                            "Cash Cash Equivalents And Short Term Investments"
                        ].iloc[i]
                    )
                    if "Cash Cash Equivalents And Short Term Investments"
                    in balance_sheet.index
                    else float(
                        balance_sheet.loc["Cash And Cash Equivalents"].iloc[i]
                    )
                )

                inv_cap = tot_d + eq - c_sh
                if inv_cap > 0:
                    historical_roics.append(round((h_nopat / inv_cap) * 100, 2))
            except Exception:
                continue

        avg_historical_roic = (
            round(sum(historical_roics) / len(historical_roics), 2)
            if historical_roics
            else round(roic, 2)
        )

        # ۵. داده‌های بازار و FCF Yield
        shares = int(
            info.get("sharesOutstanding")
            or info.get("impliedSharesOutstanding")
            or 1
        )
        current_price = float(
            info.get("currentPrice") or info.get("regularMarketPrice") or 0.0
        )
        market_cap = float(info.get("marketCap") or (current_price * shares))
        fcf_yield = (fcf / market_cap) * 100 if market_cap != 0 else 0.0

        # ۶. مدل DCF دو مرحله‌ای
        reinvestment_rate = capex / nopat if nopat > 0 else 0.5
        intrinsic_g = (roic / 100.0) * reinvestment_rate
        intrinsic_g_capped = min(max(intrinsic_g, 0.0), 0.25)

        wacc_dec = wacc_percent / 100.0
        gp_dec = terminal_growth_rate / 100.0

        # جلوگیری از تقسیم بر صفر یا مخرج منفی در DCF
        if wacc_dec <= gp_dec:
            wacc_dec = gp_dec + 0.001

        fcf_projections = []
        total_pv_phase_1 = 0.0
        fcf_curr = fcf

        for t in range(1, 6):
            fcf_curr = fcf_curr * (1 + intrinsic_g_capped)
            pv_t = fcf_curr / ((1 + wacc_dec) ** t)
            fcf_projections.append(fcf_curr)
            total_pv_phase_1 += pv_t

        terminal_value_5 = (fcf_projections[-1] * (1 + gp_dec)) / (
            wacc_dec - gp_dec
        )
        pv_terminal_value = terminal_value_5 / ((1 + wacc_dec) ** 5)

        equity_value = total_pv_phase_1 + pv_terminal_value + cash - total_debt
        intrinsic_value_per_share = (
            equity_value / shares if shares > 0 else 0.0
        )
        margin_of_safety = (
            ((intrinsic_value_per_share - current_price) / current_price) * 100
            if current_price > 0
            else 0.0
        )

        return {
            "symbol": ticker_symbol,
            "name": info.get("longName", ticker_symbol),
            "current_price": current_price,
            "market_cap": market_cap,
            "revenue": revenue,
            "cogs": cogs,
            "gross_profit": gross_profit,
            "gross_margin": round(gross_margin, 2),
            "net_income": net_income,
            "nopat": nopat,
            "ocf": ocf,
            "capex": capex,
            "fcf": fcf,
            "fcfcr": round(fcfcr, 2),
            "cash": cash,
            "total_debt": total_debt,
            "equity": equity,
            "debt_to_equity": round(debt_to_equity, 2),
            "invested_capital": invested_capital,
            "roic": round(roic, 2),
            "historical_roics": historical_roics,
            "avg_roic": avg_historical_roic,
            "industry_avg_roic": industry_avg_roic,
            "wacc": round(wacc_percent, 2),
            "spread": round(economic_spread, 2),
            "reinvestment_rate": round(reinvestment_rate * 100, 2),
            "intrinsic_g": round(intrinsic_g_capped * 100, 2),
            "terminal_g": round(terminal_growth_rate, 2),
            "intrinsic_value": round(intrinsic_value_per_share, 2),
            "margin_of_safety": round(margin_of_safety, 2),
            "fcf_yield": round(fcf_yield, 2),
            "shares": shares,
        }
    except Exception as e:
        st.error(f"Error fetching data for ticker {ticker_symbol}: {str(e)}")
        return None


# ردیابی آماری پس از تنظیمات اولیه صفحه
with streamlit_analytics.track():
    # --- Sidebar Setup ---
    st.sidebar.title("⚙️ DCF Model Inputs")
    wacc_input = st.sidebar.slider(
        "Cost of Capital (WACC %)", 5.0, 15.0, 9.0, 0.5
    )
    industry_roic_input = st.sidebar.number_input(
        "Industry Avg ROIC (%)", value=10.0
    )
    terminal_g_input = st.sidebar.slider(
        "Terminal Growth Rate (%)", 1.0, 5.0, 2.5, 0.1
    )

    # --- Main App Title ---
    st.title("📊 Smart Fundamental Stock Analysis & Valuation System")
    st.caption(
        "Based on Warren Buffett's valuation principles, Cash Flow Analysis, and DCF Modeling"
    )

    # --- Main Tabs ---
    tab1, tab2 = st.tabs(["🔍 Single Stock Analysis", "⚖️ Compare Companies"])

    # ==========================================
    # Tab 1: Comprehensive Single Stock Analysis
    # ==========================================
    with tab1:
        POPULAR_STOCKS = {
            "NVDA": "NVIDIA Corporation (NASDAQ)",
            "AAPL": "Apple Inc. (NASDAQ)",
            "MSFT": "Microsoft Corporation (NASDAQ)",
            "GOOGL": "Alphabet Inc. (NASDAQ)",
            "AMZN": "Amazon.com Inc. (NASDAQ)",
            "META": "Meta Platforms Inc. (NASDAQ)",
            "TSLA": "Tesla Inc. (NASDAQ)",
        }

        st.subheader("🔎 Search Stock Ticker")
        col_search, _ = st.columns([2, 1])

        with col_search:
            selected_ticker = st.selectbox(
                "Select a ticker or type your own:",
                options=list(POPULAR_STOCKS.keys()),
                format_func=lambda x: f"{x} - {POPULAR_STOCKS.get(x, '')}",
                index=0,
            )

        if selected_ticker:
            with st.spinner(
                f"Fetching and analyzing data for {selected_ticker}..."
            ):
                data = analyze_stock(
                    selected_ticker,
                    wacc_percent=wacc_input,
                    industry_avg_roic=industry_roic_input,
                    terminal_growth_rate=terminal_g_input,
                )

            if data:
                st.markdown("---")
                st.header(f"🏛️ {data['name']} ({data['symbol']})")

                # 1. Main KPI Metrics
                m1, m2, m3, m4, m5 = st.columns(5)
                m1.metric("Market Price", f"${data['current_price']}")
                m2.metric(
                    "Intrinsic Value per Share", f"${data['intrinsic_value']}"
                )

                mos_color = (
                    "normal" if data["margin_of_safety"] >= 20 else "inverse"
                )
                m3.metric(
                    "Margin of Safety (MOS)",
                    f"{data['margin_of_safety']}%",
                    delta_color=mos_color,
                )
                m4.metric("Return on Capital (ROIC)", f"{data['roic']}%")
                m5.metric("FCFCR Conversion Rate", f"{data['fcfcr']}")

                st.markdown("---")

                # 2. Detailed Breakdowns
                col_left, col_right = st.columns(2)

                with col_left:
                    with st.expander(
                        "1. Intrinsic Valuation (2-Stage DCF)", expanded=True
                    ):
                        st.write(
                            f"**Phase 1 Intrinsic Growth Rate (g):** {data['intrinsic_g']}%"
                        )
                        st.write(
                            f"**Reinvestment Rate:** {data['reinvestment_rate']}%"
                        )
                        st.write(
                            "**Valuation Signal:** "
                            + (
                                "🟢 Undervalued"
                                if data["margin_of_safety"] >= 20
                                else (
                                    "🟡 Fairly Valued"
                                    if data["margin_of_safety"] >= -10
                                    else "🔴 Overvalued"
                                )
                            )
                        )

                    with st.expander(
                        "2. Economic Moat Analysis", expanded=True
                    ):
                        is_high = (
                            all(r >= 15.0 for r in data["historical_roics"])
                            if data["historical_roics"]
                            else False
                        )
                        is_above = data["avg_roic"] > data["industry_avg_roic"]
                        if is_high and is_above:
                            moat_str = "🏰 Strong & Sustainable (Wide Moat)"
                        elif data["avg_roic"] >= 12.0 and is_above:
                            moat_str = "🛡️ Moderate (Narrow Moat)"
                        else:
                            moat_str = "❌ No Moat"

                        st.write(f"**Estimated Moat:** {moat_str}")
                        st.write(
                            f"**Historical Avg ROIC:** {data['avg_roic']}%"
                        )
                        st.write(
                            f"**Industry Avg:** {data['industry_avg_roic']}%"
                        )

                    with st.expander("3. Profitability & Margins"):
                        st.write(f"**Revenue:** ${data['revenue']/1e9:.2f}B")
                        st.write(f"**Gross Margin:** {data['gross_margin']}%")
                        st.write(
                            f"**Net Income:** ${data['net_income']/1e9:.2f}B"
                        )

                with col_right:
                    with st.expander("4. Balance Sheet & Debt"):
                        st.write(
                            f"**Debt-to-Equity Ratio (D/E):**"
                            f" {data['debt_to_equity']}"
                        )
                        st.write(
                            f"**Total Interest-Bearing Debt:** ${data['total_debt']/1e9:.2f}B"
                        )
                        st.write(
                            f"**Cash & Equivalents:** ${data['cash']/1e9:.2f}B"
                        )

                    with st.expander(
                        "5. Return on Invested Capital (ROIC vs WACC)"
                    ):
                        st.write(f"**ROIC:** {data['roic']}%")
                        st.write(f"**WACC:** {data['wacc']}%")
                        st.write(f"**Economic Spread:** {data['spread']}%")

                    with st.expander(
                        "6. Cash Flow & Earnings Quality (FCFCR)",
                        expanded=True,
                    ):
                        st.write(
                            f"**Free Cash Flow (FCF):** ${data['fcf']/1e9:.2f}B"
                        )
                        st.write(
                            f"**Cash Conversion Ratio (FCFCR):** {data['fcfcr']}"
                        )
                        if data["fcfcr"] >= 1.0:
                            st.success("🟢 Excellent Earnings Quality")
                        elif data["fcfcr"] >= 0.5:
                            st.warning("🟡 Average Earnings Quality")
                        else:
                            st.error(
                                "🚨 Warning: Paper profits lacking cash backing"
                            )

                    with st.expander(
                        "7. Free Cash Flow Yield (FCF Yield)", expanded=True
                    ):
                        st.write(f"**FCF Yield:** {data['fcf_yield']}%")
                        if data["fcf_yield"] >= 8.0:
                            st.success(
                                "🟢 Highly undervalued and cash-generating"
                            )
                        elif data["fcf_yield"] >= 3.0:
                            st.info("🟡 Fairly priced")
                        else:
                            st.error(
                                "🔴 Expensive relative to cash generation"
                            )

    # ==========================================
    # Tab 2: Compare Multiple Companies
    # ==========================================
    with tab2:
        st.subheader("⚖️ Compare Multiple Stocks Simultaneously")
        compare_tickers = st.multiselect(
            "Select ticker symbols to compare:",
            options=["NVDA", "AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA"],
            default=["NVDA", "AAPL", "MSFT"],
        )

        if compare_tickers:
            comp_data = []
            for t in compare_tickers:
                res = analyze_stock(
                    t,
                    wacc_percent=wacc_input,
                    industry_avg_roic=industry_roic_input,
                    terminal_growth_rate=terminal_g_input,
                )
                if res:
                    comp_data.append(res)

            if comp_data:
                df_comp = pd.DataFrame(comp_data)

                # Comparison Table
                st.markdown("### 📋 Fundamental Metrics Comparison Table")
                st.dataframe(
                    df_comp[
                        [
                            "symbol",
                            "current_price",
                            "intrinsic_value",
                            "margin_of_safety",
                            "roic",
                            "fcfcr",
                            "fcf_yield",
                            "debt_to_equity",
                        ]
                    ].rename(
                        columns={
                            "symbol": "Ticker",
                            "current_price": "Current Price ($)",
                            "intrinsic_value": "Intrinsic Value ($)",
                            "margin_of_safety": "Margin of Safety (%)",
                            "roic": "ROIC (%)",
                            "fcfcr": "FCFCR",
                            "fcf_yield": "FCF Yield (%)",
                            "debt_to_equity": "D/E Ratio",
                        }
                    ),
                    use_container_width=True,
                )

                # Comparison Chart (ROIC)
                st.markdown("### 📊 ROIC Comparison Chart")
                fig = px.bar(
                    df_comp,
                    x="symbol",
                    y="roic",
                    title="Return on Invested Capital (ROIC) Comparison",
                    labels={"symbol": "Company Ticker", "roic": "ROIC (%)"},
                    color="roic",
                    color_continuous_scale="Viridis",
                )
                st.plotly_chart(fig, use_container_width=True)
