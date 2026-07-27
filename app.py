import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="Care Master vs EOPS Reconciler & Dashboard", layout="wide")

# ==================== 1. LOGIN SYSTEM ====================
USERNAME = "admin"
PASSWORD = "password123"

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🔒 Portal Access Login")
    st.write("Please enter your credentials to access the Reconciliation Portal.")
    
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
            st.error("❌ Invalid Username or Password")
    st.stop()

if st.sidebar.button("🚪 Log Out"):
    st.session_state.logged_in = False
    st.rerun()

# ==================== 2. MAIN APPLICATION ====================
st.title("📊 Care Master vs EOPS Reconciliation & Property Dashboard")
st.write("Upload Care Master and EOPS Excel files to perform split-funding reconciliation and generate property analytics.")

col1, col2 = st.columns(2)
with col1:
    cm_file = st.file_uploader("Upload Care Master File", type=["xlsx", "xls"])
with col2:
    eops_file = st.file_uploader("Upload EOPS File", type=["xlsx", "xls"])

if cm_file and eops_file:
    if st.button("🚀 Process & Generate Reconciliation Report"):
        with st.spinner("Processing split-funded clients and property data..."):
            
            # --- Load Files ---
            df_cm = pd.read_excel(cm_file)
            df_eops = pd.read_excel(eops_file)
            
            # Clean Headers
            df_cm.columns = [str(c).strip() for c in df_cm.columns]
            df_eops.columns = [str(c).strip() for c in df_eops.columns]
            
            # Clean Charge Types & Key Identifiers
            if 'Charge Type' in df_cm.columns:
                df_cm['Charge Type Clean'] = df_cm['Charge Type'].astype(str).str.strip().str.upper()
            else:
                df_cm['Charge Type Clean'] = ""
                
            df_cm = df_cm[~df_cm['Resident Ref'].astype(str).str.startswith(('BLOCK', 'Block', 'BLK'), na=False)].copy()
            df_cm['SUID_Clean'] = df_cm['Resident Ref'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
            df_cm['Funding_Clean'] = df_cm['Inv Period Description'].astype(str).str.strip()
            
            df_eops['SUID_Clean'] = df_eops['SUID'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
            df_eops['Funding_Clean'] = df_eops['FundingAuthority'].astype(str).str.strip()
            df_eops['EOPS Full Name'] = df_eops['Service User Name'].fillna('') + ' ' + df_eops['SU Surname'].fillna('')
            
            # Filter Housing Benefits (HB) & Tenant Charges (TC) from Care Master Care calculations
            df_cm_care = df_cm[~df_cm['Charge Type Clean'].isin(['HB', 'TC'])].copy()
            
            # Care Master Aggregation by [SU ID, Funding Authority] (STAND -> Core)
            cm_grouped = df_cm_care.groupby(['SUID_Clean', 'Funding_Clean']).agg({
                'Resident Name': 'first',
                'Report Hours': 'sum',
                'Total Weekly Fee': 'sum'
            }).reset_index()
            
            cm_core = df_cm_care[df_cm_care['Charge Type Clean'] == 'STAND'].groupby(['SUID_Clean', 'Funding_Clean']).agg({
                'Report Hours': 'sum',
                'Total Weekly Fee': 'sum'
            }).rename(columns={'Report Hours': 'CM Core Hours', 'Total Weekly Fee': 'CM Core Weekly Rate'})
            
            cm_1to1 = df_cm_care[df_cm_care['Charge Type Clean'] == '1TO1'].groupby(['SUID_Clean', 'Funding_Clean']).agg({
                'Report Hours': 'sum',
                'Total Weekly Fee': 'sum'
            }).rename(columns={'Report Hours': 'CM 1to1 Hours', 'Total Weekly Fee': 'CM 1to1 Weekly Rate'})
            
            cm_split = pd.merge(cm_grouped[['SUID_Clean', 'Funding_Clean', 'Resident Name']], cm_core, on=['SUID_Clean', 'Funding_Clean'], how='left')
            cm_split = pd.merge(cm_split, cm_1to1, on=['SUID_Clean', 'Funding_Clean'], how='left').fillna(0)
            
            # EOPS Aggregation by [SU ID, Funding Authority]
            df_eops['EOPS Core Hours'] = df_eops['Core Hours'].fillna(0) + df_eops['Direct Management On Site Hours'].fillna(0)
            df_eops['EOPS Core Weekly Rate'] = df_eops['Core Weekly Charges'].fillna(0) + df_eops['Direct Management On Site Weekly Charges'].fillna(0)
            df_eops['EOPS 1to1 Hours'] = df_eops['Total 1:1 + PC Hours'].fillna(0)
            df_eops['EOPS 1to1 Weekly Rate'] = df_eops['Total 1:1 Weekly Charges'].fillna(0)
            
            eops_split = df_eops.groupby(['SUID_Clean', 'Funding_Clean']).agg({
                'EOPS Full Name': 'first',
                'Property': 'first',
                'EOPS Core Hours': 'sum',
                'EOPS Core Weekly Rate': 'sum',
                'EOPS 1to1 Hours': 'sum',
                'EOPS 1to1 Weekly Rate': 'sum'
            }).reset_index()
            
            # Merge Both Datasets by [SU ID, Funding Authority]
            merged = pd.merge(cm_split, eops_split, on=['SUID_Clean', 'Funding_Clean'], how='outer')
            
            # Header Identifiers
            merged['SU ID'] = merged['SUID_Clean']
            merged['Service User Name'] = merged['Resident Name'].combine_first(merged['EOPS Full Name'])
            merged['Funding Authority'] = merged['Funding_Clean']
            
            # Fill NaNs for Numerical Columns
            num_cols = ['CM Core Hours', 'CM Core Weekly Rate', 'CM 1to1 Hours', 'CM 1to1 Weekly Rate',
                        'EOPS Core Hours', 'EOPS Core Weekly Rate', 'EOPS 1to1 Hours', 'EOPS 1to1 Weekly Rate']
            merged[num_cols] = merged[num_cols].fillna(0)
            
            # Compute Totals at the End
            merged['CM Total Hours'] = merged['CM Core Hours'] + merged['CM 1to1 Hours']
            merged['EOPS Total Hours'] = merged['EOPS Core Hours'] + merged['EOPS 1to1 Hours']
            merged['Total Hours Diff'] = merged['CM Total Hours'] - merged['EOPS Total Hours']
            
            merged['CM Total Weekly Rate'] = merged['CM Core Weekly Rate'] + merged['CM 1to1 Weekly Rate']
            merged['EOPS Total Weekly Rate'] = merged['EOPS Core Weekly Rate'] + merged['EOPS 1to1 Weekly Rate']
            merged['Total Rate Diff'] = merged['CM Total Weekly Rate'] - merged['EOPS Total Weekly Rate']
            
            # Reorder Final Output Columns
            final_columns = [
                'SU ID', 'Service User Name', 'Funding Authority', 'Property',
                'CM Core Hours', 'EOPS Core Hours', 
                'CM Core Weekly Rate', 'EOPS Core Weekly Rate',
                'CM 1to1 Hours', 'EOPS 1to1 Hours', 
                'CM 1to1 Weekly Rate', 'EOPS 1to1 Weekly Rate',
                'CM Total Hours', 'EOPS Total Hours', 'Total Hours Diff',
                'CM Total Weekly Rate', 'EOPS Total Weekly Rate', 'Total Rate Diff'
            ]
            
            final_recon = merged[final_columns].sort_values(by=['Funding Authority', 'Service User Name']).copy()
            
            # --- PROPERTY DASHBOARD COMPUTATION (FIXED KEYERROR) ---
            property_df = df_eops.groupby('Property').agg({
                'EOPS Core Hours': 'sum',
                'EOPS 1to1 Hours': 'sum',
                'SUID_Clean': 'nunique'
            }).reset_index()
            
            # Standardize column headers
            property_df.columns = ['Property', 'Total Core Hours', 'Total 1:1 Hours', 'Occupied Beds']
            
            # Capacity and Vacancy calculations
            property_df['Total Beds Capacity'] = property_df['Occupied Beds'].apply(lambda x: max(x, 11))
            property_df['Vacant Beds'] = property_df['Total Beds Capacity'] - property_df['Occupied Beds']
            
            property_df = property_df[['Property', 'Total Core Hours', 'Total 1:1 Hours', 'Total Beds Capacity', 'Occupied Beds', 'Vacant Beds']]

            # --- DISPLAY DASHBOARD IN STREAMLIT ---
            tab1, tab2 = st.tabs(["📊 Split-Funding Reconciliation", "🏠 Property Dashboard"])
            
            with tab1:
                st.subheader("Split-Funded Client Reconciliation")
                st.dataframe(final_recon, use_container_width=True)
                
            with tab2:
                st.subheader("Property-by-Property Overview")
                st.dataframe(property_df, use_container_width=True)
            
            # --- EXCEL DOWNLOAD GENERATION ---
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                final_recon.to_excel(writer, sheet_name='Split Reconciliation', index=False)
                
                # Mismatches Sheet
                mismatches = final_recon[(final_recon['Total Hours Diff'].abs() >= 0.01) | (final_recon['Total Rate Diff'].abs() >= 0.01)]
                mismatches.to_excel(writer, sheet_name='Mismatches Only', index=False)
                
                # Property Summary Sheet
                property_df.to_excel(writer, sheet_name='Property Dashboard', index=False)
            
            st.success("✅ Reconciliation & Property Analytics Successfully Processed!")
            st.download_button(
                label="📥 Download Full Excel Report",
                data=buffer.getvalue(),
                file_name="Split_Funding_And_Property_Reconciliation.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
