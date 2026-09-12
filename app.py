from datetime import datetime, timedelta
import io
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Dashboard Overkapasitas & Audit RITP",
    page_icon="🏥",
    layout="wide",
)

st.title(
    "🏥 Dashboard Monitoring Overkapasitas & Audit Potensi Prolonged Stay RITP"
)
st.markdown(
    "Upload file Excel kunjungan FKTP untuk mendeteksi overkapasitas harian serta melacak nomor kunjungan penyebabnya."
)

# Sidebar untuk Upload File Excel
st.sidebar.header("📁 Upload Data Excel")
uploaded_file = st.sidebar.file_uploader(
    "Pilih file Excel (.xlsx / .xls)", type=["xlsx", "xls"]
)

with st.sidebar.expander("ℹ️ Panduan Format Kolom"):
    st.markdown(
        """
        Pastikan file Excel Anda memiliki kolom:
        1. **Nama Faskes**
        2. **No_Kunjungan**
        3. **Tgl_Datang** (Format: YYYY-MM-DD)
        4. **Tgl_Pulang** (Format: YYYY-MM-DD)
        5. **Jumlah_TT**
    """
    )

if uploaded_file is not None:
    try:
        df_visits = pd.read_excel(uploaded_file)

        expected_cols = [
            "Nama Faskes",
            "No_Kunjungan",
            "Tgl_Datang",
            "Tgl_Pulang",
            "Jumlah_TT",
        ]
        if not all(col in df_visits.columns for col in expected_cols):
            st.error(
                f"Format kolom Excel tidak sesuai! Pastikan ada kolom: {expected_cols}"
            )
        else:
            # Konversi kolom tanggal
            df_visits["Tgl_Datang_dt"] = pd.to_datetime(
                df_visits["Tgl_Datang"], errors="coerce"
            )
            df_visits["Tgl_Pulang_dt"] = pd.to_datetime(
                df_visits["Tgl_Pulang"], errors="coerce"
            )

            min_date = df_visits["Tgl_Datang_dt"].min()
            max_date = df_visits["Tgl_Pulang_dt"].max()
            all_dates = pd.date_range(start=min_date, end=max_date)

            rekap_list = []
            faskes_groups = df_visits.groupby("Nama Faskes")

            for faskes, group in faskes_groups:
                max_tt = int(group["Jumlah_TT"].iloc[-1])
                for d in all_dates:
                    d_str = d.strftime("%Y-%m-%d")

                    # Sensus Pasien Dirawat (Datang <= d <= Pulang)
                    sensus_mask = (group["Tgl_Datang_dt"] <= d) & (
                        group["Tgl_Pulang_dt"] >= d
                    )
                    pasien_dirawat_df = group[sensus_mask]
                    pasien_dirawat_count = int(pasien_dirawat_df.shape[0])

                    # Ambil daftar No Kunjungan yang sedang dirawat pada tanggal tersebut
                    list_no_kunjungan = ", ".join(
                        pasien_dirawat_df["No_Kunjungan"].astype(str).tolist()
                    )

                    # Pasien Pulang pada tanggal d
                    pulang_mask = group["Tgl_Pulang_dt"] == d
                    pasien_pulang_count = int(pulang_mask.sum())

                    # Logika: Jumlah TT + Pasien Pulang - Pasien Dirawat
                    sisa_kapasitas = (
                        max_tt + pasien_pulang_count - pasien_dirawat_count
                    )
                    status = (
                        "OVERKAPASITAS" if sisa_kapasitas < 0 else "Normal"
                    )

                    rekap_list.append(
                        {
                            "Nama Faskes": faskes,
                            "Tanggal": d_str,
                            "Jumlah TT": max_tt,
                            "Pasien Dirawat": pasien_dirawat_count,
                            "Pasien Pulang": pasien_pulang_count,
                            "Sisa Kapasitas": sisa_kapasitas,
                            "Status Warning": status,
                            "No Kunjungan Dirawat (Potensi Audit)": list_no_kunjungan,
                        }
                    )

            df_rekap = pd.DataFrame(rekap_list)

            # Tab Utama Aplikasi
            tab1, tab2 = st.tabs(
                [
                    "📊 Dashboard & Audit Warning",
                    "📋 Database Kunjungan Mentah",
                ]
            )

            with tab1:
                st.subheader(
                    "Analisis Pemanfaatan, Warning, & Penelusuran Kunjungan"
                )

                # --- AREA FILTER (Faskes & Status Warning) ---
                col_f1, col_f2 = st.columns(2)
                with col_f1:
                    selected_faskes = st.selectbox(
                        "Filter Berdasarkan Faskes",
                        ["Semua Faskes"]
                        + list(df_visits["Nama Faskes"].unique()),
                    )
                with col_f2:
                    selected_status = st.selectbox(
                        "Filter Berdasarkan Status Warning",
                        ["Semua Status", "OVERKAPASITAS", "Normal"],
                    )

                df_display = df_rekap.copy()
                if selected_faskes != "Semua Faskes":
                    df_display = df_display[
                        df_display["Nama Faskes"] == selected_faskes
                    ]
                if selected_status != "Semua Status":
                    df_display = df_display[
                        df_display["Status Warning"] == selected_status
                    ]
                # ---------------------------------------------


                def highlight_overcapacity(val):
                    return (
                        "background-color: #ff4d4d; color: white; font-weight: bold;"
                        if val == "OVERKAPASITAS"
                        else "background-color: #d4edda; color: #155724;"
                    )


                st.dataframe(
                    df_display.style.map(
                        highlight_overcapacity, subset=["Status Warning"]
                    ),
                    use_container_width=True,
                )

                # Tombol Download Excel Rekap
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine="openpyxl") as writer:
                    df_rekap.to_excel(
                        writer, index=False, sheet_name="Audit Overkapasitas"
                    )
                excel_data = output.getvalue()

                st.download_button(
                    label="📥 Download Laporan Audit Lengkap (Excel)",
                    data=excel_data,
                    file_name="Laporan_Audit_Overkapasitas_RITP.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )

                # Ringkasan Alert Audit
                total_overcapacity = (
                    df_rekap["Status Warning"] == "OVERKAPASITAS"
                ).sum()
                if total_overcapacity > 0:
                    st.error(
                        f"⚠️ Peringatan Audit! Terdeteksi {total_overcapacity} titik hari overkapasitas yang berisiko menjadi celah prolonged stay."
                    )
                else:
                    st.success(
                        "✅ Aman! Tidak ada indikasi overkapasitas pada periode ini."
                    )

            with tab2:
                st.subheader("Data Mentah Kunjungan Faskes")
                st.dataframe(
                    df_visits.drop(
                        columns=["Tgl_Datang_dt", "Tgl_Pulang_dt"],
                        errors="ignore",
                    ),
                    use_container_width=True,
                )

    except Exception as e:
        st.error(f"Terjadi kesalahan saat membaca file Excel: {e}")
else:
    st.info(
        "👈 Silakan **Upload File Excel** melalui panel di sebelah kiri untuk mulai menjalankan audit."
    )
