import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import plotly.express as px

from database import (
    get_connection, init_db, get_all_users, add_user, delete_user,
    update_product_price_stock, update_product_details, delete_product
)

# ---------------------------------------------------------
# ALGORITMA SINGLE EXPONENTIAL SMOOTHING & MAPE
# ---------------------------------------------------------
def single_exponential_smoothing(data, alpha):
    if len(data) == 0:
        return [], 0
    
    forecast = [float(data[0])]
    for t in range(1, len(data)):
        f_next = alpha * data[t-1] + (1 - alpha) * forecast[t-1]
        forecast.append(round(f_next, 2))
    
    next_period_forecast = round(alpha * data[-1] + (1 - alpha) * forecast[-1], 2)
    return forecast, next_period_forecast

def calculate_mape(actual, forecast):
    actual = np.array(actual, dtype=float)
    forecast = np.array(forecast, dtype=float)
    valid_idx = actual != 0
    if not np.any(valid_idx):
        return 0.0
    mape = np.mean(np.abs((actual[valid_idx] - forecast[valid_idx]) / actual[valid_idx])) * 100
    return round(mape, 2)

# ---------------------------------------------------------
# KLASIFIKASI FAST-MOVING OTOMATIS DARI TRANSAKSI
# ---------------------------------------------------------
def update_fast_moving_status():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE products SET is_fast_moving = 0")
    
    cursor.execute("""
        SELECT product_id, SUM(quantity) as total_sold 
        FROM sales 
        GROUP BY product_id
    """)
    results = cursor.fetchall()
    
    if results:
        df_sold = pd.DataFrame(results, columns=["product_id", "total_sold"])
        avg_sales = df_sold["total_sold"].mean()
        fast_ids = df_sold[df_sold["total_sold"] >= avg_sales]["product_id"].tolist()
        
        if fast_ids:
            format_strings = ','.join(['%s'] * len(fast_ids))
            cursor.execute(f"UPDATE products SET is_fast_moving = 1 WHERE id IN ({format_strings})", tuple(fast_ids))
            
    conn.commit()
    cursor.close()
    conn.close()

# ---------------------------------------------------------
# INISIALISASI APLIKASI & LOGIN
# ---------------------------------------------------------
st.set_page_config(
    page_title="Toko Kelontong Warti Jaya",
    page_icon="🛒",
    layout="wide"
)

init_db()

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.role = ""

if not st.session_state.logged_in:
    st.title("🔐 Login Sistem Kasir Toko Kelontong X")
    with st.form("login_form"):
        username_input = st.text_input("Username")
        password_input = st.text_input("Password", type="password")
        submit_login = st.form_submit_button("Masuk")
        
        if submit_login:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM users WHERE username = %s AND password = %s", (username_input, password_input))
            user = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if user:
                st.session_state.logged_in = True
                st.session_state.username = user["username"]
                st.session_state.role = user["role"]
                st.success("Login Berhasil!")
                st.rerun()
            else:
                st.error("Username atau Password salah!")
    st.stop()

# ---------------------------------------------------------
# MENU NAVIGASI BERDASARKAN ROLE
# ---------------------------------------------------------
st.sidebar.title("📌 Menu Navigasi")
st.sidebar.markdown(f"👤 Login: **{st.session_state.username}**")
st.sidebar.markdown(f"🏷️ Role: **{st.session_state.role}**")
st.sidebar.divider()

if st.session_state.role == "Pemilik":
    menu = st.sidebar.radio(
        "Pilih Modul:",
        ["Dashboard & Prediksi Stok (SES)", "Transaksi Kasir", "Data Produk", "Riwayat Penjualan", "Kelola Pengguna"]
    )
else:
    menu = st.sidebar.radio(
        "Pilih Modul:",
        ["Transaksi Kasir", "Riwayat Penjualan"]
    )

st.sidebar.divider()
if st.sidebar.button("🚪 Keluar (Logout)"):
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.role = ""
    st.rerun()

# ---------------------------------------------------------
# MODUL 1: DASHBOARD & PREDIKSI STOK (SES + MAPE) - PEMILIK
# ---------------------------------------------------------
if menu == "Dashboard & Prediksi Stok (SES)":
    st.header("📈 Dashboard Prediksi Stok Barang (Single Exponential Smoothing)")
    st.caption("Klasifikasi Fast-Moving dihitung secara otomatis dari data transaksi.")
    
    update_fast_moving_status()
    
    conn = get_connection()
    df_products = pd.read_sql("SELECT * FROM products WHERE is_fast_moving = 1", conn)
    
    if df_products.empty:
        st.warning("Belum ada produk 'Fast-Moving'. Lakukan beberapa transaksi penjualan terlebih dahulu.")
    else:
        selected_product_id = st.selectbox(
            "Pilih Produk Fast-Moving:",
            df_products["id"],
            format_func=lambda x: df_products[df_products["id"] == x]["name"].values[0]
        )
        
        query_sales = """
            SELECT date, SUM(quantity) as total_qty
            FROM sales 
            WHERE product_id = %s 
            GROUP BY date 
            ORDER BY date ASC
        """
        df_sales = pd.read_sql(query_sales, conn, params=(int(selected_product_id),))
        
        if len(df_sales) < 3:
        # ---------------------------------------------------------
        # MODUL 1: DASHBOARD & PREDIKSI STOK (SES + MAPE) - PEMILIK
        # ---------------------------------------------------------
            st.info("Membutuhkan minimal 3 record historis transaksi untuk menjalankan peramalan SES.")
        else:
            col_param, col_metric = st.columns([1, 2])
            
            with col_param:
                st.subheader("Parameter Peramalan")
                alpha = st.slider("Nilai Alpha (α):", min_value=0.01, max_value=0.99, value=0.20, step=0.01)
                
            actual_data = df_sales["total_qty"].tolist()
            forecast_history, next_forecast = single_exponential_smoothing(actual_data, alpha)
            mape_score = calculate_mape(actual_data, forecast_history)
            
            df_sales["Hasil Prediksi (SES)"] = forecast_history
            df_sales["Error Absolut"] = np.abs(df_sales["total_qty"] - df_sales["Hasil Prediksi (SES)"])
            
            with col_metric:
                st.subheader("Hasil Evaluasi & Rekomendasi")
                m1, m2, m3 = st.columns(3)
                m1.metric("Prediksi Periode Depan", f"{next_forecast:.0f} Pcs")
                m2.metric("Nilai Akurasi MAPE", f"{mape_score}%")
                
                if mape_score < 10:
                    kategori_mape = "Sangat Akurat (<10%)"
                elif mape_score < 20:
                    kategori_mape = "Baik (10-20%)"
                elif mape_score < 50:
                    kategori_mape = "Layak (20-50%)"
                else:
                    kategori_mape = "Buruk (>50%)"
                m3.metric("Kualitas Prediksi", kategori_mape)

            st.divider()
            st.subheader("Grafik Perbandingan Data Aktual vs Prediksi SES")
            df_chart = df_sales.copy()
            df_chart = df_chart.rename(columns={"total_qty": "Data Penjualan Aktual"})
            fig = px.line(
                df_chart, 
                x="date", 
                y=["Data Penjualan Aktual", "Hasil Prediksi (SES)"],
                markers=True,
                title="Tren Penjualan vs Hasil Peramalan SES"
            )
            st.plotly_chart(fig, use_container_width=True)
            
            st.subheader("Tabel Detail Perhitungan Runtut Waktu")
            st.dataframe(df_sales, use_container_width=True)
            
    conn.close()

# ---------------------------------------------------------
# MODUL 2: TRANSAKSI KASIR (POS)
# ---------------------------------------------------------
elif menu == "Transaksi Kasir":
    st.header("🛒 Point of Sales (Kasir)")
    
    conn = get_connection()
    df_products = pd.read_sql("SELECT * FROM products WHERE stock > 0", conn)
    
    if "cart" not in st.session_state:
        st.session_state.cart = []
        
    col_input, col_cart = st.columns([1, 1])
    
    with col_input:
        st.subheader("Input Item Transaksi")
        if df_products.empty:
            st.error("Stok seluruh barang habis atau belum didaftarkan.")
        else:
            product_options = {row["name"]: row for index, row in df_products.iterrows()}
            
            selected_product_name = st.selectbox(
                "Cari / Pilih Nama Barang (Ketik untuk rekomendasi):",
                options=list(product_options.keys())
            )
            
            if selected_product_name:
                prod_detail = product_options[selected_product_name]
                st.info(f"SKU: {prod_detail['code']} | Harga Paten: Rp {prod_detail['price']:,.0f} | Stok: {prod_detail['stock']}")
                
                qty = st.number_input("Jumlah (Qty):", min_value=1, max_value=int(prod_detail["stock"]), value=1)
                
                if st.button("➕ Tambah ke Keranjang"):
                    st.session_state.cart.append({
                        "product_id": prod_detail["id"],
                        "code": prod_detail["code"],
                        "name": prod_detail["name"],
                        "price": prod_detail["price"],
                        "qty": qty,
                        "subtotal": prod_detail["price"] * qty
                    })
                    st.success(f"{prod_detail['name']} ditambahkan ke keranjang.")
                
    with col_cart:
        st.subheader("Keranjang Belanja")
        if st.session_state.cart:
            cart_df = pd.DataFrame(st.session_state.cart)
            st.dataframe(cart_df[["code", "name", "price", "qty", "subtotal"]], use_container_width=True)
            
            total_bayar = cart_df["subtotal"].sum()
            st.markdown(f"### **Total: Rp {total_bayar:,.0f}**")
            
            if st.button("✅ Selesaikan & Simpan Transaksi"):
                cursor = conn.cursor()
                trx_code = f"TRX-{int(datetime.now().timestamp())}"
                today_str = datetime.now().strftime("%Y-%m-%d")
                
                for item in st.session_state.cart:
                    cursor.execute("""
                        INSERT INTO sales (transaction_code, date, product_id, quantity, total_price)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (trx_code, today_str, item["product_id"], item["qty"], item["subtotal"]))
                    
                    cursor.execute("""
                        UPDATE products SET stock = stock - %s WHERE id = %s
                    """, (item["qty"], item["product_id"]))
                    
                conn.commit()
                cursor.close()
                st.session_state.cart = []
                
                update_fast_moving_status()
                
                st.success(f"Transaksi {trx_code} Berhasil Disimpan!")
                st.rerun()
                
            if st.button("🗑️ Kosongkan Keranjang"):
                st.session_state.cart = []
                st.rerun()
        else:
            st.info("Keranjang belanja masih kosong.")
            
    conn.close()

# ---------------------------------------------------------
# MODUL 3: MASTER DATA PRODUK (CRUD BARANG) - PEMILIK
# ---------------------------------------------------------
elif menu == "Data Produk":
    st.header("📦 Kelola Data Produk")
    
    update_fast_moving_status()
    conn = get_connection()
    
    tab1, tab2, tab3, tab4 = st.tabs(["Daftar Produk", "Tambah Produk Baru", "Update Harga & Stok", "Edit / Hapus Produk"])
    
    with tab1:
        st.subheader("Daftar Seluruh Produk Toko")
        df_all = pd.read_sql("SELECT * FROM products", conn)
        st.dataframe(df_all, use_container_width=True)
        
    with tab2:
        st.subheader("Tambah Produk Baru ke Sistem")
        with st.form("form_add_product"):
            code = st.text_input("Kode Produk (SKU):")
            name = st.text_input("Nama Barang:")
            category = st.text_input("Kategori:")
            price = st.number_input("Harga Satuan Paten (Rp):", min_value=0.0, step=500.0)
            stock = st.number_input("Jumlah Stok Awal:", min_value=0, step=1)
            
            submit = st.form_submit_button("Simpan Produk Baru")
            if submit:
                if code and name:
                    try:
                        cursor = conn.cursor()
                        cursor.execute("""
                            INSERT INTO products (code, name, category, price, stock, is_fast_moving)
                            VALUES (%s, %s, %s, %s, %s, 0)
                        """, (code, name, category, price, stock))
                        conn.commit()
                        cursor.close()
                        st.success("Produk berhasil ditambahkan!")
                        st.rerun()
                    except Exception:
                        st.error("Kode produk (SKU) sudah terdaftar!")
                else:
                    st.warning("Kode dan Nama produk wajib diisi.")
                    
    with tab3:
        st.subheader("Perbarui Harga Paten & Tambah Stok Masuk")
        df_products_edit = pd.read_sql("SELECT id, code, name, price, stock FROM products", conn)
        
        if df_products_edit.empty:
            st.info("Belum ada produk terdaftar.")
        else:
            product_dict = {row["name"]: row for index, row in df_products_edit.iterrows()}
            selected_edit_name = st.selectbox("Pilih Produk:", list(product_dict.keys()), key="select_update_stock")
            prod_to_edit = product_dict[selected_edit_name]
            
            with st.form("form_update_product"):
                new_price = st.number_input("Harga Paten Baru (Rp):", min_value=0.0, value=float(prod_to_edit["price"]), step=500.0)
                added_stock = st.number_input("Tambah Stok Masuk:", min_value=0, value=0, step=1)
                
                submit_update = st.form_submit_button("Simpan Perubahan Harga/Stok")
                if submit_update:
                    update_product_price_stock(prod_to_edit["id"], new_price, added_stock)
                    st.success("Perubahan harga dan stok berhasil disimpan!")
                    st.rerun()

    with tab4:
        st.subheader("Edit Detail / Hapus Produk")
        df_products_full = pd.read_sql("SELECT * FROM products", conn)
        
        if df_products_full.empty:
            st.info("Belum ada produk.")
        else:
            prod_full_dict = {row["name"]: row for index, row in df_products_full.iterrows()}
            selected_full_name = st.selectbox("Pilih Produk:", list(prod_full_dict.keys()), key="select_edit_full")
            current_prod = prod_full_dict[selected_full_name]
            
            with st.form("form_edit_details"):
                edit_code = st.text_input("Ubah Kode (SKU):", value=current_prod["code"])
                edit_name = st.text_input("Ubah Nama Barang:", value=current_prod["name"])
                edit_category = st.text_input("Ubah Kategori:", value=current_prod["category"])
                edit_price = st.number_input("Ubah Harga (Rp):", min_value=0.0, value=float(current_prod["price"]), step=500.0)
                
                submit_edit_details = st.form_submit_button("Simpan Perubahan Detail")
                if submit_edit_details:
                    res = update_product_details(current_prod["id"], edit_code, edit_name, edit_category, edit_price)
                    if res:
                        st.success("Detail produk berhasil diperbarui!")
                        st.rerun()
                    else:
                        st.error("Gagal memperbarui (Kode SKU duplikat).")
            
            st.divider()
            if st.button("🗑️ Hapus Produk Ini"):
                res_del = delete_product(current_prod["id"])
                if res_del:
                    st.success("Produk berhasil dihapus!")
                    st.rerun()
                else:
                    st.error("Gagal menghapus produk karena masih terikat dengan data riwayat transaksi.")
                    
    conn.close()

# ---------------------------------------------------------
# MODUL 4: RIWAYAT PENJUALAN & REKAPITULASI HARIAN
# ---------------------------------------------------------
elif menu == "Riwayat Penjualan":
    st.header("📜 Riwayat & Rekap Penjualan")
    
    conn = get_connection()
    tab1, tab2 = st.tabs(["Rekap Total Penjualan Per Hari", "Rincian Transaksi Detail"])
    
    with tab1:
        st.subheader("📊 Akumulasi Pendapatan & Kuantitas Terjual per Hari")
        query_daily = """
            SELECT date AS Tanggal, 
                   COUNT(DISTINCT transaction_code) AS Total_Transaksi, 
                   SUM(quantity) AS Total_Item_Terjual, 
                   SUM(total_price) AS Total_Pendapatan
            FROM sales 
            GROUP BY date 
            ORDER BY date DESC
        """
        df_daily = pd.read_sql(query_daily, conn)
        
        if df_daily.empty:
            st.info("Belum ada data penjualan tercatat.")
        else:
            df_daily_display = df_daily.copy()
            df_daily_display["Total_Pendapatan"] = df_daily_display["Total_Pendapatan"].apply(lambda x: f"Rp {x:,.0f}")
            st.dataframe(df_daily_display, use_container_width=True)
            
            st.divider()
            st.subheader("Grafik Tren Pendapatan Harian")
            fig_daily = px.bar(
                df_daily, 
                x="Tanggal", 
                y="Total_Pendapatan",
                text="Total_Pendapatan",
                title="Total Pendapatan Berdasarkan Tanggal Penjualan"
            )
            st.plotly_chart(fig_daily, use_container_width=True)
            
    with tab2:
        st.subheader("Daftar Seluruh Item Transaksi Masuk")
        query_history = """
            SELECT s.transaction_code AS Kode_Transaksi, 
                   s.date AS Tanggal, 
                   p.name AS Nama_Barang, 
                   s.quantity AS Qty, 
                   s.total_price AS Subtotal
            FROM sales s
            JOIN products p ON s.product_id = p.id
            ORDER BY s.id DESC
        """
        df_history = pd.read_sql(query_history, conn)
        
        if df_history.empty:
            st.info("Belum ada rincian transaksi.")
        else:
            st.dataframe(df_history, use_container_width=True)
            
    conn.close()

# ---------------------------------------------------------
# MODUL 5: KELOLA PENGGUNA (CRUD USER) - PEMILIK
# ---------------------------------------------------------
elif menu == "Kelola Pengguna":
    st.header("👥 Manajemen Akun & Hak Akses Pengguna")
    
    tab1, tab2 = st.tabs(["Daftar Pengguna", "Tambah Pengguna Baru"])
    users_list = get_all_users()
    
    with tab1:
        st.subheader("Daftar Akun yang Terdaftar")
        df_users = pd.DataFrame(users_list)
        st.dataframe(df_users, use_container_width=True)
        
        user_to_delete = st.selectbox(
            "Pilih User yang Akan Dihapus:", 
            [u["id"] for u in users_list], 
            format_func=lambda x: next(u["username"] for u in users_list if u["id"] == x)
        )
        if st.button("🗑️ Hapus Pengguna"):
            if user_to_delete == 1:
                st.error("Akun Administrator utama tidak dapat dihapus!")
            else:
                delete_user(user_to_delete)
                st.success("Pengguna berhasil dihapus!")
                st.rerun()
                
    with tab2:
        st.subheader("Tambah Akun Kasir / Pemilik Baru")
        with st.form("form_add_user"):
            new_user = st.text_input("Username:")
            new_pass = st.text_input("Password:", type="password")
            new_role = st.selectbox("Hak Akses (Role):", ["Kasir", "Pemilik"])
            
            submit_user = st.form_submit_button("Simpan Pengguna")
            if submit_user:
                if new_user and new_pass:
                    res = add_user(new_user, new_pass, new_role)
                    if res:
                        st.success(f"Akun {new_user} berhasil ditambahkan!")
                        st.rerun()
                    else:
                        st.error("Username sudah terdaftar.")
                else:
                    st.warning("Username dan Password wajib diisi.")