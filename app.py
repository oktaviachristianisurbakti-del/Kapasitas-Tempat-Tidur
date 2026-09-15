from datetime import datetime, timedelta
import io
import re
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Dashboard Audit Overkapasitas & Anomali No Kunjungan",
    page_icon="🏥",
    layout="wide",
)

st.title(
    "🏥 Dashboard Audit Overkapasitas & Deteksi Backdate No Kunjungan (> 3 Hari Kerja)"
)
st.markdown(
    "Upload file Excel kunjungan FKTP untuk mendeteksi overkapasitas harian, anomali nomor kunjungan, serta unduh hasil audit siap pakai."
)

# Sidebar untuk Upload File Excel
st.sidebar.header("📁 Upload Data Excel")
uploaded_file = st.sidebar.file_uploader(
    "Pilih file Excel (.xlsx / .xls)", type=["xlsx", "xls"]
)

with st.sidebar.expander("ℹ️ Panduan Format Kolom Excel"):
    st.markdown(
        """
        Pastikan file Excel Anda memiliki kolom:
        1. **Nama Faskes**
        2. **No_Kunjungan** (Nomor urut/kunjungan yang merefleksikan urutan terbit)
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


            # Ekstrak angka dari No_Kunjungan
            def extract_number(val):
                numbers = re.findall(r"\d+", str(val))
                return int(numbers[-1]) if numbers else 0


            df_visits["Nomor_Urut"] = df_visits["No_Kunjungan"].apply(
                extract_number
            )

            # --- LOGIKA DETEKSI BACKDATE > 3 HARI KERJA BERDASARKAN URUTAN NOMOR ---
            df_temp = df_visits.dropna(subset=["Tgl_Datang_dt", "Nomor_Urut"])
            faskes_audit_results = []

            for faskes, group in df_temp.groupby("Nama Faskes"):
                g_sorted = group.sort_values(by="Tgl_Datang_dt")
                min_date = g_sorted["Tgl_Datang_dt"].min()
                max_date = g_sorted["Tgl_Datang_dt"].max()
                total_days = max(1, (max_date - min_date).days + 1)

                total_kunjungan = len(g_sorted)
                avg_per_day = max(1, total_kunjungan / total_days)

                g_sorted = g_sorted.sort_values(by="Nomor_Urut")
                min_no = g_sorted["Nomor_Urut"].min()

                for _, row in group.iterrows():
                    selisih_nomor = row["Nomor_Urut"] - min_no
                    estimasi_hari_ke = selisih_nomor / avg_per_day
                    estimasi_tgl_terbit = min_date + timedelta(
                        days=int(estimasi_hari_ke)
                    )

                    selisih_hari_backdate = (
                        estimasi_tgl_terbit - row["Tgl_Datang_dt"]
                    ).days

                    status_bk = (
                        "⚠️ TERBIT > 3 HARI KERJA (BACKDATE)"
                        if selisih_hari_backdate > 3
                        else "Normal"
                    )

                    faskes_audit_results.append(
                        {
                            "Index": row.name,
                            "Estimasi_Tgl_Terbit": estimasi_tgl_terbit.strftime(
                                "%Y-%m-%d"
                            ),
                            "Estimasi_Selisih_Hari": selisih_hari_backdate,
                            "Status_Backdate_Audit": status_bk,
                        }
                    )

            df_audit_res = pd.DataFrame(faskes_audit_results).set_index(
                "Index"
            )
            df_visits["Estimasi_Tgl_Terbit"] = df_audit_res[
                "Estimasi_Tgl_Terbit"
            ]
            df_visits["Status_Backdate_Audit"] = df_audit_res[
                "Status_Backdate_Audit"
            ].fillna("Normal")

            # --- KALKULASI OVERKAPASITAS HARIAN ---
            min_date_all = df_visits["Tgl_Datang_dt"].min()
            max_date_all = df_visits["Tgl_Pulang_dt"].max()
            all_dates = pd.date_range(start=min_date_all, end=max_date_all)

            rekap_list = []
            faskes_groups = df_visits.groupby("Nama Faskes")

            for faskes, group in faskes_groups:
                max_tt = int(group["Jumlah_TT"].iloc[-1])
                for d in all_dates:
                    d_str = d.strftime("%Y-%m-%d")

                    sensus_mask = (group["Tgl_Datang_dt"] <= d) & (
                        group["Tgl_Pulang_dt"] >= d
                    )
                    pasien_dirawat_df = group[sensus_mask]
                    pasien_dirawat_count = int(pasien_dirawat_df.shape[0])

                    list_no_kunjungan = ", ".join(
                        pasien_dirawat_df["No_Kunjungan"].astype(str).tolist()
                    )

                    pulang_mask = group["Tgl_Pulang_dt"] == d
                    pasien_pulang_count = int(pulang_mask.sum())

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
                            "No Kunjungan Dirawat": list_no_kunjungan,
                        }
                    )

            df_rekap = pd.DataFrame(rekap_list)

            # Hitung metrik ringkasan analisis
            total_overkap_days = (
                df_rekap["Status Warning"] == "OVERKAPASITAS"
            ).sum()
            df_backdate_alert = df_visits[
                df_visits["Status_Backdate_Audit"] != "Normal"
            ]
            total_backdate_cases = len(df_backdate_alert)

            # Tab Utama Aplikasi
            tab1, tab2, tab3 = st.tabs(
                [
                    "📊 Dashboard Rekap Overkapasitas",
                    "🔍 Audit Backdate No Kunjungan (> 3 Hari)",
                    "📋 Database Kunjungan Mentah",
                ]
            )

            with tab1:
                st.subheader("Analisis Pemanfaatan & Warning Overkapasitas Harian")

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

                # Kotak Ringkasan Hasil Analisis Siap Salin
                st.markdown("---")
                st.subheader("📝 Ringkasan Hasil Analisis Audit RITP")
                summary_text = f"""
                - **Total Titik Hari Overkapasitas Terdeteksi:** {total_overkap_days} hari
                - **Total Indikasi Backdate Nomor Kunjungan (> 3 Hari Kerja):** {total_backdate_cases} kunjungan
                - **Rekomendasi Audit:** Lakukan investigasi mendalam terhadap daftar nomor kunjungan pada tanggal-tanggal yang berstatus OVERKAPASITAS untuk mencegah celah *prolonged stay*. Periksa juga daftar kunjungan berlabel backdate di tab kedua.
                """
                st.info(summary_text)

                output = io.BytesIO()
                with pd.ExcelWriter(output, engine="openpyxl") as writer:
                    df_rekap.to_excel(
                        writer, index=False, sheet_name="Audit Overkapasitas"
                    )
                excel_data = output.getvalue()

                st.download_button(
                    label="📥 Download Laporan Audit Overkapasitas (Excel)",
                    data=excel_data,
                    file_name="Laporan_Audit_Overkapasitas_RITP.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )

            with tab2:
                st.subheader(
                    "🔍 Investigasi Kunjungan dengan Indikasi Backdate (> 3 Hari Kerja)"
                )
                st.markdown(
                    f"Ditemukan **{total_backdate_cases}** kunjungan yang terindikasi dicetak/diterbitkan **lebih dari 3 hari kerja** setelah tanggal pelayanan berdasarkan analisis urutan nomor kunjungan."
                )


                def highlight_backdate_alert(val):
                    return (
                        "background-color: #ffc107; color: black; font-weight: bold;"
                        if "BACKDATE" in str(val)
                        else ""
                    )


                # Tampilkan tabel yang bisa di-copy langsung
                st.dataframe(
                    df_visits.style.map(
                        highlight_backdate_alert,
                        subset=["Status_Backdate_Audit"],
                    ),
                    use_container_width=True,
                )

                # --- TOMBOL DOWNLOAD KHUSUS TABEL BACKDATE ---
                output_bk = io.BytesIO()
                with pd.ExcelWriter(output_bk, engine="openpyxl") as writer_bk:
                    df_visits.to_excel(
                        writer_bk, index=False, sheet_name="Audit Backdate No Kunjungan"
                    )
                excel_data_bk = output_bk.getvalue()

                st.download_button(
                    label="📥 Download Laporan Audit Backdate (Excel)",
                    data=excel_data_bk,
                    file_name="Laporan_Audit_Backdate_No_Kunjungan.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
                # ---------------------------------------------

            with tab3:
                st.subheader("Data Mentah Kunjungan Faskes")
                st.dataframe(
                    df_visits.drop(
                        columns=[
                            "Tgl_Datang_dt",
                            "Tgl_Pulang_dt",
                            "Nomor_Urut",
                        ],
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
