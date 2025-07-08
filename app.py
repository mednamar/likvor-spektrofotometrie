import streamlit as st
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import io

st.set_page_config(page_title="Spektrofotometrie likvoru – Výpočet NBA a NOA")
st.title("Spektrofotometrie likvoru – Výpočet NBA a NOA")

st.markdown("""
Tento nástroj umožňuje:
- zadat absorbance mozkomíšního moku pro vlnové délky 370–600 nm (po 10 nm, včetně 415 a 476 nm)
- spočítat NBA (476 nm) a NOA (415 nm)
- provést korekci NBA při zvýšeném bilirubinu
- zobrazit interpretaci výsledku dle národní směrnice
- zobrazit grafické znázornění s baseline, tangenty a úsečkami
- uložit a načíst zadaná data mezi relacemi nebo z CSV
""")

if "abs_data" not in st.session_state:
    wavelengths = [370, 380, 390, 400, 410, 415, 420, 430, 440, 450, 460, 470, 476, 480, 490, 500, 510, 520, 530, 540, 550, 560, 570, 580, 590, 600]
    st.session_state.abs_data = {wl: 0.000 for wl in wavelengths}
    st.session_state.wavelengths = wavelengths

st.header("1. Zadejte hodnoty absorbance")
abs_table = st.data_editor(
    pd.DataFrame({"Vlnová délka (nm)": st.session_state.wavelengths, "Absorbance (AU)": [st.session_state.abs_data[wl] for wl in st.session_state.wavelengths]}),
    num_rows="fixed",
    use_container_width=True,
    key="abs_table_editor"
)

st.download_button(
    "💾 Uložit data jako CSV",
    data=abs_table.to_csv(index=False).encode("utf-8"),
    file_name="absorbance_data.csv",
    mime="text/csv"
)

uploaded_file = st.file_uploader("📂 Načíst data z CSV souboru", type=["csv"])
if uploaded_file is not None:
    df_uploaded = pd.read_csv(uploaded_file)
    if "Vlnová délka (nm)" in df_uploaded.columns and "Absorbance (AU)" in df_uploaded.columns:
        abs_table = df_uploaded.copy()
        st.success("Data byla úspěšně načtena z CSV.")
    else:
        st.error("CSV musí obsahovat sloupce 'Vlnová délka (nm)' a 'Absorbance (AU)'.")

if st.button("🔁 Resetovat zadání"):
    for wl in st.session_state.wavelengths:
        st.session_state.abs_data[wl] = 0.000
    st.experimental_rerun()

st.header("2. Zadejte biochemické parametry")
col1, col2, col3 = st.columns(3)
with col1:
    csf_prot = st.number_input("Protein v likvoru (g/L)", 0.0, 5.0, 0.5, 0.01)
with col2:
    serum_prot = st.number_input("Protein v séru (g/L)", 50.0, 100.0, 70.0, 0.1)
with col3:
    serum_bil = st.number_input("Bilirubin v séru (µmol/L)", 0, 500, 15, 1)

if st.button("Spočítat výsledky"):
    df = abs_table.rename(columns={"Vlnová délka (nm)": "wavelength", "Absorbance (AU)": "absorbance"})

    base1 = np.polyfit(df[(df.wavelength >= 370) & (df.wavelength <= 400)].wavelength,
                      df[(df.wavelength >= 370) & (df.wavelength <= 400)].absorbance, 1)
    base2 = np.polyfit(df[(df.wavelength >= 430) & (df.wavelength <= 530)].wavelength,
                      df[(df.wavelength >= 430) & (df.wavelength <= 530)].absorbance, 1)

    baseline = []
    for wl in df.wavelength:
        if wl <= 400:
            baseline.append(np.polyval(base1, wl))
        elif wl >= 430:
            baseline.append(np.polyval(base2, wl))
        else:
            baseline.append(np.nan)

    df["baseline"] = baseline
    df["diff"] = df["absorbance"] - df["baseline"]

    try:
        if 415 not in df.wavelength.values or 476 not in df.wavelength.values:
            st.error("Chyba: Nejsou zadány hodnoty pro 415 nm nebo 476 nm.")
        else:
            nba_val = df[df.wavelength == 476]["diff"].values[0]
            noa_val = df[df.wavelength == 415]["diff"].values[0]

            if pd.isna(nba_val) or pd.isna(noa_val):
                st.error("Chyba: Hodnoty pro 415 nm nebo 476 nm obsahují NaN.")
            else:
                nba = round(float(nba_val), 5)
                noa = round(float(noa_val), 5)

                st.header("3. Výsledky výpočtu")
                st.write(f"**NBA (476 nm):** {nba:.5f} AU")
                st.write(f"**NOA (415 nm):** {noa:.5f} AU")

                pa = (csf_prot / serum_prot) * serum_bil * 0.042
                nba_corr = nba - pa
                st.write(f"**PA (předpokládaná absorbance):** {pa:.5f} AU")
                st.write(f"**Adjusted NBA:** {nba_corr:.5f} AU")

                st.header("4. Interpretace")
                interpretation = ""
                if nba <= 0.007 and noa <= 0.02:
                    interpretation = "Negativní nález. SAH nepodporuje."
                elif nba <= 0.007 and 0.02 < noa < 0.1:
                    interpretation = "Oxyhemoglobin přítomen, ale bilirubin nezvýšen. SAH nepodporuje."
                elif nba <= 0.007 and noa >= 0.1:
                    interpretation = "Vysoký oxyhemoglobin může maskovat bilirubin. Výsledek nejednoznačný."
                elif nba > 0.007:
                    if serum_bil > 20 and csf_prot <= 1.0:
                        if nba_corr > 0.007:
                            interpretation = "Zvýšený bilirubin po korekci. Výsledek konzistentní se SAH."
                        else:
                            interpretation = "Bilirubin pravděpodobně způsoben zvýšeným sérovým bilirubinem. SAH nepodporuje."
                    elif csf_prot > 1.0:
                        interpretation = "Zvýšený bilirubin. Možný SAH, ale výsledek interpretovat opatrně."
                    else:
                        interpretation = "Zvýšený bilirubin. Výsledek konzistentní se SAH."

                st.success(f"Interpretace: {interpretation}")

                st.header("5. Graf absorbance a baseline")
                fig, ax = plt.subplots()
                ax.plot(df.wavelength, df.absorbance, label="Absorbance")
                ax.plot(df.wavelength, df.baseline, '--', label="Baseline")
                ax.axvline(415, color='red', linestyle='--', label='415 nm (NOA)')
                ax.axvline(476, color='blue', linestyle='--', label='476 nm (NBA)')

                y415 = df[df.wavelength == 415].absorbance.values[0]
                b415 = df[df.wavelength == 415].baseline.values[0]
                y476 = df[df.wavelength == 476].absorbance.values[0]
                b476 = df[df.wavelength == 476].baseline.values[0]

                ax.vlines(x=415, ymin=b415, ymax=y415, color='red')
                ax.vlines(x=476, ymin=b476, ymax=y476, color='blue')

                ax.set_xlabel("Vlnová délka (nm)")
                ax.set_ylabel("Absorbance (AU)")
                ax.legend()
                ax.grid(True)
                st.pyplot(fig)

                st.caption("Baseline určená lineární regresí mezi 370–400 a 430–530 nm.")

    except Exception as e:
        st.error(f"Došlo k chybě při výpočtu: {str(e)}")
