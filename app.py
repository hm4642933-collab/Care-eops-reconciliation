import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="SU Reconciliation & Property Dashboard", layout="wide")

# ==================== 1. AUTHENTICATION (LOG IN / LOG OUT) ====================
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

# Logout Option in Sidebar
if st.sidebar.button("🚪 Log Out"):
    st.session_state.logged_in = False
    st.rerun()

# ==================== 2. MAIN APPLICATION ====================
st.title("📊 Care Master vs EOPS Reconciliation & Property Dashboard")

col1, col2, col3 = st.columns(3)
with col1:
    cm_file = st.file_uploader("Upload Care Master File (.xlsx)", type=["xlsx", "xls"])
with col2:
    eops_file = st.file_uploader("Upload EOPS File (.xlsx)", type=["xlsx", "xls"])
with col3:
    beds_file = st.file_uploader("Upload Total Beds File (.ods / .xlsx)", type=["ods", "xlsx", "xls"])

if cm_file and eops_file:
    if st.button("🚀 Process Reconciliation & Dashboard"):
        with st.spinner("Processing Data..."):
            
            # --- LOAD DATASETS ---
            df_cm = pd.read_excel(cm_file)
            df_eops = pd.read_excel(eops_file)
            
            # Load Total Beds File if provided
            if beds_file:
                try:
                    df_beds = pd.read_excel(beds_file)
                    df_beds.columns = [str(c).strip() for c in df_beds.columns]
                except Exception:
                    df_beds = pd.DataFrame()
            else:
                df_beds = pd.DataFrame()

            # Clean Headers
            df_cm.columns = [str(c).strip() for c in df_cm.columns]
            df_eops.columns = [str(c).strip() for c in df_eops.columns]
            
            # SUID Normalization
            df_cm['SUID_Clean'] = df_cm['Resident Ref'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
            df_eops['SUID_Clean'] = df_eops['SUID'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
            
            # Clean Charge Types
            df_cm['Charge Type Clean'] = df_cm['Charge Type'].astype(str).str.strip().str.upper() if 'Charge Type' in df_cm.columns else ""
            
            # Exclude Block bookings
            df_cm = df_cm[~df_cm['Resident Ref'].astype(str).str.startswith(('BLOCK', 'Block', 'BLK'), na=False)].copy()
            
            # Admission Date Formatting
            if 'Admission Date' in df_cm.columns:
                df_cm['Admission Date Clean'] = pd.to_datetime(df_cm['Admission Date'], errors='coerce').dt.strftime('%d/%m/%Y')
            else:
                df_cm['Admission Date Clean'] = "N/A"

            # EOPS Base Columns (All mandatory base data pulled from EOPS)
            df_eops['EOPS Full Name'] = df_eops['Service User Name'].fillna('') + ' ' + df_eops['SU Surname'].fillna('')
            df_eops['EOPS FundingAuthority'] = df_eops['FundingAuthority'].astype(str).str.strip()
            df_eops['EOPS Property'] = df_eops['Property'].astype(str).str.strip()
            
            eops_base = df_eops.groupby('SUID_Clean').agg({
                'EOPS Full Name': 'first',
                'EOPS FundingAuthority': 'first',
                'EOPS Property': 'first'
            }).reset_index()

            # Map Admission Date from CM to EOPS Base
            cm_dates = df_cm.groupby('SUID_Clean')['Admission Date Clean'].first().to_dict()
            eops_base['Admission Date'] = eops_base['SUID_Clean'].map(cm_dates).fillna("N/A")

            # --- CM CALCULATIONS (Direct & PC Included) ---
            # Core = STAND + Direct Management
            cm_core = df_cm[df_cm['Charge Type Clean'].isin(['STAND', 'DIRECT MANAGEMENT', 'DIRECT MANAGEMENT ON SITE'])].groupby('SUID_Clean').agg({
                'Report Hours': 'sum',
                'Total Weekly Fee': 'sum'
            }).rename(columns={'Report Hours': 'CM Core Hours', 'Total Weekly Fee': 'CM Core Weekly Rate'})

            # 1to1 = 1TO1 + PC
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

            # --- MERGE ALL RECON DATA ---
            recon = pd.merge(eops_base, cm_core, on='SUID_Clean', how='left')
            recon = pd.merge(recon, cm_1to1, on='SUID_Clean', how='left')
            recon = pd.merge(recon, eops_calc, on='SUID_Clean', how='left').fillna(0)

            # --- DIFFERENCE CALCULATIONS ---
            recon['Core Hours Difference'] = recon['CM Core Hours'] - recon['EOPS Core Hours']
            recon['1to1 Hours Difference'] = recon['CM 1to1 Hours'] - recon['EOPS 1to1 Hours']
            recon['1to1 Weekly Rate Difference'] = recon['CM 1to1 Weekly Rate'] - recon['EOPS 1to1 Weekly Rate']
            
            recon['CM Total Weekly Rate'] = recon['CM Core Weekly Rate'] + recon['CM 1to1 Weekly Rate']
            recon['EOPS Total Weekly Rate'] = recon['EOPS Core Weekly Rate'] + recon['EOPS 1to1 Weekly Rate']
            recon['Total Rate Difference'] = recon['CM Total Weekly Rate'] - recon['EOPS Total Weekly Rate']

            # Column Renaming for UI Output
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

            # --- PROPERTY DASHBOARD COMPUTATION ---
            prop_grp = df_eops.groupby('EOPS Property').agg({
                'SUID_Clean': 'nunique',
                'EOPS Core Hours': 'sum',
                'EOPS 1to1 Hours': 'sum'
            }).reset_index().rename(columns={
                'EOPS Property': 'Property',
                'SUID_Clean': 'Total Occupied',
                'EOPS Core Hours': 'Total Core Hours',
                'EOPS 1to1 Hours': 'Total 1to1 Hours'
            })

            # Integrate Total Beds File if Available
            if not df_beds.empty and 'Property' in df_beds.columns and 'Total Beds' in df_beds.columns:
                prop_grp = pd.merge(prop_grp, df_beds[['Property', 'Total Beds']], on='Property', how='left')
                prop_grp['Total Beds'] = prop_grp['Total Beds'].fillna(prop_grp['Total Occupied'])
            else:
                # Default capacity fallback
                prop_grp['Total Beds'] = prop_grp['Total Occupied'].apply(lambda x: max(x, 10))

            prop_grp['Total Vacancies'] = prop_grp['Total Beds'] - prop_grp['Total Occupied']
            prop_grp['Vacancies Difference'] = prop_grp['Total Vacancies'] # Customizable rule

            # --- RENDER INTERFACE (TABS) ---
            tab1, tab2 = st.tabs([" Care Master vs EOPS Reconciliation", "🏠 Property Dashboard"])

            with tab1:
                st.subheader("Split-Funded Care Master vs EOPS Reconciliation Table")
                st.dataframe(final_recon, use_container_width=True)

            with tab2:
                st.subheader("🏠 Property Capacity & Analytics Dashboard")

                # Top Key Metrics
                m1, m2, m3, m4, m5, m6 = st.columns(6)
                m1.metric("Total Beds", f"{prop_grp['Total Beds'].sum():,}")
                m2.metric("Total Occupied", f"{prop_grp['Total Occupied'].sum():,}")
                m3.metric("Total Vacancies", f"{prop_grp['Total Vacancies'].sum():,}")
                m4.metric("Vacancies Difference", f"{prop_grp['Vacancies Difference'].sum():,}")
                m5.metric("Total Core Hours", f"{prop_grp['Total Core Hours'].sum():,.2f}")
                m6.metric("Total 1to1 Hours", f"{prop_grp['Total 1to1 Hours'].sum():,.2f}")

                st.markdown("---")

                # --- SLICER (PROPERTY FILTER) ---
                st.subheader("🎛️ Property Interactive Slicer")
                property_list = ["All Properties"] + list(prop_grp['Property'].unique())
                selected_prop = st.selectbox("Select Property to Inspect:", property_list)

                if selected_prop != "All Properties":
                    filtered_prop = prop_grp[prop_grp['Property'] == selected_prop]
                    filtered_suids = recon_output[recon_output['Property'] == selected_prop][['SUID', 'SU Name', 'Funding Authority']]
                    
                    sc1, sc2, sc3, sc4 = st.columns(4)
                    sc1.metric("Selected Property", selected_prop)
                    sc2.metric("Total Beds", int(filtered_prop['Total Beds'].values[0]))
                    sc3.metric("Total Vacancies", int(filtered_prop['Total Vacancies'].values[0]))
                    sc4.metric("Vacancies Difference", int(filtered_prop['Vacancies Difference'].values[0]))
                    
                    st.write(f"**SUIDs registered under {selected_prop}:**")
                    st.dataframe(filtered_suids, use_container_width=True)
                else:
                    st.info("Select a specific property above to inspect individual SUIDs and bed availability.")

                st.markdown("---")
                st.subheader("📊 Core Hours vs 1:1 Hours Comparison Chart")
                st.bar_chart(prop_grp.set_index('Property')[['Total Core Hours', 'Total 1to1 Hours']])

                st.subheader("📋 Complete Property Master Table")
                st.dataframe(prop_grp, use_container_width=True)

            # --- EXCEL DOWNLOAD ---
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                final_recon.to_excel(writer, sheet_name='Reconciliation', index=False)
                prop_grp.to_excel(writer, sheet_name='Property Dashboard', index=False)

            st.download_button(
                label="📥 Download Updated Reconciliation & Property Excel Report",
                data=buffer.getvalue(),
                file_name="SU_Reconciliation_And_Property_Dashboard.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
