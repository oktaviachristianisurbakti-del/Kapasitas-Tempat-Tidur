from datetime import datetime, timedelta
import io
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Dashboard Overkapasitas Faskes", page_icon="🏥", layout="wide"
)

st.title("🏥 Dashboard Monitoring & Warning Overkapasitas Faskes")
st.markdown(
    "Upload file Excel kunjungan faskes Anda untuk menghitung pemanfaatan hari rawat dan deteksi overkapasitas tempat tidur (TT) secara otomatis."
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

                    # Sensus Pasien Dirawat
                    sensus_mask = (group["Tgl_Datang_dt"] <= d) & (
                        group["Tgl_Pulang_dt"] >= d
                    )
                    pasien_dirawat = int(sensus_mask.sum())

                    # Pasien Pulang
                    pulang_mask = group["Tgl_Pulang_dt"] == d
                    pasien_pulang = int(pulang_mask.sum())

                    # Logika: Jumlah TT + Pasien Pulang - Pasien Dirawat
                    sisa_kapasitas = max_tt + pasien_pulang - pasien_dirawat
                    status = (
                        "OVERKAPASITAS" if sisa_kapasitas < 0 else "Normal"
                    )

                    rekap_list.append(
                        {
                            "Nama Faskes": faskes,
                            "Tanggal": d_str,
                            "Jumlah TT": max_tt,
                            "Pasien Dirawat": pasien_dirawat,
                            "Pasien Pulang": pasien_pulang,
                            "Sisa Kapasitas": sisa_kapasitas,
                            "Status Warning": status,
                        }
                    )

            df_rekap = pd.DataFrame(rekap_list)

            # Tab Utama Aplikasi
            tab1, tab2 = st.tabs(
                [
                    "📊 Dashboard & Rekap Warning",
                    "📋 Database Kunjungan Mentah",
                ]
            )

            with tab1:
                st.subheader("Analisis Pemanfaatan & Status Overkapasitas Harian")

                # Filter Berdasarkan Faskes
                selected_faskes = st.selectbox(
                    "Filter Berdasarkan Faskes",
                    ["Semua Faskes"] + list(df_visits["Nama Faskes"].unique()),
                )
                df_display = df_rekap.copy()
                if selected_faskes != "Semua Faskes":
                    df_display = df_display[
                        df_display["Nama Faskes"] == selected_faskes
                    ]


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

                # --- FITUR TOMBOL DOWNLOAD EXCEL ---
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine="openpyxl") as writer:
                    df_rekap.to_excel(
                        writer, index=False, sheet_name="Rekap Overkapasitas"
                    )
                excel_data = output.getvalue()

                st.download_button(
                    label="📥 Download Hasil Analisis (Excel)",
                    data=excel_data,
                    file_name="Laporan_Rekap_Overkapasitas_Faskes.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
                # -----------------------------------

                total_overcapacity = (
                    df_rekap["Status Warning"] == "OVERKAPASITAS"
                ).sum()
                if total_overcapacity > 0:
                    st.error(
                        f"⚠️ Peringatan! Ditemukan {total_overcapacity} catatan insiden overkapasitas pada periode ini."
                    )
                else:
                    st.success(
                        "✅ Aman! Tidak ada indikasi overkapasitas pada periode ini."
                    )

            with tab2:
                st.subheader("Data Mentah dari Excel")
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
        "👈 Silakan **Upload File Excel** melalui panel di sebelah kiri untuk mulai melihat hasil kalkulasi."
    )
