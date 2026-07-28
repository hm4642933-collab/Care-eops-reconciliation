import streamlit as st
import pandas as pd
import io

st.set_page_config(
    page_title="SU Reconciliation & Property Dashboard",
    page_icon="📊",
    layout="wide"
)

# Custom Styling for Bootstrap 'btn-info' styled Logout button and Sidebar Navigation
st.markdown("""
    <style>
    /* Bootstrap btn-info Style for Logout Button */
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
    .stRadio > label {
        font-weight: bold;
        font-size: 16px;
    }
    </style>
""", unsafe_allow_html=True)

# ==================== 1. AUTHENTICATION ====================
USERNAME = "admin"
PASSWORD = "password123"

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🔒 Access Login Portal")
    st.write("Please log in to access the Reconciliation & Property Dashboard.")
    
    col_u, col_p = st.columns(2)
    with col_u:
        u = st.text_input("Username")
    with col_p:
        p = st.text_input("Password", type="password")
        
    if st.button("Log In"):
        if u == USERNAME and p == PASSWORD:
            st.session_state.logged_in = True
            st.rerun()
        else:
            st.error("❌ Invalid credentials")
    st.stop()

# ==================== 2. SIDEBAR NAVIGATION ====================
with st.sidebar:
    st.markdown("### 🏢 **Portal Menu**")
    
    # Bootstrap btn-info styled Log Out Button
    if st.button("🚪 Log Out", use_container_width=True):
        st.session_state.logged_in = False
        st.rerun()
        
    st.markdown("---")
    
    # Sidebar Navigation Tabs
    navigation_page = st.radio(
        "Select Section / Tab:",
        ["📋 Care Master vs EOPS Reconciliation", "🏠 Property Dashboard"],
        index=0
    )

# ==================== 3. MAIN APPLICATION ====================
st.title("📊 Care Master vs EOPS Reconciliation & Property Portal")

col1, col2 = st.columns(2)
with col1:
    cm_file = st.file_uploader("Upload Care Master File (.xlsx)", type=["xlsx", "xls"])
with col2:
    eops_file = st.file_uploader("Upload EOPS File (.xlsx)", type=["xlsx", "xls"])

if cm_file and eops_file:
    if st.button("🚀 Process Reconciliation & Dashboard", use_container_width=True):
        with st.spinner("Processing Data..."):
            
            # --- LOAD DATASETS ---
            df_cm = pd.read_excel(cm_file)
            df_eops = pd.read_excel(eops_file)

            # Clean Headers
            df_cm.columns = [str(c).strip() for c in df_cm.columns]
            df_eops.columns = [str(c).strip() for c in df_eops.columns]
            
            # Helper for safe column detection
            def get_col(df, possible_names):
                for name in possible_names:
                    for col in df.columns:
                        if col.lower().strip() == name.lower().strip():
                            return col
                return None

            # 1. SUID: EOPS aur Care Master dono se match/combine
            cm_suid_col = get_col(df_cm, ['Resident Ref', 'SUID', 'SU Ref', 'Service User ID'])
            eops_suid_col = get_col(df_eops, ['SUID', 'Resident Ref', 'SU Ref', 'Service User ID'])

            if not cm_suid_col or not eops_suid_col:
                st.error("❌ Error: SUID / Resident Ref column missing in uploaded files.")
                st.stop()

            df_cm['SUID_Clean'] = df_cm[cm_suid_col].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
            df_eops['SUID_Clean'] = df_eops[eops_suid_col].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
            
            # 2. SU Name: EOPS & CM se compile
            fn_eops = get_col(df_eops, ['Service User Name', 'SU Name', 'First Name'])
            sn_eops = get_col(df_eops, ['SU Surname', 'Surname', 'Last Name'])
            cm_name = get_col(df_cm, ['Service User Name', 'SU Name', 'Resident Name', 'Client Name'])

            df_eops['EOPS_Name'] = (df_eops[fn_eops].fillna('') if fn_eops else '') + ' ' + (df_eops[sn_eops].fillna('') if sn_eops else '')
            df_eops['EOPS_Name'] = df_eops['EOPS_Name'].str.strip()

            cm_names_dict = df_cm.groupby('SUID_Clean')[cm_name].first().to_dict() if cm_name else {}

            # 3. Admission Date: EOPS se mapped
            adm_eops = get_col(df_eops, ['Admission Date', 'Admit Date', 'Admission_Date'])
            if adm_eops:
                df_eops['Admission Date Clean'] = pd.to_datetime(df_eops[adm_eops], errors='coerce').dt.strftime('%d/%m/%Y')
            else:
                df_eops['Admission Date Clean'] = "N/A"

            # 4. Funding Authority: Council Name / Split Funding
            fa_col = get_col(df_eops, ['FundingAuthority', 'Funding Authority', 'Council Name', 'LA Name', 'Split Funding Council'])
            df_eops['Council Name'] = df_eops[fa_col].astype(str).str.strip() if fa_col else 'N/A'

            # 5. Property Address: EOPS se liya jaye
            prop_eops = get_col(df_eops, ['Property', 'Property Address', 'Address', 'Property_Address'])
            df_eops['Property Address EOPS'] = df_eops[prop_eops].astype(str).str.strip() if prop_eops else 'N/A'

            # --- EOPS BASE TABLE ---
            eops_base = df_eops.groupby('SUID_Clean').agg({
                'EOPS_Name': 'first',
                'Admission Date Clean': 'first',
                'Council Name': 'first',
                'Property Address EOPS': 'first'
            }).reset_index()

            # SU Name Compile logic (EOPS fallback to CM if blank)
            eops_base['SU Name'] = eops_base.apply(
                lambda r: r['EOPS_Name'] if r['EOPS_Name'] != '' else cm_names_dict.get(r['SUID_Clean'], 'N/A'), axis=1
            )

            # --- CHARGE TYPE FILTERING & CM CALCULATIONS ---
            charge_col = get_col(df_cm, ['Charge Type'])
            df_cm['Charge Type Clean'] = df_cm[charge_col].astype(str).str.strip().str.upper() if charge_col else ""
            df_cm = df_cm[~df_cm[cm_suid_col].astype(str).str.startswith(('BLOCK', 'Block', 'BLK'), na=False)].copy()

            rep_hrs = get_col(df_cm, ['Report Hours', 'Hours'])
            w_fee = get_col(df_cm, ['Total Weekly Fee', 'Weekly Fee', 'Fee'])

            cm_core = df_cm[df_cm['Charge Type Clean'].isin(['STAND', 'DIRECT MANAGEMENT', 'DIRECT MANAGEMENT ON SITE'])].groupby('SUID_Clean').agg({
                rep_hrs: 'sum' if rep_hrs else lambda x: 0,
                w_fee: 'sum' if w_fee else lambda x: 0
            }).rename(columns={rep_hrs: 'CM Core Hours', w_fee: 'CM Core Weekly Rate'})

            cm_1to1 = df_cm[df_cm['Charge Type Clean'].isin(['1TO1', 'PC', 'PERSONAL CARE'])].groupby('SUID_Clean').agg({
                rep_hrs: 'sum' if rep_hrs else lambda x: 0,
                w_fee: 'sum' if w_fee else lambda x: 0
            }).rename(columns={rep_hrs: 'CM 1to1 Hours', w_fee: 'CM 1to1 Weekly Rate'})

            # --- EOPS CALCULATIONS ---
            core_h = get_col(df_eops, ['Core Hours'])
            dm_h = get_col(df_eops, ['Direct Management On Site Hours'])
            core_c = get_col(df_eops, ['Core Weekly Charges'])
            dm_c = get_col(df_eops, ['Direct Management On Site Weekly Charges'])
            one_h = get_col(df_eops, ['Total 1:1 + PC Hours', '1to1 Hours'])
            one_c = get_col(df_eops, ['Total 1:1 Weekly Charges', '1to1 Charges'])

            df_eops['EOPS Core Hours'] = (df_eops[core_h].fillna(0) if core_h else 0) + (df_eops[dm_h].fillna(0) if dm_h else 0)
            df_eops['EOPS Core Weekly Rate'] = (df_eops[core_c].fillna(0) if core_c else 0) + (df_eops[dm_c].fillna(0) if dm_c else 0)
            df_eops['EOPS 1to1 Hours'] = df_eops[one_h].fillna(0) if one_h else 0
            df_eops['EOPS 1to1 Weekly Rate'] = df_eops[one_c].fillna(0) if one_c else 0

            eops_calc = df_eops.groupby('SUID_Clean').agg({
                'EOPS Core Hours': 'sum',
                'EOPS Core Weekly Rate': 'sum',
                'EOPS 1to1 Hours': 'sum',
                'EOPS 1to1 Weekly Rate': 'sum'
            }).reset_index()

            # --- MERGE ALL RECON DATA ---
            recon = pd.merge(eops_base, cm_core, on='SUID_Clean', how='left')
            recon = pd.merge(recon, cm_1to1, on='SUID_Clean', how='left')
            recon = pd.merge(recon, eops_calc, on='SUID_Clean', how='left').fillna(0)

            # Differences
            recon['Core Hours Difference'] = recon['CM Core Hours'] - recon['EOPS Core Hours']
            recon['1to1 Hours Difference'] = recon['CM 1to1 Hours'] - recon['EOPS 1to1 Hours']
            recon['1to1 Weekly Rate Difference'] = recon['CM 1to1 Weekly Rate'] - recon['EOPS 1to1 Weekly Rate']
            
            recon['CM Total Weekly Rate'] = recon['CM Core Weekly Rate'] + recon['CM 1to1 Weekly Rate']
            recon['EOPS Total Weekly Rate'] = recon['EOPS Core Weekly Rate'] + recon['EOPS 1to1 Weekly Rate']
            recon['Total Rate Difference'] = recon['CM Total Weekly Rate'] - recon['EOPS Total Weekly Rate']

            recon_output = recon.rename(columns={
                'SUID_Clean': 'SUID',
                'Admission Date Clean': 'Admission Date',
                'Council Name': 'Funding Authority',
                'Property Address EOPS': 'Property'
            })

            final_recon = recon_output[[
                'SUID', 'SU Name', 'Admission Date', 'Funding Authority', 'Property',
                'CM Core Hours', 'EOPS Core Hours', 'Core Hours Difference',
                'CM Core Weekly Rate', 'EOPS Core Weekly Rate',
                'CM 1to1 Hours', 'EOPS 1to1 Hours', '1to1 Hours Difference',
                'CM 1to1 Weekly Rate', 'EOPS 1to1 Weekly Rate', '1to1 Weekly Rate Difference',
                'CM Total Weekly Rate', 'EOPS Total Weekly Rate', 'Total Rate Difference'
            ]]

            # --- PROPERTY DASHBOARD MASTER DATA ---
            property_detail_df = recon_output[[
                'SUID', 'SU Name', 'Funding Authority', 'Property', 'EOPS Core Hours', 'EOPS 1to1 Hours'
            ]].copy()
            
            property_detail_df.rename(columns={
                'EOPS Core Hours': 'Core Hours',
                'EOPS 1to1 Hours': '1to1 Hours'
            }, inplace=True)

            property_detail_df['Total Hours'] = property_detail_df['Core Hours'] + property_detail_df['1to1 Hours']

            # Session State
            st.session_state.processed = True
            st.session_state.final_recon = final_recon
            st.session_state.property_detail_df = property_detail_df

# Routing according to Sidebar Tab
if st.session_state.get("processed", False):
    final_recon = st.session_state.final_recon
    property_detail_df = st.session_state.property_detail_df

    if navigation_page == "📋 Care Master vs EOPS Reconciliation":
        st.subheader("📋 Split-Funded Care Master vs EOPS Reconciliation Table")
        st.dataframe(final_recon, use_container_width=True)

    elif navigation_page == "🏠 Property Dashboard":
        st.subheader("🏠 Property Dynamic Dashboard")

        FIXED_TOTAL_BEDS = 539
        total_occupied_su = property_detail_df['SUID'].nunique()
        vacancies_diff = FIXED_TOTAL_BEDS - total_occupied_su

        m1, m2, m3, m4, m5, m6 = st.columns(6)
        m1.metric("Total Beds", f"{FIXED_TOTAL_BEDS:,}")
        m2.metric("Occupied Beds (EOPS)", f"{total_occupied_su:,}")
        m3.metric("Vacancies Difference", f"{vacancies_diff:,}")
        m4.metric("EOPS Core Hours", f"{property_detail_df['Core Hours'].sum():,.2f}")
        m5.metric("EOPS 1to1 Hours", f"{property_detail_df['1to1 Hours'].sum():,.2f}")
        m6.metric("Total EOPS Hours", f"{property_detail_df['Total Hours'].sum():,.2f}")

        st.markdown("---")

        unique_props = [str(p).strip() for p in property_detail_df['Property'].dropna().unique() if str(p).strip() != ""]
        property_options = ["All Properties"] + sorted(list(set(unique_props)))

        st.subheader("🔍 Property Search & Dynamic Slicer")
        selected_property = st.selectbox("Search or Select Property to Inspect:", property_options)

        if selected_property != "All Properties":
            filtered_dashboard_df = property_detail_df[property_detail_df['Property'].astype(str) == selected_property]
        else:
            filtered_dashboard_df = property_detail_df

        st.subheader("📈 Hours Breakdown Chart")
        chart_data = filtered_dashboard_df.groupby('Property')[['Core Hours', '1to1 Hours', 'Total Hours']].sum()
        st.bar_chart(chart_data)

        st.markdown("---")

        st.subheader(f"📋 Service User Details - [{selected_property}]")
        display_cols = ['SUID', 'SU Name', 'Funding Authority', 'Property', 'Core Hours', '1to1 Hours', 'Total Hours']
        st.dataframe(filtered_dashboard_df[display_cols], use_container_width=True)

    # Download Excel Report
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        final_recon.to_excel(writer, sheet_name='Reconciliation', index=False)
        property_detail_df.to_excel(writer, sheet_name='Property Dashboard', index=False)

    st.sidebar.markdown("---")
    st.sidebar.download_button(
        label="📥 Download Excel Report",
        data=buffer.getvalue(),
        file_name="SU_Reconciliation_And_Property_Dashboard.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )
