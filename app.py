import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="SU Reconciliation & Dynamic Property Dashboard", layout="wide")

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

if st.sidebar.button("🚪 Log Out"):
    st.session_state.logged_in = False
    st.rerun()

# ==================== 2. MAIN APPLICATION ====================
st.title("📊 Care Master vs EOPS Reconciliation & Dynamic Property Dashboard")

col1, col2 = st.columns(2)
with col1:
    cm_file = st.file_uploader("Upload Care Master File (.xlsx)", type=["xlsx", "xls"])
with col2:
    eops_file = st.file_uploader("Upload EOPS File (.xlsx)", type=["xlsx", "xls"])

if cm_file and eops_file:
    if st.button("🚀 Process Reconciliation & Dashboard"):
        with st.spinner("Processing Data..."):
            
            # --- LOAD DATASETS ---
            df_cm = pd.read_excel(cm_file)
            df_eops = pd.read_excel(eops_file)

            # Clean Headers
            df_cm.columns = [str(c).strip() for c in df_cm.columns]
            df_eops.columns = [str(c).strip() for c in df_eops.columns]
            
            # SUID Normalization
            df_cm['SUID_Clean'] = df_cm['Resident Ref'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
            df_eops['SUID_Clean'] = df_eops['SUID'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
            
            # Clean Charge Types
            df_cm['Charge Type Clean'] = df_cm['Charge Type'].astype(str).str.strip().str.upper() if 'Charge Type' in df_cm.columns else ""
            df_cm = df_cm[~df_cm['Resident Ref'].astype(str).str.startswith(('BLOCK', 'Block', 'BLK'), na=False)].copy()
            
            # Admission Date
            if 'Admission Date' in df_cm.columns:
                df_cm['Admission Date Clean'] = pd.to_datetime(df_cm['Admission Date'], errors='coerce').dt.strftime('%d/%m/%Y')
            else:
                df_cm['Admission Date Clean'] = "N/A"

            # EOPS Base Columns (Mandatory mapped fields)
            df_eops['EOPS Full Name'] = df_eops['Service User Name'].fillna('') + ' ' + df_eops['SU Surname'].fillna('')
            df_eops['EOPS FundingAuthority'] = df_eops['FundingAuthority'].astype(str).str.strip()
            df_eops['EOPS Property'] = df_eops['Property'].astype(str).str.strip()
            
            eops_base = df_eops.groupby('SUID_Clean').agg({
                'EOPS Full Name': 'first',
                'EOPS FundingAuthority': 'first',
                'EOPS Property': 'first'
            }).reset_index()

            cm_dates = df_cm.groupby('SUID_Clean')['Admission Date Clean'].first().to_dict()
            eops_base['Admission Date'] = eops_base['SUID_Clean'].map(cm_dates).fillna("N/A")

            # --- CM CALCULATIONS (Core includes Direct Management, 1to1 includes PC) ---
            cm_core = df_cm[df_cm['Charge Type Clean'].isin(['STAND', 'DIRECT MANAGEMENT', 'DIRECT MANAGEMENT ON SITE'])].groupby('SUID_Clean').agg({
                'Report Hours': 'sum',
                'Total Weekly Fee': 'sum'
            }).rename(columns={'Report Hours': 'CM Core Hours', 'Total Weekly Fee': 'CM Core Weekly Rate'})

            cm_1to1 = df_cm[df_cm['Charge Type Clean'].isin(['1TO1', 'PC', 'PERSONAL CARE'])].groupby('SUID_Clean').agg({
                'Report Hours': 'sum',
                'Total Weekly Fee': 'sum'
            }).rename(columns={'Report Hours': 'CM 1to1 Hours', 'Total Weekly Fee': 'CM 1to1 Weekly Rate'})

            # --- EOPS CALCULATIONS ---
            df_eops['EOPS Core Hours'] = df_eops['Core Hours'].fillna(0) + df_eops['Direct Management On Site Hours'].fillna(0)
            df_eops['EOPS Core Weekly Rate'] = df_eops['Core Weekly Charges'].fillna(0) + df_eops['Direct Management On Site Weekly Charges'].fillna(0)
            df_eops['EOPS 1to1 Hours'] = df_eops['Total 1:1 + PC Hours'].fillna(0)
            df_eops['EOPS 1to1 Weekly Rate'] = df_eops['Total 1:1 Weekly Charges'].fillna(0)

            eops_calc = df_eops.groupby('SUID_Clean').agg({
                'EOPS Core Hours': 'sum',
                'EOPS Core Weekly Rate': 'sum',
                'EOPS 1to1 Hours': 'sum',
                'EOPS 1to1 Weekly Rate': 'sum'
            }).reset_index()

            # --- MERGE RECON DATA ---
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
                'EOPS Full Name': 'SU Name',
                'EOPS FundingAuthority': 'Funding Authority',
                'EOPS Property': 'Property'
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

            # Total Hours Calculation
            property_detail_df['Total Hours'] = property_detail_df['Core Hours'] + property_detail_df['1to1 Hours']

            # --- RENDER TABS ---
            tab1, tab2 = st.tabs(["📊 Care Master vs EOPS Reconciliation", "🏠 Property Dashboard"])

            with tab1:
                st.subheader("Split-Funded Care Master vs EOPS Reconciliation Table")
                st.dataframe(final_recon, use_container_width=True)

            with tab2:
                st.subheader("🏠 Property Dynamic Dashboard & SUID Breakdown")

                # PROPERTY SLICER / DROPDOWN
                property_options = ["All Properties"] + sorted(list(property_detail_df['Property'].dropna().unique()))
                selected_property = st.selectbox("📌 Select Property Address to filter Dashboard Data:", property_options)

                # Filter Dataset Based on Selected Property
                if selected_property != "All Properties":
                    filtered_dashboard_df = property_detail_df[property_detail_df['Property'] == selected_property]
                else:
                    filtered_dashboard_df = property_detail_df

                # KPI Calculations
                FIXED_TOTAL_BEDS = 539
                occupied_beds = filtered_dashboard_df['SUID'].nunique()
                vacancies = FIXED_TOTAL_BEDS - occupied_beds
                vacancies_diff = vacancies  # Difference

                # METRICS DISPLAY
                m1, m2, m3, m4, m5, m6 = st.columns(6)
                m1.metric("Total Beds", f"{FIXED_TOTAL_BEDS:,}")
                m2.metric("Occupied Beds", f"{occupied_beds:,}")
                m3.metric("Vacancies", f"{vacancies:,}")
                m4.metric("Vacancies Difference", f"{vacancies_diff:,}")
                m5.metric("Total Core Hours", f"{filtered_dashboard_df['Core Hours'].sum():,.2f}")
                m6.metric("Total 1to1 Hours", f"{filtered_dashboard_df['1to1 Hours'].sum():,.2f}")

                st.markdown("---")

                # DYNAMIC DATA TABLE (EXACT REQUESTED COLUMNS)
                st.subheader(f"📋 Service User Details - [{selected_property}]")
                st.write("Columns: **SUID | SU Name | Funding Authority | Property | Core Hours | 1to1 Hours | Total Hours**")
                
                # Column Display Order
                display_cols = ['SUID', 'SU Name', 'Funding Authority', 'Property', 'Core Hours', '1to1 Hours', 'Total Hours']
                st.dataframe(filtered_dashboard_df[display_cols], use_container_width=True)

            # --- EXCEL DOWNLOAD ---
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                final_recon.to_excel(writer, sheet_name='Reconciliation', index=False)
                property_detail_df.to_excel(writer, sheet_name='Property Dashboard', index=False)

            st.download_button(
                label="📥 Download Updated Reconciliation & Dashboard Excel Report",
                data=buffer.getvalue(),
                file_name="SU_Reconciliation_And_Property_Dashboard.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
