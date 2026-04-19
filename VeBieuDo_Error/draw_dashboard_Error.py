import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import re

# ==========================================
# 1. CÁC HÀM XỬ LÝ VÀ KÉO DÀI DỮ LIỆU
# ==========================================

def extend_to_end(df, max_time=1250):
    if df.empty: return df
    last_row = df.iloc[[-1]].copy()
    last_row['Time_sec'] = max_time
    return pd.concat([df, last_row], ignore_index=True)

def load_and_clean_locust(filename):
    df = pd.read_csv(filename)
    df.columns = df.columns.str.strip()
    if 'Name' in df.columns: 
        df = df[df['Name'] == 'Aggregated'].copy()
    
    df['Time_sec'] = df['Timestamp'] - df['Timestamp'].min()
    
    if 'Total Request Count' in df.columns and 'Total Average Response Time' in df.columns:
        df['Total_Time_Sum'] = df['Total Request Count'] * df['Total Average Response Time']
        req_diff = df['Total Request Count'].diff()
        time_diff = df['Total_Time_Sum'].diff()
        df['Inst_Latency'] = time_diff / req_diff
        df['Inst_Latency'] = df['Inst_Latency'].replace([np.inf, -np.inf], np.nan).ffill().fillna(0)
        df['Inst_Latency'] = df['Inst_Latency'].clip(upper=6000).rolling(window=3, min_periods=1).mean()
    else:
        df['Inst_Latency'] = df['50%'].clip(upper=6000).rolling(window=3, min_periods=1).mean()
        
    df['Requests/s'] = df['Requests/s'].clip(upper=350).rolling(window=3, min_periods=1).mean()
    return extend_to_end(df)

def load_hpa_error_log(filename):
    data = []
    try:
        try:
            with open(filename, 'r', encoding='utf-16') as f: lines = f.readlines()
        except UnicodeError:
            with open(filename, 'r', encoding='utf-8') as f: lines = f.readlines()
                
        for line in lines:
            if 'frontend' not in line or 'NAME' in line: continue
            parts = line.strip().split()
            if len(parts) < 8: continue
            
            date_str = f"{parts[0]} {parts[1]}"
            metric_val = 0.0
            
            for p in parts:
                if '/' in p and 'Deployment' not in p:
                    val_str = p.split('/')[0] 
                    if 'unknown' in val_str.lower(): 
                        metric_val = 0.0
                    elif val_str.endswith('m'):
                        metric_val = (float(val_str.replace('m', '')) / 1000.0) * 100
                    else: 
                        try:
                            metric_val = float(val_str) * 100
                        except ValueError:
                            pass
                    break
                    
            try:
                pod_val = int(parts[-2])
                data.append({'Datetime': date_str, 'Error_Pct': metric_val, 'Pods': pod_val})
            except ValueError:
                continue
    except FileNotFoundError:
        print(f"LỖI: Không tìm thấy {filename}")
        return pd.DataFrame()
        
    df = pd.DataFrame(data)
    if df.empty: return pd.DataFrame()
    df['Datetime'] = pd.to_datetime(df['Datetime'], errors='coerce')
    df = df.dropna()
    df['Time_sec'] = (df['Datetime'] - df['Datetime'].min()).dt.total_seconds()
    return extend_to_end(df.sort_values('Time_sec'))

# ==========================================
# 2. NẠP DỮ LIỆU
# ==========================================
print("🚀 Đang vẽ biểu đồ: Nhân bản biểu đồ gộp lỗi thành 2 bản sao để dễ dóng hàng...")

loc_no = load_and_clean_locust('No_KEDA_Error_stats_history.csv')
hpa_no = load_hpa_error_log('Log_Tinh_Standard_Error.txt')

loc_60s = load_and_clean_locust('With_KEDA_Error_60s_stats_history.csv')
hpa_60s = load_hpa_error_log('Log_KEDA_Error_60s.txt')

loc_600s = load_and_clean_locust('With_KEDA_Error_600s_stats_history.csv')
hpa_600s = load_hpa_error_log('Log_KEDA_Error_600s.txt')

P1_START, P1_END = 0, 180           
P2_START, P2_END = 180, 600         
P3_START, P3_END = 600, 900         
P4_START, P4_END = 900, 1250

COLOR_NO = '#e74c3c'      # Đỏ (Tĩnh)
COLOR_60S = '#ff7f0e'     # Cam (60s)
COLOR_600S = '#1f77b4'    # Xanh dương (600s)
col_users = 'User Count'

def add_phase_bg(ax, show_labels=False):
    ax.axvspan(P1_START, P1_END, color='#e0f7fa', alpha=0.5) 
    ax.axvspan(P2_START, P2_END, color='#fff9c4', alpha=0.5) 
    ax.axvspan(P3_START, P3_END, color='#c8e6c9', alpha=0.5) 
    ax.axvspan(P4_START, P4_END, color='#e1bee7', alpha=0.4) 

    if show_labels:
        bbox_props = dict(facecolor='white', alpha=0.85, edgecolor='gray', boxstyle='round,pad=0.3')
        y_pos = 0.5 
        ax.text((P1_START + P1_END)/2, y_pos, 'Khởi động\n(30 Users)', transform=ax.get_xaxis_transform(), fontsize=10, color='#00838f', fontweight='bold', ha='center', va='center', bbox=bbox_props)
        ax.text((P2_START + P2_END)/2, y_pos, 'Đỉnh tải\n(200 Users)', transform=ax.get_xaxis_transform(), fontsize=11, color='#f57f17', fontweight='bold', ha='center', va='center', bbox=bbox_props)
        ax.text((P3_START + P3_END)/2, y_pos, 'Hạ nhiệt\n(10 Users)', transform=ax.get_xaxis_transform(), fontsize=10, color='#2e7d32', fontweight='bold', ha='center', va='center', bbox=bbox_props)
        ax.text((P4_START + P4_END)/2, y_pos, 'Tải nền\n(1 User)', transform=ax.get_xaxis_transform(), fontsize=10, color='#6a1b9a', fontweight='bold', ha='center', va='center', bbox=bbox_props)

# ==========================================
# 3. VẼ SIÊU DASHBOARD
# ==========================================
fig = plt.figure(figsize=(24, 20)) 
fig.suptitle('BIỂU ĐỒ SO SÁNH HIỆU NĂNG KHI CÓ KEDA VÀ CHỨNG MINH KHẢ NĂNG SCALE UP - SCALE DOWN LINH HOẠT (KỊCH BẢN ERROR)', fontsize=24, fontweight='bold', y=0.94)

outer_gs = gridspec.GridSpec(2, 2, figure=fig, hspace=0.3, wspace=0.15)

# --- [GÓC TRÁI TRÊN]: RPS ---
inner_rps = outer_gs[0, 0].subgridspec(2, 1, height_ratios=[2.5, 1], hspace=0.1)
ax_rps = fig.add_subplot(inner_rps[0])
add_phase_bg(ax_rps, show_labels=False)
ax_rps.plot(loc_no['Time_sec'], loc_no['Requests/s'], color=COLOR_NO, linewidth=2.5, linestyle='--', label='Kịch bản (NoKEDA)', zorder=10)
ax_rps.plot(loc_60s['Time_sec'], loc_60s['Requests/s'], color=COLOR_60S, linewidth=3, label='Kịch bản (KEDA-60s) - FLAPPING', zorder=11)
ax_rps.plot(loc_600s['Time_sec'], loc_600s['Requests/s'], color=COLOR_600S, linewidth=3.5, label='Kịch Bản (KEDA-600s) - SMOOTHING', zorder=12)
ax_rps.set_title('THÔNG LƯỢNG HỆ THỐNG (THROUGHPUT)', fontsize=16, fontweight='bold', pad=10)
ax_rps.set_ylabel('Requests / Giây', fontsize=12, fontweight='bold')
ax_rps.legend(loc='upper right', fontsize=12)
ax_rps.grid(True, linestyle=':', alpha=0.6); ax_rps.set_xlim(0, P4_END)
plt.setp(ax_rps.get_xticklabels(), visible=False)

ax_u1 = fig.add_subplot(inner_rps[1], sharex=ax_rps)
add_phase_bg(ax_u1, show_labels=True)
ax_u1.plot(loc_600s['Time_sec'], loc_600s[col_users], color='green', linewidth=2.5, drawstyle='steps-post', label='Lượng User ảo')
ax_u1.set_ylabel('Số Users', fontsize=12, fontweight='bold'); ax_u1.grid(True, linestyle=':', alpha=0.6)

# --- [GÓC PHẢI TRÊN]: LATENCY ---
inner_lat = outer_gs[0, 1].subgridspec(2, 1, height_ratios=[2.5, 1], hspace=0.1)
ax_lat = fig.add_subplot(inner_lat[0])
add_phase_bg(ax_lat, show_labels=False)
ax_lat.plot(loc_no['Time_sec'], loc_no['Inst_Latency'], color=COLOR_NO, linewidth=2.5, linestyle='--', label='Kịch bản NoKEDA (Thảm họa)', zorder=10)
ax_lat.plot(loc_60s['Time_sec'], loc_60s['Inst_Latency'], color=COLOR_60S, linewidth=3, label='KEDA (60s) - FLAPPING', zorder=11)
ax_lat.plot(loc_600s['Time_sec'], loc_600s['Inst_Latency'], color=COLOR_600S, linewidth=3.5, label='KEDA (600s) - SMOOTHING', zorder=12)
ax_lat.axhline(1000, color='purple', linestyle=':', linewidth=2.5, label='Ngưỡng Timeout (1000ms)', zorder=5)
ax_lat.set_title('THỜI GIAN PHẢN HỒI (LATENCY)', fontsize=16, fontweight='bold', pad=10)
ax_lat.set_ylabel('Độ trễ (ms)', fontsize=12, fontweight='bold')
ax_lat.legend(loc='upper right', fontsize=12)
ax_lat.grid(True, linestyle=':', alpha=0.6); ax_lat.set_xlim(0, P4_END)
plt.setp(ax_lat.get_xticklabels(), visible=False)

ax_u2 = fig.add_subplot(inner_lat[1], sharex=ax_lat)
add_phase_bg(ax_u2, show_labels=True)
ax_u2.plot(loc_600s['Time_sec'], loc_600s[col_users], color='green', linewidth=2.5, drawstyle='steps-post')
ax_u2.set_ylabel('Số Users', fontsize=12, fontweight='bold'); ax_u2.grid(True, linestyle=':', alpha=0.6)

# ==========================================
# HÀM VẼ GÓC DƯỚI (DÙNG ĐỂ NHÂN BẢN)
# ==========================================
def draw_combined_bottom_panel(gs_pos):
    inner_combined = outer_gs[gs_pos].subgridspec(2, 1, height_ratios=[2, 1.2], hspace=0.15)

    # --- Bảng Lỗi (Gộp 3 đường) ---
    ax_err = fig.add_subplot(inner_combined[0])
    add_phase_bg(ax_err, show_labels=False)

    if not hpa_no.empty:
        ax_err.plot(hpa_no['Time_sec'], hpa_no['Error_Pct'], color=COLOR_NO, linewidth=2.0, linestyle='--', label='Lỗi (NoKEDA)', zorder=10)
        ax_err.fill_between(hpa_no['Time_sec'], hpa_no['Error_Pct'], color=COLOR_NO, alpha=0.1, zorder=2)
        
    if not hpa_60s.empty:
        ax_err.plot(hpa_60s['Time_sec'], hpa_60s['Error_Pct'], color=COLOR_60S, linewidth=2.5, linestyle='-.', label='Lỗi (KEDA-60s)', zorder=11)
        ax_err.fill_between(hpa_60s['Time_sec'], hpa_60s['Error_Pct'], color=COLOR_60S, alpha=0.1, zorder=3) 
        
    if not hpa_600s.empty:
        ax_err.plot(hpa_600s['Time_sec'], hpa_600s['Error_Pct'], color=COLOR_600S, linewidth=3.5, label='Lỗi (KEDA-600s)', zorder=12)
        ax_err.fill_between(hpa_600s['Time_sec'], hpa_600s['Error_Pct'], color=COLOR_600S, alpha=0.15, zorder=4) 

    ax_err.axhline(1.0, color='darkgrey', linestyle='-', linewidth=2, label='Ngưỡng Scale KEDA (1.0%)', zorder=5)
    ax_err.set_title('ĐÁNH GIÁ TỔNG HỢP TỶ LỆ LỖI (NoKEDA - KEDA 60s - KEDA 600s)', fontsize=16, fontweight='bold', pad=10)
    ax_err.set_ylabel('Tỷ lệ lỗi (%)', fontsize=12, fontweight='bold')
    ax_err.set_ylim(bottom=-2, top=105) 
    ax_err.legend(loc='upper right', fontsize=11, ncol=2, framealpha=0.9)
    ax_err.grid(True, linestyle=':', alpha=0.6)
    ax_err.set_xlim(0, P4_END)
    plt.setp(ax_err.get_xticklabels(), visible=False)

    # --- Bảng Pods (Gộp 3 đường) ---
    ax_pod = fig.add_subplot(inner_combined[1], sharex=ax_err)
    add_phase_bg(ax_pod, show_labels=False)

    if not hpa_no.empty:
        ax_pod.plot(hpa_no['Time_sec'], hpa_no['Pods'], color=COLOR_NO, linewidth=2.5, linestyle='--', drawstyle='steps-post', label='Pod (Tĩnh)', zorder=10)
        
    if not hpa_60s.empty:
        ax_pod.plot(hpa_60s['Time_sec'], hpa_60s['Pods'], color=COLOR_60S, linewidth=2.5, linestyle='-.', drawstyle='steps-post', label='Pod (60s)', zorder=11)
        
    if not hpa_600s.empty:
        ax_pod.plot(hpa_600s['Time_sec'], hpa_600s['Pods'], color=COLOR_600S, linewidth=4.0, drawstyle='steps-post', label='Pod (600s)', zorder=12)
        ax_pod.fill_between(hpa_600s['Time_sec'], hpa_600s['Pods'], step='post', color=COLOR_600S, alpha=0.1, zorder=1)

    ax_pod.set_ylabel('Số lượng Pods', fontsize=12, fontweight='bold')
    ax_pod.set_xlabel('Thời gian thực thi (Giây)', fontsize=13, fontweight='bold')
    ax_pod.set_yticks(range(0, 7))
    ax_pod.legend(loc='upper right', fontsize=11, ncol=3, framealpha=0.9)
    ax_pod.grid(True, linestyle=':', alpha=0.6)

# Vẽ 2 biểu đồ sinh đôi y hệt nhau ở góc dưới trái và dưới phải
draw_combined_bottom_panel((1, 0))
draw_combined_bottom_panel((1, 1))

# Xuất cả file PNG và SVG
plt.savefig('Master_Dashboard_Error.png', dpi=300, bbox_inches='tight')
plt.savefig('Master_Dashboard_Error.svg', format='svg', bbox_inches='tight')
print("✅ HOÀN TẤT! Đã nhân đôi biểu đồ gộp thành 2 ô trái phải để dóng hàng!")