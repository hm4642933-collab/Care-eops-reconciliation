import io
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(
    page_title="SU Reconciliation & Property Dashboard",
    page_icon="📊",
    layout="wide",
)

# Custom Styling
st.markdown(
    """
    <style>
    div.stButton > button[kind="primary"], div.stButton > button {
        background-color: #17a2b8 !important;
        color: white !important;
        border: 1px solid #17a2b8 !important;
        border-radius: 5px !important;
        font-weight: 600 !important;
        font-size: 15px !important;
        padding: 8px 16px !important;
        transition: all 0.3s ease !important;
    }
    div.stButton > button:hover {
        background-color: #138496 !important;
        border-color: #117a8b !important;
        color: white !important;
        box-shadow: 0px 4px 8px rgba(0,0,0,0.2) !important;
    }
    .stSidebar {
        background-color: #1e222d;
    }
    .brand-box {
        background: linear-gradient(135deg, #17a2b8, #117a8b);
        padding: 15px;
        border-radius: 8px;
        text-align: center;
        color: white;
        margin-bottom: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .brand-title {
        font-size: 18px;
        font-weight: 700;
        margin: 0;
    }
    </style>
""",
    unsafe_allow_html=True,
)

# Initialize Session States safely
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "navigation_page" not in st.session_state:
    st.session_state.navigation_page = "📋 Care Master vs EOPS Reconciliation"

if "processed" not in st.session_state:
    st.session_state.processed = False

# Authentication Portal
if not st.session_state.logged_in:
    st.title("🔒 Access Login Portal")
    st.write("Please log in to access the Reconciliation & Property Dashboard.")

    col_u, col_p = st.columns(2)
    with col_u:
        u = st.text_input("Username")
    with col_p:
        p = st.text_input("Password", type="password")

    if st.button("Log In"):
        if u == "admin" and p == "password123":
            st.session_state.logged_in = True
            st.rerun()
        else:
            st.error("❌ Invalid credentials")
    st.stop()

# Sidebar Navigation
with st.sidebar:
    st.markdown(
        """
            <div class="brand-box">
                <div style="font-size: 24px; margin-bottom: 3px;">🏢</div>
                <p class="brand-title">Comfort Care Services</p>
                <div style="font-size: 13px; opacity: 0.9; margin-top: 2px;">Portal</div>
            </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("### 📌 **Portal Menu**")

    if st.button("🚪 Log Out", use_container_width=True):
        st.session_state.logged_in = False
        st.rerun()

    st.markdown("---")
    st.markdown("### **Select Section / Tab:**")

    if st.button(
        "📋 Care Master vs EOPS Reconciliation",
        use_container_width=True,
        key="btn_recon",
    ):
        st.session_state.navigation_page = "📋 Care Master vs EOPS Reconciliation"

    if st.button(
        "🏠 Property Dashboard", use_container_width=True, key="btn_prop"
    ):
        st.session_state.navigation_page = "🏠 Property Dashboard"

    navigation_page = st.session_state.navigation_page


def clean_suid(series):
    return (
        series.astype(str)
        .str.strip()
        .str.replace(r"\.0$", "", regex=True)
        .str.upper()
        .replace(["NAN", "NONE", "<NA>", ""], pd.NA)
    )


def to_excel_bytes(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Sheet1")
    return output.getvalue()


# Main Application
st.title("📊 Care Master vs EOPS Reconciliation & Property Portal")

col1, col2, col3 = st.columns(3)
with col1:
    cm_file = st.file_uploader(
        "Upload Care Master File (.xlsx)", type=["xlsx", "xls"]
    )
with col2:
    eops_file = st.file_uploader("Upload EOPS File (.xlsx)", type=["xlsx", "xls"])
with col3:
    prop_data_file = st.file_uploader(
        "Upload Property Data File (.xlsx)", type=["xlsx", "xls"]
    )

if cm_file:
    st.session_state.cm_file_bytes = cm_file.getvalue()
if eops_file:
    st.session_state.eops_file_bytes = eops_file.getvalue()
if prop_data_file:
    st.session_state.prop_data_bytes = prop_data_file.getvalue()

has_files = (
    "cm_file_bytes" in st.session_state
    and "eops_file_bytes" in st.session_state
    and "prop_data_bytes" in st.session_state
)

if has_files:
    if st.button("🚀 Process Reconciliation & Dashboard", use_container_width=True):
        try:
            with st.spinner("Processing Data..."):
                df_cm = pd.read_excel(
                    io.BytesIO(st.session_state.cm_file_bytes), dtype=str
                )
                df_eops = pd.read_excel(
                    io.BytesIO(st.session_state.eops_file_bytes), dtype=str
                )
                df_prop_meta = pd.read_excel(
                    io.BytesIO(st.session_state.prop_data_bytes), dtype=str
                )

                df_cm.columns = [str(c).strip() for c in df_cm.columns]
                df_eops.columns = [str(c).strip() for c in df_eops.columns]
                df_prop_meta.columns = [
                    str(c).strip() for c in df_prop_meta.columns
                ]

                def get_col(df, possible_names):
                    for name in possible_names:
                        for col in df.columns:
                            if col.lower().strip() == name.lower().strip():
                                return col
                    return None

                eops_suid_col = get_col(
                    df_eops,
                    ["SUID", "Resident Ref", "SU Ref", "Service User ID", "Ref"],
                )
                cm_suid_col = get_col(
                    df_cm,
                    ["Resident Ref", "SUID", "SU Ref", "Service User ID", "Ref"],
                )

                if not eops_suid_col or not cm_suid_col:
                    st.error(
                        "❌ Error: SUID / Resident Ref column not found in EOPS or Care Master files."
                    )
                    st.stop()

                df_eops["SUID_Clean"] = clean_suid(df_eops[eops_suid_col])
                df_cm["SUID_Clean"] = clean_suid(df_cm[cm_suid_col])

                df_eops = df_eops.dropna(subset=["SUID_Clean"]).copy()
                df_cm = df_cm.dropna(subset=["SUID_Clean"]).copy()

                fn_eops = get_col(
                    df_eops, ["Service User Name", "SU Name", "First Name"]
                )
                sn_eops = get_col(df_eops, ["SU Surname", "Surname", "Last Name"])

                df_eops["EOPS_Name"] = (
                    (df_eops[fn_eops].fillna("") if fn_eops else "")
                    + " "
                    + (df_eops[sn_eops].fillna("") if sn_eops else "")
                ).str.strip()
                df_eops["SU Name"] = (
                    df_eops["EOPS_Name"].replace("", "N/A").fillna("N/A")
                )

                adm_eops = get_col(
                    df_eops,
                    [
                        "Admission Date",
                        "Admit Date",
                        "Admission_Date",
                        "Start Date",
                        "StartDate",
                    ],
                )
                if adm_eops:
                    parsed_dates = pd.to_datetime(
                        df_eops[adm_eops], errors="coerce"
                    )
                    df_eops["Admission Date"] = parsed_dates.dt.strftime(
                        "%d/%m/%Y"
                    )
                    df_eops["Admission Date"] = df_eops["Admission Date"].fillna(
                        df_eops[adm_eops].astype(str).str.strip()
                    )
                    df_eops["Admission Date"] = df_eops[
                        "Admission Date"
                    ].replace(["nan", "NAT", "NaT", ""], "N/A")
                else:
                    df_eops["Admission Date"] = "N/A"

                fa_col = get_col(
                    df_eops,
                    [
                        "FundingAuthority",
                        "Funding Authority",
                        "Council Name",
                        "LA Name",
                        "Split Funding Council",
                    ],
                )
                df_eops["Funding Authority"] = (
                    df_eops[fa_col].astype(str).str.strip().fillna("N/A")
                    if fa_col
                    else "N/A"
                )

                prop_eops = get_col(
                    df_eops,
                    ["Property", "Property Address", "Address", "Property_Address"],
                )
                df_eops["Property"] = (
                    df_eops[prop_eops].astype(str).str.strip().fillna("N/A")
                    if prop_eops
                    else "N/A"
                )

                core_h = get_col(df_eops, ["Core Hours"])
                dm_h = get_col(df_eops, ["Direct Management On Site Hours"])
                core_c = get_col(df_eops, ["Core Weekly Charges"])
                dm_c = get_col(
                    df_eops, ["Direct Management On Site Weekly Charges"]
                )
                one_h = get_col(df_eops, ["Total 1:1 + PC Hours", "1to1 Hours"])
                one_c = get_col(
                    df_eops, ["Total 1:1 Weekly Charges", "1to1 Charges"]
                )

                for col in [core_h, dm_h, core_c, dm_c, one_h, one_c]:
                    if col:
                        df_eops[col] = pd.to_numeric(
                            df_eops[col], errors="coerce"
                        ).fillna(0)

                df_eops["EOPS Core Hours"] = (
                    df_eops[core_h] if core_h else 0
                ) + (df_eops[dm_h] if dm_h else 0)
                df_eops["EOPS Core Weekly Rate"] = (
                    df_eops[core_c] if core_c else 0
                ) + (df_eops[dm_c] if dm_c else 0)
                df_eops["EOPS 1to1 Hours"] = df_eops[one_h] if one_h else 0
                df_eops["EOPS 1to1 Weekly Rate"] = df_eops[one_c] if one_c else 0

                charge_col = get_col(df_cm, ["Charge Type"])
                df_cm["Charge Type Clean"] = (
                    df_cm[charge_col].astype(str).str.strip().str.upper()
                    if charge_col
                    else ""
                )

                df_cm = df_cm[
                    ~df_cm["Charge Type Clean"].isin([
                        "TC",
                        "HB",
                        "TENANT CONTRIBUTION",
                        "HOUSING BENEFIT",
                        "TOP UP",
                        "TOPUP",
                    ])
                ].copy()

                rep_hrs = get_col(df_cm, ["Report Hours", "Hours"])
                w_fee = get_col(df_cm, ["Total Weekly Fee", "Weekly Fee", "Fee"])

                for col in [rep_hrs, w_fee]:
                    if col:
                        df_cm[col] = pd.to_numeric(
                            df_cm[col], errors="coerce"
                        ).fillna(0)

                cm_core = (
                    df_cm[
                        df_cm["Charge Type Clean"].isin([
                            "STAND",
                            "DIRECT MANAGEMENT",
                            "DIRECT MANAGEMENT ON SITE",
                            "CORE",
                        ])
                    ]
                    .groupby("SUID_Clean")
                    .agg({
                        rep_hrs: "sum" if rep_hrs else lambda x: 0,
                        w_fee: "sum" if w_fee else lambda x: 0,
                    })
                    .rename(
                        columns={
                            rep_hrs: "CM Core Hours",
                            w_fee: "CM Core Weekly Rate",
                        }
                    )
                )

                cm_1to1 = (
                    df_cm[
                        df_cm["Charge Type Clean"].isin(
                            ["1TO1", "PC", "PERSONAL CARE", "1:1"]
                        )
                    ]
                    .groupby("SUID_Clean")
                    .agg({
                        rep_hrs: "sum" if rep_hrs else lambda x: 0,
                        w_fee: "sum" if w_fee else lambda x: 0,
                    })
                    .rename(
                        columns={
                            rep_hrs: "CM 1to1 Hours",
                            w_fee: "CM 1to1 Weekly Rate",
                        }
                    )
                )

                recon = df_eops[[
                    "SUID_Clean",
                    "SU Name",
                    "Admission Date",
                    "Funding Authority",
                    "Property",
                    "EOPS Core Hours",
                    "EOPS Core Weekly Rate",
                    "EOPS 1to1 Hours",
                    "EOPS 1to1 Weekly Rate",
                ]].copy()

                recon = pd.merge(recon, cm_core, on="SUID_Clean", how="left")
                recon = pd.merge(
                    recon, cm_1to1, on="SUID_Clean", how="left"
                ).fillna(0)

                recon["Core Hours Difference"] = (
                    recon["CM Core Hours"] - recon["EOPS Core Hours"]
                )
                recon["Core Weekly Rate Difference"] = (
                    recon["CM Core Weekly Rate"]
                    - recon["EOPS Core Weekly Rate"]
                )
                recon["1to1 Hours Difference"] = (
                    recon["CM 1to1 Hours"] - recon["EOPS 1to1 Hours"]
                )
                recon["1to1 Weekly Rate Difference"] = (
                    recon["CM 1to1 Weekly Rate"] - recon["EOPS 1to1 Weekly Rate"]
                )

                recon["CM Total Weekly Rate"] = (
                    recon["CM Core Weekly Rate"]
                    + recon["CM 1to1 Weekly Rate"]
                )
                recon["EOPS Total Weekly Rate"] = (
                    recon["EOPS Core Weekly Rate"]
                    + recon["EOPS 1to1 Weekly Rate"]
                )
                recon["Total Rate Difference"] = (
                    recon["CM Total Weekly Rate"]
                    - recon["EOPS Total Weekly Rate"]
                )

                recon_output = recon.rename(columns={"SUID_Clean": "SUID"})

                final_recon = recon_output[[
                    "SUID",
                    "SU Name",
                    "Admission Date",
                    "Funding Authority",
                    "Property",
                    "CM Core Hours",
                    "EOPS Core Hours",
                    "Core Hours Difference",
                    "CM Core Weekly Rate",
                    "EOPS Core Weekly Rate",
                    "Core Weekly Rate Difference",
                    "CM 1to1 Hours",
                    "EOPS 1to1 Hours",
                    "1to1 Hours Difference",
                    "CM 1to1 Weekly Rate",
                    "EOPS 1to1 Weekly Rate",
                    "1to1 Weekly Rate Difference",
                    "CM Total Weekly Rate",
                    "EOPS Total Weekly Rate",
                    "Total Rate Difference",
                ]].copy()

                final_recon.insert(0, "S.No", range(1, len(final_recon) + 1))

                property_detail_df = recon_output[[
                    "SUID",
                    "SU Name",
                    "Admission Date",
                    "Funding Authority",
                    "Property",
                    "EOPS Core Hours",
                    "EOPS 1to1 Hours",
                ]].copy()

                property_detail_df.rename(
                    columns={
                        "EOPS Core Hours": "Core Hours",
                        "EOPS 1to1 Hours": "1to1 Hours",
                    },
                    inplace=True,
                )

                property_detail_df["Total Hours"] = (
                    property_detail_df["Core Hours"]
                    + property_detail_df["1to1 Hours"]
                )
                property_detail_df.insert(
                    0, "S.No", range(1, len(property_detail_df) + 1)
                )

                st.session_state.processed = True
                st.session_state.final_recon = final_recon
                st.session_state.property_detail_df = property_detail_df
                st.session_state.df_prop_meta = df_prop_meta
                st.success("✅ Data Processed Successfully!")
                st.rerun()

        except Exception as e:
            st.error(f"❌ An error occurred during processing: {e}")

if st.session_state.get("processed", False):
    try:
        final_recon = st.session_state.final_recon
        property_detail_df = st.session_state.property_detail_df
        df_prop_meta = st.session_state.df_prop_meta

        if st.session_state.navigation_page == "📋 Care Master vs EOPS Reconciliation":
            st.subheader("📋 Care Master vs EOPS Reconciliation Table")
            st.dataframe(final_recon, use_container_width=True)

            recon_excel = to_excel_bytes(final_recon)
            st.download_button(
                label="📥 Download Care Master vs EOPS Reconciliation Excel",
                data=recon_excel,
                file_name="CareMaster_vs_EOPS_Reconciliation.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

        elif st.session_state.navigation_page == "🏠 Property Dashboard":
            st.subheader("🏠 Property Dynamic Dashboard")

            unique_props = [
                str(p).strip()
                for p in property_detail_df["Property"].dropna().unique()
                if str(p).strip() != "" and str(p).strip() != "N/A"
            ]
            property_options = ["All Properties"] + sorted(list(set(unique_props)))

            selected_property = st.selectbox(
                "Search or Select Property:", property_options
            )

            if selected_property == "All Properties":
                total_occupied_eops = property_detail_df["SUID"].nunique()
                filtered_dashboard_df = property_detail_df
            else:
                filtered_dashboard_df = property_detail_df[
                    property_detail_df["Property"].astype(str)
                    == selected_property
                ]
                total_occupied_eops = filtered_dashboard_df["SUID"].nunique()

            # Display only Occupied Beds metric
            st.metric(
                "👥 Occupied Beds (EOPS)", f"{total_occupied_eops:,.0f}"
            )

            st.markdown("---")

            col_chart, _ = st.columns([2, 1])
            with col_chart:
                core_sum = filtered_dashboard_df["Core Hours"].sum()
                one_to_one_sum = filtered_dashboard_df["1to1 Hours"].sum()

                chart_data = pd.DataFrame({
                    "Hours Type": ["1to1 Hours", "Core Hours"],
                    "Hours": [one_to_one_sum, core_sum],
                })

                fig_circle = px.pie(
                    chart_data,
                    values="Hours",
                    names="Hours Type",
                    hole=0.5,
                    title=f"⭕ Core vs 1to1 Total Hours ({selected_property})",
                    color_discrete_sequence=["#1f77b4", "#ff7f0e"],
                )
                fig_circle.update_traces(textinfo="value")
                st.plotly_chart(fig_circle, use_container_width=True)

            st.dataframe(filtered_dashboard_df, use_container_width=True)

            prop_excel = to_excel_bytes(filtered_dashboard_df)
            st.download_button(
                label=(
                    "📥 Download Property Dashboard Report Excel"
                    f" ({selected_property})"
                ),
                data=prop_excel,
                file_name=(
                    "Property_Dashboard_Report_"
                    f"{selected_property.replace(' ', '_')}.xlsx"
                ),
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
    except Exception as e:
        st.error(f"❌ Display Error: {e}")
