import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path

st.set_page_config(
    page_title="Workora Interactive Analytics Dashboard",
    page_icon="📊",
    layout="wide",
)

st.title("📊 Workora Interactive Analytics Dashboard")
st.caption("Web traffic • Customer churn • Regional market • Checkout A/B testing")

# Supports CSV files uploaded either beside app.py or inside a data/ folder.
ROOT = Path(__file__).resolve().parent
DATA_DIRS = [ROOT / "data", ROOT]

FILES = {
    "traffic": "web_traffic.csv",
    "churn": "customer_churn.csv",
    "market": "regional_market.csv",
    "ab": "checkout_ab_test.csv",
}

def find_csv(filename):
    for folder in DATA_DIRS:
        candidate = folder / filename
        if candidate.exists():
            return candidate
    searched = ", ".join(str(folder / filename) for folder in DATA_DIRS)
    raise FileNotFoundError(f"Can't find {filename}. Checked: {searched}")

@st.cache_data
def load_data():
    traffic = pd.read_csv(find_csv(FILES["traffic"]))
    churn = pd.read_csv(find_csv(FILES["churn"]))
    market = pd.read_csv(find_csv(FILES["market"]))
    ab = pd.read_csv(find_csv(FILES["ab"]))

    # Standardize names so later code is consistent.
    for frame in (traffic, churn, market, ab):
        frame.columns = [str(c).strip() for c in frame.columns]

    traffic["Date"] = pd.to_datetime(traffic["Date"], errors="coerce")
    churn["Churn"] = churn["Churn"].astype(str).str.strip().str.title()
    churn["TotalChargesINR"] = pd.to_numeric(churn["TotalChargesINR"], errors="coerce")
    churn["MonthlyChargesINR"] = pd.to_numeric(churn["MonthlyChargesINR"], errors="coerce")
    churn["Region"] = churn["Region"].fillna("Unknown").astype(str)
    ab["Timestamp"] = pd.to_datetime(ab["Timestamp"], errors="coerce")
    ab["OrderValueINR"] = pd.to_numeric(ab["OrderValueINR"], errors="coerce").fillna(0)
    for col in ["Registered", "Bounced", "StartedRegistration"]:
        if col in traffic.columns:
            traffic[col] = traffic[col].astype(str).str.strip().str.title()
    for col in ["Converted", "CheckoutStarted"]:
        if col in ab.columns:
            ab[col] = ab[col].astype(str).str.strip().str.title()

    return traffic, churn, market, ab

try:
    traffic, churn, market, ab = load_data()
except Exception as exc:
    st.error("The dashboard could not load its CSV data.")
    st.code(str(exc))
    st.info(
        "Keep app.py, requirements.txt, and these four CSV files in the repository root, "
        "or put all four CSV files inside a folder named data: "
        "web_traffic.csv, customer_churn.csv, regional_market.csv, checkout_ab_test.csv."
    )
    st.stop()

# ----- Sidebar filters -----
st.sidebar.header("🔎 Dashboard Filters")

traffic_dates = traffic["Date"].dropna()
if not traffic_dates.empty:
    min_date = traffic_dates.min().date()
    max_date = traffic_dates.max().date()
else:
    min_date, max_date = pd.Timestamp.today().date(), pd.Timestamp.today().date()

date_value = st.sidebar.date_input(
    "Web traffic date range",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date,
)
if isinstance(date_value, (tuple, list)) and len(date_value) == 2:
    start_date, end_date = date_value
else:
    start_date = end_date = date_value

regions = sorted(traffic["Region"].dropna().astype(str).unique().tolist())
selected_regions = st.sidebar.multiselect("Region", regions, default=regions)

category_options = sorted(traffic["Source"].dropna().astype(str).unique().tolist())
selected_sources = st.sidebar.multiselect(
    "Traffic source (category filter)", category_options, default=category_options
)

traffic_f = traffic.copy()
traffic_f = traffic_f[
    traffic_f["Date"].dt.date.between(start_date, end_date)
]
if selected_regions:
    traffic_f = traffic_f[traffic_f["Region"].astype(str).isin(selected_regions)]
else:
    traffic_f = traffic_f.iloc[0:0]
if selected_sources:
    traffic_f = traffic_f[traffic_f["Source"].astype(str).isin(selected_sources)]
else:
    traffic_f = traffic_f.iloc[0:0]


# ----- Customer churn filters -----
churn_f = churn.copy()

# Use the region values that actually exist in the churn dataset.
churn_regions = sorted(
    churn["Region"].dropna().astype(str).unique().tolist()
)

selected_churn_regions = st.sidebar.multiselect(
    "Customer Churn Region",
    options=churn_regions,
    default=churn_regions,
    key="customer_churn_regions",
)

churn_f = churn_f[
    churn_f["Region"].astype(str).isin(selected_churn_regions)
]
# The A/B dataset may cover a different period; if selected dates exclude it all,
# show its full data rather than misleadingly reporting zero revenue.
if ab_f.empty:
    ab_f = ab.copy()

# ----- KPI cards -----
st.subheader("📌 Key Performance Indicators")
total_revenue = float(ab_f.loc[ab_f["Converted"].eq("Yes"), "OrderValueINR"].sum())
active_users = int(traffic_f["SessionID"].nunique()) if "SessionID" in traffic_f.columns else int(len(traffic_f))
churn_rate = float(churn_f["Churn"].eq("Yes").mean() * 100) if not churn_f.empty else 0.0
converted_orders = ab_f.loc[ab_f["Converted"].eq("Yes"), "OrderValueINR"]
avg_ticket = float(converted_orders[converted_orders > 0].mean()) if (converted_orders > 0).any() else 0.0

k1, k2, k3, k4 = st.columns(4)
k1.metric("Total Revenue", f"₹{total_revenue:,.0f}")
k2.metric("Active Sessions", f"{active_users:,}")
k3.metric("Customer Churn", f"{churn_rate:.1f}%")
k4.metric("Average Ticket Size", f"₹{avg_ticket:,.0f}")

st.caption(
    "Revenue and average ticket size use converted checkout orders. "
    "Active sessions use filtered web traffic. Churn uses customers in the selected regions."
)
st.divider()

# ----- Traffic analytics -----
st.subheader("🌐 Web Traffic Analytics")
left, right = st.columns(2)

with left:
    st.markdown("**Sessions by Region**")
    if not traffic_f.empty:
        by_region = traffic_f.groupby("Region", as_index=False).agg(Sessions=("SessionID", "nunique"))
        fig = px.bar(by_region, x="Region", y="Sessions", color="Region", template="plotly_white")
        fig.update_layout(showlegend=False, margin=dict(l=10, r=10, t=25, b=10))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No web traffic matches the current filters.")

with right:
    st.markdown("**Sessions Over Time**")
    if not traffic_f.empty:
        by_day = traffic_f.groupby(traffic_f["Date"].dt.floor("D"), as_index=False).agg(Sessions=("SessionID", "nunique"))
        by_day = by_day.rename(columns={"Date": "Date"})
        fig = px.line(by_day, x="Date", y="Sessions", markers=True, template="plotly_white")
        fig.update_layout(margin=dict(l=10, r=10, t=25, b=10), xaxis_title="Date")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No web traffic matches the current filters.")

st.divider()

# ----- Churn analytics -----
st.subheader("👥 Customer Churn Analysis")
c1, c2 = st.columns(2)
with c1:
    st.markdown("**Churn by Subscription Type**")
    if not churn_f.empty:
        churn_by_plan = (
            churn_f.groupby("SubscriptionType", as_index=False)
            .agg(ChurnRate=("Churn", lambda x: x.eq("Yes").mean() * 100),
                 Customers=("CustomerID", "nunique"))
        )
        fig = px.bar(churn_by_plan, x="SubscriptionType", y="ChurnRate",
                     hover_data=["Customers"], color="SubscriptionType", template="plotly_white",
                     labels={"ChurnRate": "Churn rate (%)"})
        fig.update_layout(showlegend=False, margin=dict(l=10, r=10, t=25, b=10))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No customers match the selected regions.")

with c2:
    st.markdown("**Customer Churn Distribution**")
    if not churn_f.empty:
        churn_counts = churn_f["Churn"].value_counts().rename_axis("Churn").reset_index(name="Customers")
        fig = px.pie(churn_counts, names="Churn", values="Customers", hole=0.45, template="plotly_white")
        fig.update_layout(margin=dict(l=10, r=10, t=25, b=10))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No customers match the selected regions.")

st.divider()

# ----- Regional market analytics -----
st.subheader("📍 Regional Market Opportunities")
m1, m2 = st.columns(2)
with m1:
    st.markdown("**Search Demand by Population Segment**")
    segment = market.groupby("PopulationSegment", as_index=False)["MonthlySearchDemand"].sum()
    fig = px.bar(segment, x="PopulationSegment", y="MonthlySearchDemand",
                 color="PopulationSegment", template="plotly_white")
    fig.update_layout(showlegend=False, margin=dict(l=10, r=10, t=25, b=10))
    st.plotly_chart(fig, use_container_width=True)
with m2:
    st.markdown("**Lead Conversion Rate by State**")
    state = market.groupby("State", as_index=False)["LeadConversionRate"].mean()
    state["LeadConversionRate"] = state["LeadConversionRate"] * 100
    fig = px.bar(state.sort_values("LeadConversionRate", ascending=False).head(12),
                 x="State", y="LeadConversionRate", color="State", template="plotly_white",
                 labels={"LeadConversionRate": "Lead conversion (%)"})
    fig.update_layout(showlegend=False, margin=dict(l=10, r=10, t=25, b=10))
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# ----- A/B testing -----
st.subheader("🧪 Checkout A/B Testing")
if not ab.empty:
    ab_summary = (
        ab.groupby("Variant", as_index=False)
        .agg(Visitors=("VisitorID", "nunique"),
             Conversions=("Converted", lambda x: x.eq("Yes").sum()),
             Revenue=("OrderValueINR", "sum"))
    )
    ab_summary["Conversion Rate (%)"] = (
        ab_summary["Conversions"] / ab_summary["Visitors"].replace(0, pd.NA) * 100
    ).fillna(0).round(2)
    st.dataframe(ab_summary, use_container_width=True, hide_index=True)
    fig = px.bar(ab_summary, x="Variant", y="Conversion Rate (%)", color="Variant",
                 text="Conversion Rate (%)", template="plotly_white",
                 title="Conversion Rate by Variant")
    fig.update_layout(showlegend=False, margin=dict(l=10, r=10, t=45, b=10))
    st.plotly_chart(fig, use_container_width=True)

with st.expander("Preview the filtered web traffic data"):
    st.dataframe(traffic_f.head(100), use_container_width=True)

st.caption("Educational dashboard built with Streamlit, Pandas and Plotly. Revenue is based on the supplied synthetic checkout dataset.")
