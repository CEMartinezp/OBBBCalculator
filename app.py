
	import streamlit as st
	import requests
	from datetime import datetime

	WORKER_BASE = "https://obbb-tax-calculator.joncamacaro.workers.dev"
	VALIDATE_URL = f"{WORKER_BASE}/validate-token"
	CONSUME_URL = f"{WORKER_BASE}/consume-token"

	st.set_page_config(page_title="OBBB Tax Calculator", layout="centered")

	token = st.query_params.get("token")

	st.title("OBBB Tax Calculator")

	if not token:
	    st.warning("No token detected")
	    st.stop()

	# VALIDATE
	r = requests.get(VALIDATE_URL, params={"token": token})
	st.write("VALIDATE RESPONSE:", r.json())

	if not r.json().get("valid"):
	    st.error("Token inválido")
	    st.stop()

	data = r.json()

	expiry_date = datetime.fromtimestamp(
	    data["expires_at"] / 1000
	).strftime("%Y-%m-%d")

	if data["type"] == "sub":
	    st.info(f"Usos restantes: {data['uses_left']}")
	    st.info(f"Válido hasta: {expiry_date}")
	else:
	    st.info(f"Acceso único. Vence el: {expiry_date}")

	income = st.number_input("Ingreso anual", min_value=0.0, value=1000.0)
	expenses = st.number_input("Gastos anuales", min_value=0.0, value=200.0)

	if st.button("Calcular"):

	    r2 = requests.post(
	        CONSUME_URL,
	        json={"token": token}
	    )

	    st.write("CONSUME RESPONSE:", r2.json())

	    if r2.json().get("success"):
	        st.success("CALCULO EXITOSO")
	        result = income - expenses
	        st.write("Resultado:", result)
	    else:
	        st.error("Fallo al consumir token")
