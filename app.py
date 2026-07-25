import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="Care Master vs EOPS Reconciler", layout="wide")

st.title("📊 Care Master vs EOPS Reconciliation Portal")
st.write("Dono Excel files upload karein aur 1-Click mein Detailed Reconciliation Report generate karein.")

col1, col2 = st.columns(2)

with col1:
    cm_file = st.file_uploader("Care Master File Upload Karein", type=["xlsx", "xls"])

with col2:
    eops_file = st.file_uploader("EOPS File Upload Karein", type=["xlsx", "xls"])

if cm_file and eops_file:
    if st.button("🚀 Generate Reconciliation Report"):
        with st.spinner("Data process ho raha hai..."):
            df_cm = pd.read_excel(cm_file)
            df_eops = pd.read_excel(eops_file)
            
            # Smart Column Detection for Funding/Council in Care Master
            cm_funding_col = None
            for col in ['Council', 'Funder', 'Funding Authority', 'Funding Body', 'Local Authority']:
                if col in df_cm.columns:
                    cm_funding_col = col
                    break
            
            # Clean IDs
            df_cm['Resident Ref Clean'] = df_cm['Resident Ref'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
            df_eops['SUID Clean'] = df_eops['SUID'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
            
            # Care Master side grouping
            cm_groupby_cols = ['Resident Ref Clean', 'Resident Name']
            if cm_funding_col:
                cm_groupby_cols.append(cm_funding_col)
                
            cm_summary = df_cm.groupby(cm_groupby_cols, as_index=False)['Total Weekly Fee'].sum()
            cm_summary.rename(columns={
                'Resident Ref Clean': 'Care Master Ref',
                'Total Weekly Fee': 'Care Master Weekly Rate'
            }, inplace=True)
            if cm_funding_col:
                cm_summary.rename(columns={cm_funding_col: 'Care Master Funding Authority'}, inplace=True)
            
            # Smart Column Detection for Funding/Council in EOPS
            eops_funding_col = None
            for col in ['Council', 'Funder Name', 'Funder', 'Funding Authority', 'Funding Body', 'Local Authority']:
                if col in df_eops.columns:
                    eops_funding_col = col
                    break
            
            # EOPS side grouping
            eops_groupby_cols = ['SUID Clean', 'Service User Name', 'SU Surname']
            if eops_funding_col:
                eops_groupby_cols.append(eops_funding_col)
                
            eops_summary = df_eops.groupby(eops_groupby_cols, as_index=False)['Total Weekly Charge (Excluding Agency)'].sum()
            eops_summary['Full Name'] = eops_summary['Service User Name'].fillna('') + ' ' + eops_summary['SU Surname'].fillna('')
            
            eops_summary.rename(columns={
                'SUID Clean': 'EOPS SUID',
                'Total Weekly Charge (Excluding Agency)': 'EOPS Weekly Rate'
            }, inplace=True)
            if eops_funding_col:
                eops_summary.rename(columns={eops_funding_col: 'EOPS Funding Authority'}, inplace=True)
                
            eops_summary = eops_summary.drop(columns=['Service User Name', 'SU Surname'])
            
            # Merging Data
            merged = pd.merge(cm_summary, eops_summary, left_on='Care Master Ref', right_on='EOPS SUID', how='outer')
            
            merged['Care Master Weekly Rate'] = merged['Care Master Weekly Rate'].fillna(0)
            merged['EOPS Weekly Rate'] = merged['EOPS Weekly Rate'].fillna(0)
            merged['Difference Rate'] = merged['Care Master Weekly Rate'] - merged['EOPS Weekly Rate']
            
            # Filtering Results
            mismatches = merged[(merged['Care Master Ref'].notna()) & (merged['EOPS SUID'].notna()) & (merged['Difference Rate'].abs() >= 0.01)]
            missing_in_eops = merged[merged['EOPS SUID'].isna()]
            missing_in_cm = merged[merged['Care Master Ref'].isna()]
            matches = merged[(merged['Care Master Ref'].notna()) & (merged['EOPS SUID'].notna()) & (merged['Difference Rate'].abs() < 0.01)]
            
            # Excel Buffer Generation
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                pd.DataFrame({
                    'Metric': ['Total Records Evaluated', 'Exact Matches', 'Amount Mismatches', 'Missing in EOPS', 'Missing in Care Master'],
                    'Count': [len(merged), len(matches), len(mismatches), len(missing_in_eops), len(missing_in_cm)]
                }).to_excel(writer, sheet_name='Summary', index=False)
                
                merged.to_excel(writer, sheet_name='Full Reconciliation', index=False)
                mismatches.to_excel(writer, sheet_name='Amount Mismatches', index=False)
                missing_in_eops.to_excel(writer, sheet_name='Missing in EOPS', index=False)
                missing_in_cm.to_excel(writer, sheet_name='Missing in Care Master', index=False)
            
            st.success("✅ Reconciliation Complete!")
            st.download_button(
                label="📥 Download Excel Reconciliation Report",
                data=buffer.getvalue(),
                file_name="Reconciliation_Report.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
