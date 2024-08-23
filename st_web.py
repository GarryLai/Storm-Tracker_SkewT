import matplotlib.gridspec as gridspec
import matplotlib.pyplot as plt
import pandas as pd
import metpy.calc as mpcalc
from metpy.plots import add_metpy_logo, Hodograph, SkewT
from metpy.units import units
import numpy as np
import os, sys
import streamlit as st
from io import StringIO

drop_periods = -10
drop_thres = 0.002

st.set_page_config(
	page_title='Storm Tracker Skew-T',
	page_icon=':balloon:',
	layout='wide'
)
st.title('Storm Tracker Skew-T')

pd.set_option('display.max_columns', None)

column = {
	'Time (UTC)': str,
	'Channel': int,
	'Data Count': int,
	'Temperature (0.01 deg C)': float,
	'Humidity (0.1 %)': float,
	'Pressure (Pa)': float,
	'Voltage (2.2/1023 v)': float,
	'Lonitude (0.00001 deg)': float,
	'Latitude (0.00001 deg)': float,
	'MSL Height (0.01m)': float,
	'GPS Sat': int,
	'RSSI (dB)': int,
	'FREQERR': int,
	'Unknown': int,
	'Speed (0.01 km/hr)': float,
	'SNR (dB)': int,
	'Direction (0.01 deg)': float,
	'Node Number': int
}

uploaded_file = st.file_uploader("Upload LoRa CSV file")
if uploaded_file:
	try:
		raw_data = pd.read_csv(uploaded_file, names=column.keys(), dtype=column, header=None, index_col=False)
	except:
		st.error('Unknown format! Use LoRa CSV file!')
		st.stop()
	#print('==> RAW_DATA\n', raw_data, '\n')
	
	option = st.selectbox(
		"Node Number",
		raw_data['Node Number'].apply(str).unique().tolist(),
	)
	node = int(option)
	
	proc_data = raw_data[raw_data['Node Number'] == node]
	proc_data = proc_data.drop(['Unknown'], axis=1)

	proc_data['Time (UTC)'] = pd.to_datetime(proc_data['Time (UTC)'])

	proc_data['Temperature (0.01 deg C)'] = proc_data['Temperature (0.01 deg C)'] * 0.01
	proc_data['Humidity (0.1 %)'] = proc_data['Humidity (0.1 %)'] * 0.1
	proc_data['Pressure (Pa)'] = proc_data['Pressure (Pa)'] * 0.01
	proc_data['Lonitude (0.00001 deg)'] = proc_data['Lonitude (0.00001 deg)'] * 0.00001
	proc_data['Latitude (0.00001 deg)'] = proc_data['Latitude (0.00001 deg)'] * 0.00001
	proc_data['MSL Height (0.01m)'] = proc_data['MSL Height (0.01m)'] * 0.01
	proc_data['Speed (0.01 km/hr)'] = proc_data['Speed (0.01 km/hr)'] * 0.01 * 0.539956803
	proc_data['Direction (0.01 deg)'] = proc_data['Direction (0.01 deg)'] * 0.01
	proc_data['Voltage (2.2/1023 v)'] = proc_data['Voltage (2.2/1023 v)'] / 1023 * 2.2

	proc_data = proc_data.rename({
		'Temperature (0.01 deg C)': 'Temperature (deg C)',
		'Humidity (0.1 %)': 'Humidity (%)',
		'Pressure (Pa)': 'Pressure (hPa)',
		'Lonitude (0.00001 deg)': 'Lonitude (deg)',
		'Latitude (0.00001 deg)': 'Latitude (deg)',
		'MSL Height (0.01m)': 'MSL Height (m)',
		'Speed (0.01 km/hr)': 'Speed (knots)',
		'Direction (0.01 deg)': 'Direction (deg)',
		'Voltage (2.2/1023 v)': 'Voltage (v)'
	}, axis='columns')
	
	proc_data['Pressure Difference (%)'] = proc_data['Pressure (hPa)'].pct_change(periods=drop_periods)

	#Remove dropping
	truncate_data = proc_data.truncate(after=proc_data['MSL Height (m)'].idxmax())
	
	#Remove ground
	try:
		truncate_data = truncate_data.truncate(before=truncate_data[truncate_data['Pressure Difference (%)'] >= drop_thres].index.values[0])
		#1==1
	except:
		st.error('Balloon no rise! Is ST on the ground?')
		st.stop()
		
	print('==> PROCESSED_DATA\n', truncate_data, '\n')
		
	display_data = truncate_data.copy()
	display_data = display_data.drop(columns=['Pressure Difference (%)'])
	display_data['Temperature (deg C)'] = display_data['Temperature (deg C)'].apply(lambda x: format(x, '.2f'))
	display_data['MSL Height (m)'] = display_data['MSL Height (m)'].apply(lambda x: format(x, '.2f'))
	display_data['Humidity (%)'] = display_data['Humidity (%)'].apply(lambda x: format(x, '.1f'))
	display_data['Direction (deg)'] = display_data['Direction (deg)'].apply(lambda x: format(x, '.2f'))
	display_data['Voltage (v)'] = display_data['Voltage (v)'].apply(lambda x: format(x, '.2f'))
	
	truncate_data = truncate_data.sort_values('Pressure (hPa)', ascending=False)

	#############################################################################################

	h = truncate_data['MSL Height (m)'].values * units.m
	p = truncate_data['Pressure (hPa)'].values * units.hPa
	T = truncate_data['Temperature (deg C)'].values * units.degC
	Td = mpcalc.dewpoint_from_relative_humidity(truncate_data['Temperature (deg C)'].values * units.degC, truncate_data['Humidity (%)'].values * units.percent)
	wind_speed = truncate_data['Speed (knots)'].values * units.knots
	wind_dir = truncate_data['Direction (deg)'].values * units.degrees
	u, v = mpcalc.wind_components(wind_speed, wind_dir)

	fig = plt.figure(figsize=(12, 9))

	gs = gridspec.GridSpec(3, 3)
	skew = SkewT(fig, rotation=45, subplot=gs[:, :2])

	prof = mpcalc.parcel_profile(p, T[0], Td[0]).to('degC')

	skew.plot(p, T, 'b')
	skew.plot(p, Td, 'r')
	skew.plot(p, prof, 'k')
	skew.plot_barbs(p[::100], u[::100], v[::100])

	skew.plot_dry_adiabats(lw=1, alpha=0.3)
	skew.plot_moist_adiabats(lw=1, alpha=0.3)
	skew.plot_mixing_lines(lw=1, alpha=0.3)
	skew.shade_cape(p, T, prof)
	skew.shade_cin(p, T, prof)

	skew.ax.set_xlim(-20, 40)
	skew.ax.set_ylim(1000, 200)
	plt.title(f'Storm Tracker #{node}\n{display_data["Time (UTC)"].iloc[0]}')

	lcl_p, lcl_t = mpcalc.lcl(p[0], T[0], Td[0])
	ccl_p, ccl_t, t_c = mpcalc.ccl(p, T, Td, prof)
	lfc_p, lfc_t = mpcalc.lfc(p, T, Td, prof)
	el_p, el_t = mpcalc.el(p, T, Td, prof)

	class A:
		pass
	try:
		cape, cin = mpcalc.cape_cin(p, T, Td, prof)
	except:
		cape = A()
		cape.magnitude = np.nan
		cin = A()
		cin.magnitude = np.nan
	k_idx = mpcalc.k_index(p, T, Td)
	parcel_p, parcel_t, parcel_td = mpcalc.mixed_parcel(p, T, Td, depth=500 * units.m, height=h)
	above = h > 500 * units.m
	press = np.concatenate([[parcel_p], p[above]])
	temp = np.concatenate([[parcel_t], T[above]])
	mixed_prof = mpcalc.parcel_profile(press, parcel_t, parcel_td)
	li = mpcalc.lifted_index(press, temp, mixed_prof)

	tt = mpcalc.total_totals_index(p, T, Td)

	plt.text(0.7, 0.6, f'''
P0= {round(p[0].magnitude, 1)} hPa
T0= {round(T[0].magnitude, 1)} °C
Td0= {round(Td[0].magnitude, 1)} °C

LCL= {round(lcl_p.magnitude, 1)} hPa ({round(lcl_t.magnitude, 1)} °C)
CCL= {round(ccl_p.magnitude, 1)} hPa ({round(ccl_t.magnitude, 1)} °C)
LFC= {round(lfc_p.magnitude, 1)} hPa ({round(lfc_t.magnitude, 1)} °C)
EL= {round(el_p.magnitude, 1)} hPa ({round(el_t.magnitude, 1)} °C)

Tc= {round(t_c.magnitude, 1)} °C
CAPE= {round(cape.magnitude, 1)} J/kg
CIN= {round(cin.magnitude, 1)} J/kg
K_INDEX= {round(k_idx.magnitude, 1)}
LI= {round(li.magnitude[0], 1)}
TOTAL= {round(tt.magnitude, 1)}''', transform=fig.transFigure, verticalalignment='top')

	ax = fig.add_subplot(gs[0, -1])
	h = Hodograph(ax, component_range=50)
	h.add_grid(increment=10)
	h.plot(u[::100], v[::100])
	st.pyplot(fig)
	
	plt.rcParams["date.autoformatter.minute"] = "%H:%M"
	
	def plot(y, y2=None, scatter=False):
		fig, ax = plt.subplots()
		ax.plot(proc_data['Time (UTC)'], proc_data[y], linewidth=0.7)
		plt.xlabel('Time (UTC)')
		plt.ylabel(y, color='b')
		if y2:
			ax2 = ax.twinx()
			ax2.set_ylabel(y2, color='g')
			if scatter:
				ax2.scatter(proc_data['Time (UTC)'], proc_data[y2], color='g', s=3)
			else:
				ax2.plot(proc_data['Time (UTC)'], proc_data[y2], color='g', linewidth=0.7)
			ax2.tick_params(axis='y', color='g')
		ax.axvline(x=proc_data['Time (UTC)'].loc[proc_data[proc_data['Pressure Difference (%)'] >= drop_thres].index.values[0]], color='r')
		ax.axvline(x=proc_data['Time (UTC)'].loc[proc_data['MSL Height (m)'].idxmax()], color='r')
		st.pyplot(fig)
	
	plot('Pressure (hPa)', 'MSL Height (m)')
	plot('Temperature (deg C)', 'Humidity (%)')
	plot('Speed (knots)', 'Direction (deg)', True)
	plot('Voltage (v)', 'GPS Sat')
	plot('SNR (dB)', 'RSSI (dB)')
	
	if st.toggle("Show Data"):
		st.table(display_data)
