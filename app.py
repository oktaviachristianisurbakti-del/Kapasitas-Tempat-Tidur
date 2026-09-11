from datetime import datetime, timedelta
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Dashboard Overkapasitas Faskes", page_icon="🏥", layout="wide"
)

st.title("🏥 Dashboard Monitoring & Warning Overkapasitas Faskes")
st.markdown(
    "Aplikasi otomatisasi pemanfaatan hari rawat dan deteksi overkapasitas tempat tidur (TT) per faskes."
)

# 1. Inisialisasi Session State untuk menyimpan data kunjungan sementara
if "data_kunjungan" not in st.session_state:
    st.session_state.data_kunjungan = pd.DataFrame(
        [
            {
                "Faskes": "RS Sehat Selalu",
                "No_Kunjungan": "KUN-001",
                "Tgl_Datang": "2026-06-01",
                "Tgl_Pulang": "2026-06-03",
                "Jumlah_TT": 5,
            },
            {
                "Faskes": "RS Sehat Selalu",
                "No_Kunjungan": "KUN-002",
                "Tgl_Datang": "2026-06-01",
                "Tgl_Pulang": "2026-06-02",
                "Jumlah_TT": 5,
            },
            {
                "Faskes": "RS Bhakti Husada",
                "No_Kunjungan": "BH-001",
                "Tgl_Datang": "2026-06-01",
                "Tgl_Pulang": "2026-06-03",
                "Jumlah_TT": 3,
            },
        ]
    )

# Sidebar untuk Input Data Kunjungan Baru
st.sidebar.header("➕ Input Kunjungan Faskes")
with st.sidebar.form("form_kunjungan"):
    faskes_input = st.text_input("Nama Faskes")
    no_kunjungan = st.text_input("Nomor Kunjungan")
    tgl_datang = st.date_input("Tanggal Datang", value=datetime.today())
    tgl_pulang = st.date_input(
        "Tanggal Pulang", value=datetime.today() + timedelta(days=2)
    )
    jumlah_tt = st.number_input(
        "Jumlah Tempat Tidur (TT)", min_value=1, value=10
    )

    submit_button = st.form_submit_button(label="Simpan Data")

    if submit_button:
        if faskes_input and no_kunjungan:
            new_row = {
                "Faskes": faskes_input,
                "No_Kunjungan": no_kunjungan,
                "Tgl_Datang": str(tgl_datang),
                "Tgl_Pulang": str(tgl_pulang),
                "Jumlah_TT": int(jumlah_tt),
            }
            st.session_state.data_kunjungan = pd.concat(
                [
                    st.session_state.data_kunjungan,
                    pd.DataFrame([new_row]),
                ],
                ignore_index=True,
            )
            st.sidebar.success("Data berhasil ditambahkan!")
        else:
            st.sidebar.error(
                "Nama Faskes dan Nomor Kunjungan tidak boleh kosong!"
            )

df_visits = st.session_state.data_kunjungan

# Tab Utama Aplikasi
tab1, tab2 = st.tabs(
    ["📊 Dashboard & Rekap Warning", "📋 Database Kunjungan Mentah"]
)

with tab1:
    st.subheader("Analisis Pemanfaatan & Status Overkapasitas Harian")

    if not df_visits.empty:
        df_visits["Tgl_Datang_dt"] = pd.to_datetime(df_visits["Tgl_Datang"])
        df_visits["Tgl_Pulang_dt"] = pd.to_datetime(df_visits["Tgl_Pulang"])

        min_date = df_visits["Tgl_Datang_dt"].min()
        max_date = df_visits["Tgl_Pulang_dt"].max()
        all_dates = pd.date_range(start=min_date, end=max_date)

        rekap_list = []
        faskes_groups = df_visits.groupby("Faskes")

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

        # Filter Berdasarkan Faskes
        selected_faskes = st.selectbox(
            "Filter Berdasarkan Faskes",
            ["Semua Faskes"] + list(df_visits["Faskes"].unique()),
        )
        if selected_faskes != "Semua Faskes":
            df_rekap = df_rekap[df_rekap["Nama Faskes"] == selected_faskes]


        # Pewarnaan Warning
        def highlight_overcapacity(val):
            return (
                "background-color: #ff4d4d; color: white; font-weight: bold;"
                if val == "OVERKAPASITAS"
                else "background-color: #d4edda; color: #155724;"
            )


        st.dataframe(
            df_rekap.style.applymap(
                highlight_overcapacity, subset=["Status Warning"]
            ),
            use_container_width=True,
        )

        total_overcapacity = (df_rekap["Status Warning"] == "OVERKAPASITAS").sum()
        if total_overcapacity > 0:
            st.error(
                f"⚠️ Peringatan! Ditemukan {total_overcapacity} catatan insiden overkapasitas pada periode ini."
            )
        else:
            st.success(
                "✅ Aman! Tidak ada indikasi overkapasitas pada periode ini."
            )
    else:
        st.info("Belum ada data kunjungan. Silakan input melalui sidebar.")

with tab2:
    st.subheader("Data Mentah Kunjungan Faskes")
    st.dataframe(
        df_visits.drop(
            columns=["Tgl_Datang_dt", "Tgl_Pulang_dt"], errors="ignore"
        ),
        use_container_width=True,
    )
