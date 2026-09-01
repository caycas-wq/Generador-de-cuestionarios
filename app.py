import json
import docx
from google import genai
import pypdf
import streamlit as st

st.set_page_config(
    page_title="Generador de Cuestionarios", page_icon="📚", layout="centered"
)

# Inicializar estados de memoria
if "saved_quizzes" not in st.session_state:
  st.session_state["saved_quizzes"] = {}
if "api_key" not in st.session_state:
  st.session_state["api_key"] = ""

st.title("📚 Generador de Cuestionarios Personalizable")

# --- BARRA LATERAL ---
with st.sidebar:
  st.header("⚙️ Configuración")

  # Guardar la API Key de forma persistente en la sesión
  saved_key = st.text_input(
      "API Key de Google Gemini:",
      value=st.session_state["api_key"],
      type="password",
  )
  if saved_key:
    st.session_state["api_key"] = saved_key

  st.divider()
  st.subheader("🎯 Parámetros de Cuestionario")

  # Selector de cantidad de preguntas
  questions_per_section = st.slider(
      "Preguntas por sección:", min_value=1, max_value=10, value=3
  )

  # Selector de dificultad
  difficulty = st.selectbox(
      "Nivel de Dificultad:",
      ["Fácil (Directa)", "Intermedio (Análisis)", "Avanzado (Casos Prácticos)"],
      index=1,
  )

  # Selector de tipo de preguntas
  question_type = st.selectbox(
      "Tipo de Preguntas:",
      ["Opción Múltiple (4 opciones)", "Verdadero / Falso", "Combinado"],
  )

  st.divider()

  # --- HISTORIAL DE CUESTIONARIOS ---
  st.header("📂 Mis Cuestionarios Guardados")
  if st.session_state["saved_quizzes"]:
    selected_saved = st.selectbox(
        "Selecciona un cuestionario:",
        options=["-- Seleccionar --"]
        + list(st.session_state["saved_quizzes"].keys()),
    )

    if selected_saved != "-- Seleccionar --":
      if st.button("📖 Cargar Cuestionario"):
        st.session_state["quiz_data"] = st.session_state["saved_quizzes"][
            selected_saved
        ]
        st.session_state["active_title"] = selected_saved
        st.success(f"Cargado: {selected_saved}")
  else:
    st.info("Aún no has guardado cuestionarios.")

# --- ÁREA PRINCIPAL ---
uploaded_file = st.file_uploader(
    "Carga un nuevo documento (Word .docx, PDF o TXT)",
    type=["docx", "pdf", "txt"],
)

text_content = ""

if uploaded_file is not None:
  if uploaded_file.name.endswith(".docx"):
    doc = docx.Document(uploaded_file)
    text_content = "\n".join([para.text for para in doc.paragraphs if para.text])
  elif uploaded_file.name.endswith(".pdf"):
    reader = pypdf.PdfReader(uploaded_file)
    for page in reader.pages:
      text_content += page.extract_text() + "\n"
  elif uploaded_file.name.endswith(".txt"):
    text_content = uploaded_file.read().decode("utf-8")

# Generar cuestionario
if text_content and st.session_state["api_key"]:
  if st.button("🚀 Generar Nuevo Cuestionario"):
    with st.spinner("Analizando documento con IA y ajustando dificultad..."):
      try:
        client = genai.Client(api_key=st.session_state["api_key"])

        prompt = f"""
                Analiza el siguiente texto y organízalo en sus secciones/temas principales.
                Para cada sección, genera exactamente {questions_per_section} preguntas.

                CONFIGURACIÓN PEDAGÓGICA:
                - Nivel de dificultad: {difficulty}.
                - Tipo de pregunta deseado: {question_type}.

                REGLAS CRÍTICAS PARA LAS OPCIONES:
                1. Para Opción Múltiple: Genera 4 alternativas donde TODAS (correctas e incorrectas) tengan una longitud, complejidad y tono similar.
                2. Para Verdadero/Falso: Genera únicamente 2 opciones: ["Verdadero", "Falso"].
                3. NUNCA hagas que la opción correcta sea visiblemente más larga o detallada que los distractores.

                Devuelve EXCLUSIVAMENTE un JSON válido con esta estructura exacta:
                {{
                  "sections": [
                    {{
                      "sectionTitle": "Nombre de la Sección",
                      "questions": [
                        {{
                          "question": "Pregunta...",
                          "options": ["Opción A", "Opción B", "Opción C", "Opción D"],
                          "correctIndex": 0,
                          "explanation": "Explicación detallada..."
                        }}
                      ]
                    }}
                  ]
                }}

                Texto:
                {text_content[:20000]}
                """

        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt,
            config={"response_mime_type": "application/json"},
        )

        st.session_state["quiz_data"] = json.loads(response.text)
        st.session_state["active_title"] = (
            uploaded_file.name.rsplit(".", 1)[0].capitalize()
        )
      except Exception as e:
        st.error(f"Error al procesar el archivo: {e}")

elif not st.session_state["api_key"] and uploaded_file:
  st.warning("⚠️ Por favor ingresa tu API Key en la barra lateral izquierda.")

# --- RENDERIZADO DEL CUESTIONARIO ---
if "quiz_data" in st.session_state:
  st.divider()

  col1, col2 = st.columns([2, 1])
  with col1:
    quiz_name_input = st.text_input(
        "Nombre para guardar este cuestionario:",
        value=st.session_state.get("active_title", "Mi Cuestionario"),
    )
  with col2:
    st.write(" ")
    st.write(" ")
    if st.button("💾 Guardar en Biblioteca"):
      st.session_state["saved_quizzes"][quiz_name_input] = st.session_state[
          "quiz_data"
      ]
      st.success(f"¡'{quiz_name_input}' guardado con éxito!")

  st.divider()

  quiz = st.session_state["quiz_data"]
  for s_idx, sec in enumerate(quiz.get("sections", [])):
    st.header(f"📌 {sec['sectionTitle']}")
    for q_idx, q in enumerate(sec.get("questions", [])):
      st.subheader(f"{q_idx + 1}. {q['question']}")
      selected = st.radio(
          "Selecciona tu respuesta:", q["options"], key=f"q_{s_idx}_{q_idx}"
      )
      if st.button(
          f"Comprobar respuesta {q_idx + 1}", key=f"btn_{s_idx}_{q_idx}"
      ):
        correct_option = q["options"][q["correctIndex"]]
        if selected == correct_option:
          st.success(f"¡Correcto! {q['explanation']}")
        else:
          st.error(
              f"Incorrecto. La respuesta correcta era:"
              f" {correct_option}.\n\nExplicación: {q['explanation']}"
          )
