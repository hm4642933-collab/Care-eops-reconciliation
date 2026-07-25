import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="Care Master vs EOPS Reconciler", layout="wide")

# ==================== 1. LOGIN SYSTEM ====================
USERNAME = "admin"
PASSWORD = "password123"

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🔒 Portal Login")
    u = st.text_input("Username")
    p = st.text_input("Password", type="password")
    if st.button("Log In"):
        if u == USERNAME and p == PASSWORD:
            st.session_state.logged_in = True
            st.rerun()
        else:
            st.error("❌ Galat Username ya Password")
    st.stop()

if st.sidebar.button("🚪 Log Out"):
    st.session_state.logged_in = False
    st.rerun()

# ==================== 2. MAIN RECONCILIATION APP ====================
st.title("📊 Hours & Rates Reconciliation Portal")
st.write("Care Master aur EOPS ki files upload karke Clean Consolidated Report download karein.")

col1, col2 = st.columns(2)
with col1:
    cm_file = st.file_uploader("Care Master File Upload Karein", type=["xlsx", "xls"])
with col2:
    eops_file = st.file_uploader("EOPS File Upload Karein", type=["xlsx", "xls"])

if cm_file and eops_file:
    if st.button("🚀 Generate Reconciled Report"):
        with st.spinner("Data Process ho raha hai..."):
            df_cm = pd.read_excel(cm_file)
            df_eops = pd.read_excel(eops_file)
            
            # Clean Column Names
            df_cm.columns = [str(c).strip() for c in df_cm.columns]
            df_eops.columns = [str(c).strip() for c in df_eops.columns]
            
            # Filter Block rows from Care Master
            df_cm = df_cm[~df_cm['Resident Ref'].astype(str).str.startswith(('BLOCK', 'Block', 'BLK'), na=False)].copy()
            df_cm['SUID_Clean'] = df_cm['Resident Ref'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
            
            # Care Master Aggregation (Standard vs 1-to-1)
            cm_stand = df_cm[df_cm['Charge Type'].astype(str).str.upper() == 'STAND'].groupby('SUID_Clean').agg({
                'Report Hours': 'sum',
                'Total Weekly Fee': 'sum'
            }).rename(columns={'Report Hours': 'CM Standard Hours', 'Total Weekly Fee': 'CM Standard Weekly Rate'})
            
            cm_1to1 = df_cm[df_cm['Charge Type'].astype(str).str.upper() == '1TO1'].groupby('SUID_Clean').agg({
                'Report Hours': 'sum',
                'Total Weekly Fee': 'sum'
            }).rename(columns={'Report Hours': 'CM 1to1 Hours', 'Total Weekly Fee': 'CM 1to1 Weekly Rate'})
            
            cm_info = df_cm.groupby('SUID_Clean').agg({
                'Resident Name': 'first',
                'Inv Period Description': lambda x: ', '.join(set(str(v) for v in x if pd.notna(v)))
            }).rename(columns={'Resident Name': 'CM Resident Name', 'Inv Period Description': 'CM Funding'})
            
            cm_summary = cm_info.join(cm_stand, how='left').join(cm_1to1, how='left').fillna(0).reset_index()
            
            # EOPS Processing & Calculations
            df_eops['SUID_Clean'] = df_eops['SUID'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
            df_eops['EOPS Full Name'] = df_eops['Service User Name'].fillna('') + ' ' + df_eops['SU Surname'].fillna('')
            
            # Standard Hours = Core Hours + Direct Management On Site Hours
            df_eops['EOPS Standard Hours'] = df_eops['Core Hours'].fillna(0) + df_eops['Direct Management On Site Hours'].fillna(0)
            df_eops['EOPS Standard Weekly Rate'] = df_eops['Core Weekly Charges'].fillna(0) + df_eops['Direct Management On Site Weekly Charges'].fillna(0)
            
            # 1 to 1 Hours = Total 1:1 + PC Hours
            df_eops['EOPS 1to1 Hours'] = df_eops['Total 1:1 + PC Hours'].fillna(0)
            df_eops['EOPS 1to1 Weekly Rate'] = df_eops['Total 1:1 Weekly Charges'].fillna(0)
            
            eops_summary = df_eops.groupby('SUID_Clean').agg({
                'EOPS Full Name': 'first',
                'FundingAuthority': lambda x: ', '.join(set(str(v) for v in x if pd.notna(v))),
                'EOPS Standard Hours': 'sum',
                'EOPS Standard Weekly Rate': 'sum',
                'EOPS 1to1 Hours': 'sum',
                'EOPS 1to1 Weekly Rate': 'sum'
            }).rename(columns={'FundingAuthority': 'EOPS Funding'}).reset_index()
            
            # Merging Data
            merged = pd.merge(cm_summary, eops_summary, on='SUID_Clean', how='outer')
            
            # Single Combined Columns for Info (No Duplicates)
            merged['SU ID'] = merged['SUID_Clean']
            merged['Service User Name'] = merged['CM Resident Name'].combine_first(merged['EOPS Full Name'])
            merged['Funding Authority'] = merged['CM Funding'].combine_first(merged['EOPS Funding'])
            
            # Numeric Columns Clean & Difference Logic
            num_cols = ['CM Standard Hours', 'EOPS Standard Hours', 'CM Standard Weekly Rate', 'EOPS Standard Weekly Rate',
                        'CM 1to1 Hours', 'EOPS 1to1 Hours', 'CM 1to1 Weekly Rate', 'EOPS 1to1 Weekly Rate']
            merged[num_cols] = merged[num_cols].fillna(0)
            
            merged['Standard Hours Diff'] = merged['CM Standard Hours'] - merged['EOPS Standard Hours']
            merged['Standard Rate Diff'] = merged['CM Standard Weekly Rate'] - merged['EOPS Standard Weekly Rate']
            merged['1to1 Hours Diff'] = merged['CM 1to1 Hours'] - merged['EOPS 1to1 Hours']
            merged['1to1 Rate Diff'] = merged['CM 1to1 Weekly Rate'] - merged['EOPS 1to1 Weekly Rate']
            
            # Final Clean Columns Structure
            final_columns = [
                'SU ID', 'Service User Name', 'Funding Authority',
                'CM Standard Hours', 'EOPS Standard Hours', 'Standard Hours Diff',
                'CM Standard Weekly Rate', 'EOPS Standard Weekly Rate', 'Standard Rate Diff',
                'CM 1to1 Hours', 'EOPS 1to1 Hours', '1to1 Hours Diff',
                'CM 1to1 Weekly Rate', 'EOPS 1to1 Weekly Rate', '1to1 Rate Diff'
            ]
            
            final_df = merged[final_columns].copy()
            
            # Excel Generation
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                final_df.to_excel(writer, sheet_name='Full Reconciliation', index=False)
                
                # Hours Mismatches
                hours_diff = final_df[(final_df['Standard Hours Diff'].abs() >= 0.01) | (final_df['1to1 Hours Diff'].abs() >= 0.01)]
                hours_diff.to_excel(writer, sheet_name='Hours Mismatches', index=False)
                
                # Rate Mismatches
                rate_diff = final_df[(final_df['Standard Rate Diff'].abs() >= 0.01) | (final_df['1to1 Rate Diff'].abs() >= 0.01)]
                rate_diff.to_excel(writer, sheet_name='Rate Mismatches', index=False)
            
            st.success("✅ Reconciliation Report Successfully Generated!")
            st.download_button(
                label="📥 Download Clean Excel Report",
                data=buffer.getvalue(),
                file_name="Reconciliation_Report.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
