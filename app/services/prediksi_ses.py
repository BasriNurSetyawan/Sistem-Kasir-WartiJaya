def hitung_ses_mape(data_aktual, alpha=0.3):
    """
    Menghitung prediksi Single Exponential Smoothing dan akurasi MAPE.
    data_aktual: List agregasi total penjualan historis per periode (misal: harian).
    """
    n = len(data_aktual)
    if n == 0:
        return 0, 0
    elif n == 1:
        return data_aktual[0], 0

    # Inisialisasi list forecast (F1 = Y1)
    forecast = [data_aktual[0]] 

    # Perhitungan Single Exponential Smoothing (Ft)
    for i in range(1, n):
        # Ft = alpha * Y_{t-1} + (1 - alpha) * F_{t-1}
        f_next = (alpha * data_aktual[i-1]) + ((1 - alpha) * forecast[i-1])
        forecast.append(f_next)

    # Prediksi untuk periode berikutnya (t+1)
    prediksi_berikutnya = (alpha * data_aktual[-1]) + ((1 - alpha) * forecast[-1])

    # Perhitungan MAPE (Mean Absolute Percentage Error)
    total_error = 0
    count_valid = 0

    for i in range(1, n):
        y = data_aktual[i]
        f = forecast[i]
        if y != 0: # Mencegah ZeroDivisionError
            error = abs((y - f) / y)
            total_error += error
            count_valid += 1

    mape = (total_error / count_valid) * 100 if count_valid > 0 else 0

    return round(prediksi_berikutnya, 2), round(mape, 2)