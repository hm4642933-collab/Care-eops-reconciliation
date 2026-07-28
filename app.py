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
    .stRadio > label {
        font-weight: bold;
        font-size: 16px;
    }
    </style>
""",
    unsafe_allow_html=True,
)

# ==================== 1. CONSTANTS ====================
TOTAL_FIXED_BEDS = 485  # Total Beds set to 485

# ==================== 2. AUTHENTICATION ====================
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

# ==================== 3. SIDEBAR NAVIGATION ====================
with st.sidebar:
  st.markdown("### 🏢 **Portal Menu**")

  if st.button("🚪 Log Out", use_container_width=True):
    st.session_state.logged_in = False
    st.rerun()

  st.markdown("---")

  navigation_page = st.radio(
      "Select Section / Tab:",
      ["📋 Care Master vs EOPS Reconciliation", "🏠 Property Dashboard"],
      index=0,
  )


# Helper function to clean SUID string
def clean_suid(series):
  return (
      series.astype(str)
      .str.strip()
      .str.replace(r"\.0$", "", regex=True)
      .str.upper()
      .replace(["NAN", "NONE", "<NA>", ""], pd.NA)
  )


# ==================== 4. MAIN APPLICATION ====================
st.title("📊 Care Master vs EOPS Reconciliation & Property Portal")

col1, col2 = st.columns(2)
with col1:
  cm_file = st.file_uploader(
      "Upload Care Master File (.xlsx)", type=["xlsx", "xls"]
  )
with col2:
  eops_file = st.file_uploader("Upload EOPS File (.xlsx)", type=["xlsx", "xls"])

if cm_file and eops_file:
  if st.button("🚀 Process Reconciliation & Dashboard", use_container_width=True):
    with st.spinner("Processing Data..."):

      # --- LOAD DATASETS ---
      df_cm = pd.read_excel(cm_file, dtype=str)
      df_eops = pd.read_excel(eops_file, dtype=str)

      # Clean Headers
      df_cm.columns = [str(c).strip() for c in df_cm.columns]
      df_eops.columns = [str(c).strip() for c in df_eops.columns]

      def get_col(df, possible_names):
        for name in possible_names:
          for col in df.columns:
            if col.lower().strip() == name.lower().strip():
              return col
        return None

      # 1. SUID Mapping (Strictly from EOPS for Base Master)
      eops_suid_col = get_col(
          df_eops, ['SUID', 'Resident Ref', 'SU Ref', 'Service User ID', 'Ref']
      )
      cm_suid_col = get_col(
          df_cm, ['Resident Ref', 'SUID', 'SU Ref', 'Service User ID', 'Ref']
      )

      if not eops_suid_col or not cm_suid_col:
        st.error(
            "❌ Error: SUID / Resident Ref column not found in EOPS or Care"
            " Master files."
        )
        st.stop()

      df_eops['SUID_Clean'] = clean_suid(df_eops[eops_suid_col])
      df_cm['SUID_Clean'] = clean_suid(df_cm[cm_suid_col])

      df_eops = df_eops.dropna(subset=['SUID_Clean']).copy()
      df_cm = df_cm.dropna(subset=['SUID_Clean']).copy()

      # 2. EOPS Mappings (SU Name, Admission Date, Property, Funding Authority)
      fn_eops = get_col(
          df_eops, ['Service User Name', 'SU Name', 'First Name']
      )
      sn_eops = get_col(df_eops, ['SU Surname', 'Surname', 'Last Name'])

      df_eops['EOPS_Name'] = (
          (df_eops[fn_eops].fillna('') if fn_eops else '')
          + ' '
          + (df_eops[sn_eops].fillna('') if sn_eops else '')
      ).str.strip()

      adm_eops = get_col(
          df_eops, ['Admission Date', 'Admit Date', 'Admission_Date']
      )
      df_eops['Admission Date Clean'] = (
          pd.to_datetime(df_eops[adm_eops], errors='coerce').dt.strftime(
              '%d/%m/%Y'
          )
          if adm_eops
          else 'N/A'
      )

      fa_col = get_col(
          df_eops,
          [
              'FundingAuthority',
              'Funding Authority',
              'Council Name',
              'LA Name',
              'Split Funding Council',
          ],
      )
      df_eops['Council Name'] = (
          df_eops[fa_col].astype(str).str.strip() if fa_col else 'N/A'
      )

      prop_eops = get_col(
          df_eops,
          ['Property', 'Property Address', 'Address', 'Property_Address'],
      )
      df_eops['Property Address EOPS'] = (
          df_eops[prop_eops].astype(str).str.strip() if prop_eops else 'N/A'
      )

      # Build Base Information strictly from EOPS
      base_info = (
          df_eops.groupby('SUID_Clean')
          .agg({
              'EOPS_Name': 'first',
              'Admission Date Clean': 'first',
              'Council Name': 'first',
              'Property Address EOPS': 'first',
          })
          .reset_index()
      )

      base_info.rename(
          columns={
              'EOPS_Name': 'SU Name',
              'Admission Date Clean': 'Admission Date',
              'Council Name': 'Funding Authority',
              'Property Address EOPS': 'Property',
          },
          inplace=True,
      )

      base_info['SU Name'] = base_info['SU Name'].replace('', 'N/A').fillna('N/A')
      base_info['Admission Date'] = base_info['Admission Date'].fillna('N/A')
      base_info['Funding Authority'] = base_info['Funding Authority'].fillna(
          'N/A'
      )
      base_info['Property'] = base_info['Property'].fillna('N/A')

      # --- CHARGE TYPE FILTERING & CM CALCULATIONS ---
      charge_col = get_col(df_cm, ['Charge Type'])
      df_cm['Charge Type Clean'] = (
          df_cm[charge_col].astype(str).str.strip().str.upper()
          if charge_col
          else ''
      )

      # Exclude TC, HB & Top Up lines
      df_cm = df_cm[
          ~df_cm['Charge Type Clean'].isin([
              'TC',
              'HB',
              'TENANT CONTRIBUTION',
              'HOUSING BENEFIT',
              'TOP UP',
              'TOPUP',
          ])
      ].copy()

      rep_hrs = get_col(df_cm, ['Report Hours', 'Hours'])
      w_fee = get_col(df_cm, ['Total Weekly Fee', 'Weekly Fee', 'Fee'])

      for col in [rep_hrs, w_fee]:
        if col:
          df_cm[col] = pd.to_numeric(df_cm[col], errors='coerce').fillna(0)

      # CORE ALLOWED TYPES
      cm_core = (
          df_cm[
              df_cm['Charge Type Clean'].isin([
                  'STAND',
                  'DIRECT MANAGEMENT',
                  'DIRECT MANAGEMENT ON SITE',
                  'CORE',
              ])
          ]
          .groupby('SUID_Clean')
          .agg({
              rep_hrs: 'sum' if rep_hrs else lambda x: 0,
              w_fee: 'sum' if w_fee else lambda x: 0,
          })
          .rename(
              columns={
                  rep_hrs: 'CM Core Hours',
                  w_fee: 'CM Core Weekly Rate',
              }
          )
      )

      # 1TO1 ALLOWED TYPES
      cm_1to1 = (
          df_cm[
              df_cm['Charge Type Clean'].isin(
                  ['1TO1', 'PC', 'PERSONAL CARE', '1:1']
              )
          ]
          .groupby('SUID_Clean')
          .agg({
              rep_hrs: 'sum' if rep_hrs else lambda x: 0,
              w_fee: 'sum' if w_fee else lambda x: 0,
          })
          .rename(
              columns={
                  rep_hrs: 'CM 1to1 Hours',
                  w_fee: 'CM 1to1 Weekly Rate',
              }
          )
      )

      # --- EOPS CALCULATIONS ---
      core_h = get_col(df_eops, ['Core Hours'])
      dm_h = get_col(df_eops, ['Direct Management On Site Hours'])
      core_c = get_col(df_eops, ['Core Weekly Charges'])
      dm_c = get_col(df_eops, ['Direct Management On Site Weekly Charges'])
      one_h = get_col(df_eops, ['Total 1:1 + PC Hours', '1to1 Hours'])
      one_c = get_col(df_eops, ['Total 1:1 Weekly Charges', '1to1 Charges'])

      for col in [core_h, dm_h, core_c, dm_c, one_h, one_c]:
        if col:
          df_eops[col] = pd.to_numeric(df_eops[col], errors='coerce').fillna(0)

      df_eops['EOPS Core Hours'] = (df_eops[core_h] if core_h else 0) + (
          df_eops[dm_h] if dm_h else 0
      )
      df_eops['EOPS Core Weekly Rate'] = (df_eops[core_c] if core_c else 0) + (
          df_eops[dm_c] if dm_c else 0
      )
      df_eops['EOPS 1to1 Hours'] = df_eops[one_h] if one_h else 0
      df_eops['EOPS 1to1 Weekly Rate'] = df_eops[one_c] if one_c else 0

      eops_calc = (
          df_eops.groupby('SUID_Clean')
          .agg({
              'EOPS Core Hours': 'sum',
              'EOPS Core Weekly Rate': 'sum',
              'EOPS 1to1 Hours': 'sum',
              'EOPS 1to1 Weekly Rate': 'sum',
          })
          .reset_index()
      )

      # --- MERGE ALL RECON DATA ---
      recon = pd.merge(base_info, cm_core, on='SUID_Clean', how='left')
      recon = pd.merge(recon, cm_1to1, on='SUID_Clean', how='left')
      recon = pd.merge(recon, eops_calc, on='SUID_Clean', how='left').fillna(0)

      # Differences
      recon['Core Hours Difference'] = (
          recon['CM Core Hours'] - recon['EOPS Core Hours']
      )
      recon['1to1 Hours Difference'] = (
          recon['CM 1to1 Hours'] - recon['EOPS 1to1 Hours']
      )
      recon['1to1 Weekly Rate Difference'] = (
          recon['CM 1to1 Weekly Rate'] - recon['EOPS 1to1 Weekly Rate']
      )

      recon['CM Total Weekly Rate'] = (
          recon['CM Core Weekly Rate'] + recon['CM 1to1 Weekly Rate']
      )
      recon['EOPS Total Weekly Rate'] = (
          recon['EOPS Core Weekly Rate'] + recon['EOPS 1to1 Weekly Rate']
      )
      recon['Total Rate Difference'] = (
          recon['CM Total Weekly Rate'] - recon['EOPS Total Weekly Rate']
      )

      recon_output = recon.rename(columns={'SUID_Clean': 'SUID'})

      final_recon = recon_output[[
          'SUID',
          'SU Name',
          'Admission Date',
          'Funding Authority',
          'Property',
          'CM Core Hours',
          'EOPS Core Hours',
          'Core Hours Difference',
          'CM Core Weekly Rate',
          'EOPS Core Weekly Rate',
          'CM 1to1 Hours',
          'EOPS 1to1 Hours',
          '1to1 Hours Difference',
          'CM 1to1 Weekly Rate',
          'EOPS 1to1 Weekly Rate',
          '1to1 Weekly Rate Difference',
          'CM Total Weekly Rate',
          'EOPS Total Weekly Rate',
          'Total Rate Difference',
      ]]

      # --- PROPERTY DASHBOARD MASTER DATA ---
      property_detail_df = recon_output[[
          'SUID',
          'SU Name',
          'Funding Authority',
          'Property',
          'EOPS Core Hours',
          'EOPS 1to1 Hours',
      ]].copy()

      property_detail_df.rename(
          columns={
              'EOPS Core Hours': 'Core Hours',
              'EOPS 1to1 Hours': '1to1 Hours',
          },
          inplace=True,
      )

      property_detail_df['Total Hours'] = (
          property_detail_df['Core Hours'] + property_detail_df['1to1 Hours']
      )

      st.session_state.processed = True
      st.session_state.final_recon = final_recon
      st.session_state.property_detail_df = property_detail_df

# Routing & Table Display
if st.session_state.get('processed', False):
  final_recon = st.session_state.final_recon
  property_detail_df = st.session_state.property_detail_df

  if navigation_page == '📋 Care Master vs EOPS Reconciliation':
    st.subheader('📋 Split-Funded Care Master vs EOPS Reconciliation Table')

    st.dataframe(
        final_recon,
        use_container_width=True,
        column_config={
            'SUID': st.column_config.TextColumn(
                'SUID', help='Full Service User ID', width='medium'
            ),
            'SU Name': st.column_config.TextColumn(
                'SU Name', help='Full Service User Name', width='large'
            ),
        },
    )

  elif navigation_page == '🏠 Property Dashboard':
    st.subheader('🏠 Property Dynamic Dashboard')

    # --- 1. TOP METRICS: FIXED 485 BEDS & VACANCY ANALYSIS ---
    st.markdown('### 🛏️ **Bed Occupancy & Vacancy Summary**')

    total_occupied_eops = property_detail_df['SUID'].nunique()
    total_vacant_beds = max(0, TOTAL_FIXED_BEDS - total_occupied_eops)
    overall_occupancy_pct = (total_occupied_eops / TOTAL_FIXED_BEDS) * 100

    b1, b2, b3, b4 = st.columns(4)
    b1.metric('🛏️ Total Beds (Fixed)', f'{TOTAL_FIXED_BEDS:,}')
    b2.metric('👥 Occupied Beds (EOPS)', f'{total_occupied_eops:,}')
    b3.metric(
        '🟢 Vacant Beds (Difference)',
        f'{total_vacant_beds:,}',
        delta=f'-{total_vacant_beds} Vacant',
        delta_color='inverse',
    )
    b4.metric('📊 Occupancy Rate', f'{overall_occupancy_pct:.1f}%')

    st.markdown('---')

    # --- 2. HOURS SUMMARY METRICS ---
    st.markdown('### ⏱️ **EOPS Hours Summary**')
    m1, m2, m3 = st.columns(3)
    m1.metric(
        ' Total Core Hours (EOPS)',
        f"{property_detail_df['Core Hours'].sum():,.2f}",
    )
    m2.metric(
        ' Total 1to1 Hours (EOPS)',
        f"{property_detail_df['1to1 Hours'].sum():,.2f}",
    )
    m3.metric(
        '📊 Grand Total Hours (EOPS)',
        f"{property_detail_df['Total Hours'].sum():,.2f}",
    )

    st.markdown('---')

    # --- 3. PROPERTY SEARCH & SLICER ---
    unique_props = [
        str(p).strip()
        for p in property_detail_df['Property'].dropna().unique()
        if str(p).strip() != '' and str(p).strip() != 'N/A'
    ]
    property_options = ['All Properties'] + sorted(list(set(unique_props)))

    st.subheader('🔍 Property Search & Slicer')
    selected_property = st.selectbox(
        'Search or Select Property:', property_options
    )

    if selected_property != 'All Properties':
      filtered_dashboard_df = property_detail_df[
          property_detail_df['Property'].astype(str) == selected_property
      ]
      prop_occupied = filtered_dashboard_df['SUID'].nunique()
      st.info(
          f'📌 **Selected Property:** {selected_property}  |  **👥 Occupied'
          f' Service Users (SUs):** {prop_occupied}'
      )
    else:
      filtered_dashboard_df = property_detail_df
      st.info(
          f'📌 **Selected:** All Properties  |  **🛏️ Total Beds:**'
          f' {TOTAL_FIXED_BEDS}  |  **👥 Total Occupied:** {total_occupied_eops}'
          f'  |  **🟢 Total Vacant:** {total_vacant_beds}'
      )

    # --- 4. CIRCLE GRAPH (DONUT CHART) ---
    col_chart, _ = st.columns([2, 1])
    with col_chart:
      core_sum = filtered_dashboard_df['Core Hours'].sum()
      one_to_one_sum = filtered_dashboard_df['1to1 Hours'].sum()

      chart_data = pd.DataFrame({
          'Hours Type': ['Core Hours', '1to1 Hours'],
          'Hours': [core_sum, one_to_one_sum],
      })

      fig_circle = px.pie(
          chart_data,
          values='Hours',
          names='Hours Type',
          hole=0.5,
          title=f'⭕ Core vs 1to1 Hours Ratio ({selected_property})',
          color_discrete_sequence=['#1f77b4', '#ff7f0e'],
      )
      st.plotly_chart(fig_circle, use_container_width=True)

    st.markdown('---')

    # --- 5. SERVICE USER DETAILS TABLE ---
    st.subheader(f'📋 Service User Details - [{selected_property}]')
    display_cols = [
        'SUID',
        'SU Name',
        'Funding Authority',
        'Property',
        'Core Hours',
        '1to1 Hours',
        'Total Hours',
    ]
    st.dataframe(
        filtered_dashboard_df[display_cols],
        use_container_width=True,
        column_config={
            'SUID': st.column_config.TextColumn(
                'SUID', help='Full Service User ID', width='medium'
            ),
            'SU Name': st.column_config.TextColumn(
                'SU Name', help='Full Service User Name', width='large'
            ),
        },
    )

  # Download Excel Report
  buffer = io.BytesIO()
  with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
    final_recon.to_excel(writer, sheet_name='Reconciliation', index=False)
    property_detail_df.to_excel(
        writer, sheet_name='Property Dashboard', index=False
    )

  st.sidebar.markdown('---')
  st.sidebar.download_button(
      label='📥 Download Excel Report',
      data=buffer.getvalue(),
      file_name='SU_Reconciliation_And_Property_Dashboard.xlsx',
      mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      use_container_width=True,
  )
